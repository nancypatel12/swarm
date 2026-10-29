"""Recent papers from arXiv: find them, read the sections where authors say what's unsolved, and tell which
papers come from independent groups. Searches go to arXiv's API, or to OpenAlex's index of arXiv when arXiv
doesn't answer."""

import asyncio
import hashlib
import json
import os
import re
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

import httpx

from . import store

ARXIV = "https://export.arxiv.org/api/query"
# arXiv asks for one request every three seconds, across everything a server sends.
ARXIV_GAP = 3.0
ARXIV_TRIES = 3
# arXiv answers 429 when one address asks too often, and keeps refusing for a while, so a 429 waits much longer.
ARXIV_BUSY_WAIT = 20.0
# The same search within a day is answered from disk, so a repeated question costs arXiv nothing.
ARXIV_CACHE_SECONDS = 24 * 3600
# arXiv's API once stopped answering this project's address for hours. After a failure, searches go to OpenAlex,
# a free index of scholarly papers that includes arXiv's, and arXiv is tried again after this long.
ARXIV_REST_SECONDS = 600
OPENALEX = "https://api.openalex.org/works"
# arXiv's ID as a source in OpenAlex.
OPENALEX_ARXIV = "S4306400194"
_ARXIV_URL = re.compile(r"arxiv\.org/abs/(.+?)(?:v\d+)?$")
_arxiv_rests_until = 0.0
ATOM = {"a": "http://www.w3.org/2005/Atom"}
MAX_SECTION_CHARS = 6000
# Where authors say what's left: these headings, or the closing sections that usually hold it.
_SECTION = re.compile(r"^#{1,4}\s*(?:\d+(?:\.\d+)*\.?\s*)?(.+)$", re.MULTILINE)
_WANTED = re.compile(r"limitation|future|open (?:problem|question|challenge)|discussion|conclusion", re.IGNORECASE)


@dataclass
class Paper:
    id: str
    title: str
    authors: list[str]
    published: str
    abstract: str
    # The sections Swarm read, or the abstract when the full text couldn't be read.
    text: str = ""
    source: str = "abstract"
    # The authors' own code repository, when the paper links one before its references.
    code: str = ""
    url: str = field(init=False)

    def __post_init__(self) -> None:
        self.url = f"https://arxiv.org/abs/{self.id}"

    def meta(self) -> dict:
        # The abstract is sent too, so the page can print the paper while it's read.
        fields = {k: getattr(self, k) for k in ("id", "title", "authors", "published", "url")}
        return {**fields, "abstract": self.abstract[:900]}


def clean_math(text: str) -> str:
    """Math in arXiv pages comes out twice, as symbols and then as TeX: "the budget kk", "1,0001{,}000",
    "cos>0.9999\\cos>0.9999", "6.66.6". Citations come as links to the reference list, "[[38](#bib.bib46)]", and
    keep only their text, "[38]". Quotes are checked against this cleaned text, so they stay word for word and read
    cleanly."""
    text = re.sub(r"\[([^\[\]]*)\]\(#[^)\s]*\)", r"\1", text)
    text = text.replace("{,}", ",").replace("$", "")
    text = re.sub(r"\\([a-zA-Z]+)", r"\1", text)
    text = re.sub(r"[{}]", "", text)
    # A piece repeated back to back: one lowercase letter, or a number with a separator or symbol in it. Plain
    # digit runs are left alone, so "2020" stays a year and "Phase II" stays as written.
    edge, stop = r"(?<![^\s\u2013\u2014(\[/])", r"(?=[\s.,;:)\]\u2013\u2014/]|$)"
    text = re.sub(edge + r"([a-z]|[^\s\u2013\u2014]*\d[^\s\u2013\u2014\d][^\s\u2013\u2014]*?)\1" + stop, r"\1", text)
    return re.sub(r"[ \t]{2,}", " ", text)


def parse_feed(xml: str, since: datetime) -> list[Paper]:
    papers = []
    for entry in ET.fromstring(xml).findall("a:entry", ATOM):
        published = entry.findtext("a:published", "", ATOM)
        if not published or datetime.fromisoformat(published.replace("Z", "+00:00")) < since:
            continue
        papers.append(
            Paper(
                # "http://arxiv.org/abs/2601.01234v2" becomes "2601.01234".
                id=re.sub(r"v\d+$", "", entry.findtext("a:id", "", ATOM).rsplit("/abs/", 1)[-1]),
                title=" ".join(entry.findtext("a:title", "", ATOM).split()),
                authors=[a.findtext("a:name", "", ATOM).strip() for a in entry.findall("a:author", ATOM)],
                published=published[:10],
                abstract=clean_math(" ".join(entry.findtext("a:summary", "", ATOM).split())),
            )
        )
    return papers


