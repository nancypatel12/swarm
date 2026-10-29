import asyncio
import json
from datetime import UTC, datetime

import pytest

from swarm import papers
from swarm.llm import parse_json
from swarm.papers import (
    Paper,
    arxiv_query,
    clean_math,
    closing_sections,
    code_link,
    independent_groups,
    merge_by_rank,
    parse_feed,
)
from swarm.verify import found_in

FEED = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>http://arxiv.org/abs/2610.01234v2</id>
    <published>2026-10-01T12:00:00Z</published>
    <title>Long audio
      with diffusion</title>
    <summary>  We study long audio.  </summary>
    <author><name>A. Rivera</name></author>
    <author><name>B. Okafor</name></author>
  </entry>
  <entry>
    <id>http://arxiv.org/abs/2401.00001v1</id>
    <published>2024-01-01T12:00:00Z</published>
    <title>Too old</title>
    <summary>Old.</summary>
    <author><name>C. Old</name></author>
  </entry>
</feed>"""


def test_feed_keeps_recent_papers_and_cleans_fields():
    [p] = parse_feed(FEED, since=datetime(2026, 5, 1, tzinfo=UTC))
    assert (p.id, p.title, p.abstract, p.published) == (
        "2610.01234",
        "Long audio with diffusion",
        "We study long audio.",
        "2026-10-01",
    )
    assert p.authors == ["A. Rivera", "B. Okafor"] and p.url == "https://arxiv.org/abs/2610.01234"


def test_arxiv_query_drops_symbols_that_change_its_meaning():
    q = arxiv_query(["RLHF: (reward) model", "-"], datetime(2026, 5, 1), datetime(2026, 10, 28))
    assert q.startswith('all:"RLHF reward model" AND submittedDate')
    assert arxiv_query(["?!", "--"], datetime(2026, 5, 1), datetime(2026, 10, 28)) == ""


def test_arxiv_is_retried_after_errors(monkeypatch):
    import httpx

    calls = []

    class Flaky:
        def __init__(self, **_):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return False

        async def get(self, url, params):
            calls.append(1)
            request = httpx.Request("GET", url)
            status = 503 if len(calls) < 3 else 200
            return httpx.Response(status, text=FEED, request=request)

    async def no_wait(*_):
        return None

    monkeypatch.setattr(papers.httpx, "AsyncClient", Flaky)
    monkeypatch.setattr(papers, "_wait_turn", no_wait)
    monkeypatch.setattr(papers.asyncio, "sleep", no_wait)
    assert asyncio.run(papers._get({})) == FEED and len(calls) == 3
    # The same search again is answered from disk.
    assert asyncio.run(papers._get({})) == FEED and len(calls) == 3


def test_arxiv_query_needs_every_phrase_within_the_dates():
    q = arxiv_query(['reward "model"', "outcome"], datetime(2026, 5, 1), datetime(2026, 10, 28))
    assert q == 'all:"reward model" AND all:"outcome" AND submittedDate:[202605010000 TO 202610282359]'


def test_closing_sections_keep_only_where_authors_say_what_is_left():
    markdown = (
        "# 1 Introduction\nWe do X.\n## 5 Results\nIt works.\n## 6 Limitations\nY is open.\n## 7 Conclusion\nZ next."
    )
    text = closing_sections(markdown)
    assert "Y is open." in text and "Z next." in text
    assert "We do X." not in text and "It works." not in text


def test_merging_takes_the_best_of_every_search_first():
    def p(pid):
        return Paper(id=pid, title=pid, authors=[], published="2026-10-01", abstract="")

    a, b = [p("a1"), p("a2"), p("a3")], [p("b1"), p("a1"), p("b2")]
    assert [x.id for x in merge_by_rank([a, b], 4)] == ["a1", "b1", "a2", "a3"]
    assert merge_by_rank([], 4) == []


@pytest.mark.parametrize(
    ("raw", "clean"),
    [
        # Doubled math from real runs.
        ("how to choose the budget kk, although", "how to choose the budget k, although"),
        ("at 1,0001{,}000 pairs", "at 1,000 pairs"),
        ("head (cos>0.9999\\cos>0.9999) may", "head (cos>0.9999) may"),
        ("lose 6.66.6\u201311.011.0 points", "lose 6.6\u201311.0 points"),
        ("with $k$ samples", "with k samples"),
        ("predicate invention [[38](#bib.bib46)] is next", "predicate invention [38] is next"),
        ("as in ([Li et al., 2023](#bib.bib54)).", "as in (Li et al., 2023)."),
        # Ordinary text must not change.
        ("see [our code](https://github.com/x/y)", "see [our code](https://github.com/x/y)"),
        ("in 2020 and 1919", "in 2020 and 1919"),
        ("a Phase II trial", "a Phase II trial"),
        ("version 1.2 of 3.4", "version 1.2 of 3.4"),
        ("a class of models", "a class of models"),
    ],
)
def test_math_debris_is_cleaned_and_ordinary_text_is_not(raw, clean):
    assert clean_math(raw) == clean


def test_shared_authors_count_as_one_group():
    def paper(*authors):
        return Paper(id="x", title="t", authors=list(authors), published="2026-10-01", abstract="")

    # The third paper links the first two, so all three are one group; the fourth is independent.
    assert independent_groups([paper("A"), paper("B"), paper("a", "b"), paper("C")]) == 2


@pytest.mark.parametrize(
    ("quote", "ok"),
    [
        ("remains an open problem for diffusion models", True),
        ("Remains an  open PROBLEM for diffusion models.", True),
        ("is still an open problem for diffusion models", False),  # paraphrased
        ("an open problem", False),  # too short to count as a quote
    ],
)
def test_quotes_must_appear_word_for_word(quote, ok):
    assert found_in(quote, "Long audio remains an open problem for diffusion models.") is ok


def test_ligatures_from_typeset_papers_still_match():
    typeset = "We leave e\ufb03cient \ufb01ne-tuning to future work."
    assert found_in("we leave efficient fine tuning to future work", typeset)


def test_curly_quotes_and_dashes_still_match():
    assert found_in("the model\u2019s memory \u2014 not its size", "The model's memory - not its size - matters.")


def test_parse_json_skips_reasoning_and_fences():
    assert parse_json('<think>{"wrong": 1}</think>\n```json\n{"ok": true}\n```') == {"ok": True}


def test_parse_json_rejects_prose():
    with pytest.raises(ValueError):
        parse_json("There are three open problems.")


def test_arxiv_requests_wait_three_seconds_for_each_other(monkeypatch):
    clock = {"now": 1000.0}
    waits = []

    async def sleep(seconds):
        waits.append(round(seconds, 1))
        clock["now"] += seconds

    monkeypatch.setattr(papers.time, "monotonic", lambda: clock["now"])
    monkeypatch.setattr(papers.asyncio, "sleep", sleep)
    monkeypatch.setattr(papers, "_last_request", 0.0)

    async def three():
        await papers._wait_turn()
        clock["now"] += 1  # the request itself takes a second
        await papers._wait_turn()
        await papers._wait_turn()

    asyncio.run(three())
    assert waits == [2.0, 3.0]


OPENALEX_PAGE = {
    "results": [
        {
            "title": "Process  supervision at scale",
            "publication_date": "2026-10-21",
            "authorships": [{"author": {"display_name": "Ada Lovelace"}}, {"author": None}],
            "locations": [
                {"landing_page_url": "https://doi.org/x"},
                {"landing_page_url": "https://arxiv.org/abs/2610.29498v2"},
            ],
            "abstract_inverted_index": {"open.": [2], "We": [0], "leave": [1]},
        },
        {"title": "Not on arXiv", "locations": [{"landing_page_url": "https://example.org/paper"}]},
    ]
}


def test_openalex_results_become_arxiv_papers():
    [p] = papers.parse_openalex(OPENALEX_PAGE)
    assert (p.id, p.title, p.authors, p.published) == (
        "2610.29498",
        "Process supervision at scale",
        ["Ada Lovelace"],
        "2026-10-21",
    )
    assert p.abstract == "We leave open." and p.url == "https://arxiv.org/abs/2610.29498"


def test_openalex_search_needs_every_phrase_from_arxiv_within_the_dates(monkeypatch):
    monkeypatch.delenv("SWARM_CONTACT", raising=False)
    params = papers.openalex_params(['reward "model"', "outcome"], datetime(2026, 5, 1), datetime(2026, 10, 28), 80)
    assert params["search"] == '"reward model" AND "outcome"'
    assert params["filter"] == (
        "from_publication_date:2026-05-01,to_publication_date:2026-10-28,locations.source.id:S4306400194"
    )
    assert "mailto" not in params


def test_search_falls_back_to_openalex_and_lets_arxiv_rest(monkeypatch):
    asked = []

    async def get(params, url=papers.ARXIV):
        asked.append(url)
        if url == papers.ARXIV:
            raise papers.httpx.ConnectTimeout("arXiv is down")
        return json.dumps(OPENALEX_PAGE)

    monkeypatch.setattr(papers, "_get", get)
    monkeypatch.setattr(papers, "_arxiv_rests_until", 0.0)
    assert [p.id for p in asyncio.run(papers.search(["process supervision"], 10))] == ["2610.29498"]
    asyncio.run(papers.search(["reward model"], 10))
    # The second search doesn't wait on arXiv again.
    assert asked == [papers.ARXIV, papers.OPENALEX, papers.OPENALEX]


def test_a_code_link_is_the_papers_own_not_one_from_its_references():
    page = "Our code is at https://github.com/lab/poil.git.\n## 6 Limitations\nx\n## References\nhttps://github.com/other/tool"
    assert code_link(page) == "https://github.com/lab/poil"
    assert code_link("## References\nhttps://github.com/other/tool") == ""