_last_request = 0.0
_locks: dict[asyncio.AbstractEventLoop, asyncio.Lock] = {}


async def _wait_turn() -> None:
    """Every arXiv request on this server, from any run, waits until three seconds after the previous one."""
    global _last_request
    async with _locks.setdefault(asyncio.get_running_loop(), asyncio.Lock()):
        if (wait := _last_request + ARXIV_GAP - time.monotonic()) > 0:
            await asyncio.sleep(wait)
        _last_request = time.monotonic()


def arxiv_query(phrases: list[str], since: datetime, until: datetime) -> str:
    """Every phrase must appear as written, within the date range. Single words matched thousands of loosely related
    papers in a real run ("reward" alone is in most reinforcement learning papers), so the searches are phrases."""
    # Quotes, colons and brackets would change the query's meaning, so phrases keep only words and hyphens.
    clean = [" ".join(re.sub(r"[^\w\s-]", " ", p).split()) for p in phrases]
    terms = " AND ".join(f'all:"{p}"' for p in clean if re.search(r"[^\W_]", p))
    # With no phrase left, the date range alone would match every paper, so there's no query at all.
    return f"{terms} AND submittedDate:[{since:%Y%m%d}0000 TO {until:%Y%m%d}2359]" if terms else ""


async def search(phrases: list[str], limit: int, months: int = 6) -> list[Paper]:
    """The papers most relevant to the phrases, from the last few months. Sorted by relevance: sorted by date, a
    real run got whatever was posted that day."""
    global _arxiv_rests_until
    now = datetime.now(UTC)
    since = now - timedelta(days=30 * months)
    if not (query := arxiv_query(phrases, since, now)):
        return []
    if time.time() >= _arxiv_rests_until:
        try:
            params = {"search_query": query, "sortBy": "relevance", "max_results": str(limit)}
            return parse_feed(await _get(params), since)
        except httpx.HTTPError as e:
            print(f"arXiv didn't answer ({e!r}); searching OpenAlex for {ARXIV_REST_SECONDS} s")
            _arxiv_rests_until = time.time() + ARXIV_REST_SECONDS
    return parse_openalex(json.loads(await _get(openalex_params(phrases, since, now, limit), OPENALEX)))


def openalex_params(phrases: list[str], since: datetime, until: datetime, limit: int) -> dict:
    """The same search on OpenAlex: every phrase exactly, arXiv papers only, within the dates, most relevant first."""
    clean = [" ".join(re.sub(r"[^\w\s-]", " ", p).split()) for p in phrases]
    params = {
        "search": " AND ".join(f'"{p}"' for p in clean if p),
        "filter": f"from_publication_date:{since:%Y-%m-%d},to_publication_date:{until:%Y-%m-%d},"
        f"locations.source.id:{OPENALEX_ARXIV}",
        "sort": "relevance_score:desc",
        "per_page": str(min(limit, 200)),
        "select": "title,publication_date,authorships,locations,abstract_inverted_index",
    }
    # OpenAlex asks for a contact address to use its faster pool; it's optional and never filled in by default.
    if contact := os.environ.get("SWARM_CONTACT"):
        params["mailto"] = contact
    return params


def parse_openalex(data: dict) -> list[Paper]:
    papers = []
    for w in data.get("results", []):
        urls = [loc.get("landing_page_url") or "" for loc in w.get("locations") or []]
        ids = [m.group(1) for u in urls if (m := _ARXIV_URL.search(u))]
        if not ids or not w.get("title"):
            continue
        # OpenAlex stores abstracts as word positions; this puts the words back in order.
        index = w.get("abstract_inverted_index") or {}
        words = sorted((pos, word) for word, positions in index.items() for pos in positions)
        papers.append(
            Paper(
                id=ids[0],
                title=" ".join(w["title"].split()),
                authors=[a["author"]["display_name"] for a in w.get("authorships") or [] if a.get("author")],
                published=w.get("publication_date") or "",
                abstract=clean_math(" ".join(word for _, word in words)),
            )
        )
    return papers


async def _get(params: dict, url: str = ARXIV) -> str:
    """arXiv sometimes answers slowly or with 429 and 503; each retry waits its turn and then a little longer.
    OpenAlex asks for no such gap, so its requests skip the queue."""
    key = hashlib.sha256(json.dumps([url, params], sort_keys=True).encode()).hexdigest()[:24]
    cached = store.DATA_DIR / "arxiv" / f"{key}.txt"
    if cached.exists() and time.time() - cached.stat().st_mtime < ARXIV_CACHE_SECONDS:
        return cached.read_text()
    for attempt in range(ARXIV_TRIES):
        if url == ARXIV:
            await _wait_turn()
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                r = await client.get(url, params=params)
                r.raise_for_status()
                cached.parent.mkdir(parents=True, exist_ok=True)
                cached.write_text(r.text)
                return r.text
        except httpx.HTTPError as e:
            # A server that doesn't answer at all rarely answers a retry, so a timeout gives up at once.
            if attempt == ARXIV_TRIES - 1 or isinstance(e, httpx.TimeoutException):
                raise
            busy = isinstance(e, httpx.HTTPStatusError) and e.response.status_code == 429
            await asyncio.sleep((ARXIV_BUSY_WAIT if busy else ARXIV_GAP) * (attempt + 1))
    raise AssertionError("unreachable")


def merge_by_rank(results: list[list[Paper]], limit: int) -> list[Paper]:
    """Takes the best paper from each search in turn, then the second best, and so on, skipping repeats. Each search
    is sorted by relevance, so this keeps the papers most relevant to every search, not just to the first."""
    merged: dict[str, Paper] = {}
    for rank in range(max((len(r) for r in results), default=0)):
        for r in results:
            if rank < len(r):
                merged.setdefault(r[rank].id, r[rank])
    return list(merged.values())[:limit]


def closing_sections(markdown: str) -> str:
    """The limitations, future work, discussion and conclusion sections of a paper, up to a fixed length."""
    heads = list(_SECTION.finditer(markdown))
    parts = []
    for i, h in enumerate(heads):
        if _WANTED.search(h.group(1)):
            end = heads[i + 1].start() if i + 1 < len(heads) else len(markdown)
            parts.append(markdown[h.start() : end].strip())
    return "\n\n".join(parts)[:MAX_SECTION_CHARS]


async def read(papers: list[Paper]) -> None:
    """Reads each paper's closing sections from its arXiv HTML page with Tavily Extract, 20 pages per call. A paper
    whose page can't be read, or that has no such sections, falls back to its abstract."""
    from tavily import AsyncTavilyClient

    client = AsyncTavilyClient(api_key=os.environ["TAVILY_API_KEY"])
    by_id = {p.id: p for p in papers}
    urls = [f"https://arxiv.org/html/{p.id}" for p in papers]

    async def batch(chunk: list[str]) -> list[dict]:
        try:
            return (await client.extract(urls=chunk, format="markdown", timeout=60)).get("results", [])
        except Exception as e:
            print(f"Tavily Extract failed for {len(chunk)} papers: {e}")
            return []

    for results in await asyncio.gather(*(batch(urls[i : i + 20]) for i in range(0, len(urls), 20))):
        for r in results:
            # The page may come back under a versioned address, like .../html/2601.01234v2.
            match = re.search(r"/html/([^/v]+)", r.get("url", ""))
            paper = by_id.get(match.group(1)) if match else None
            if paper:
                paper.code = code_link(r.get("raw_content") or "")
            if paper and (text := clean_math(closing_sections(r.get("raw_content") or ""))):
                paper.text, paper.source = text, "full text"
    for p in papers:
        if not p.text:
            p.text = p.abstract


def code_link(markdown: str) -> str:
    """The first GitHub repository a paper links before its references. A real run told readers to "extract the
    code" of papers that may never have released any; links in the references are other people's code."""
    body = re.split(
        r"(?:^|\n)#+\s*(?:\d+\s*)?(?:References|Bibliography)\b", markdown, maxsplit=1, flags=re.IGNORECASE
    )[0]
    m = re.search(r"https?://(?:www\.)?github\.com/[\w.-]+/[\w-]+(?:\.[\w-]+)*", body)
    return m.group(0).removesuffix(".git") if m else ""


def independent_groups(papers: list[Paper]) -> int:
    """Papers that share an author count as one group, so one lab repeating itself isn't mistaken for agreement."""
    groups: list[set[str]] = []
    for p in papers:
        names = {a.lower() for a in p.authors}
        touching = [g for g in groups if g & names]
        for g in touching:
            groups.remove(g)
            names |= g
        groups.append(names)
    return len(groups)
