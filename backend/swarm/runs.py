"""One run: understand the reader, find recent papers, read them all at once, and turn what they say is unsolved
into a short list of open problems.

Every step is published as an event. The page replays past events on connect, so a refresh never loses a run.
"""

import asyncio
import os
import time
import uuid

from . import papers as arxiv
from . import store
from .llm import get_llm
from .problems import answer, check_addressed, explain, extract, group, phrases, terms_in, understand

# Up to this many of the most relevant papers from the last six months.
PAPERS = int(os.environ.get("SWARM_PAPERS", "80"))
# Key terms that get a search of their own, on top of the model's searches.
TERM_SEARCHES = 3
# Fewer papers than this and the field's everyday name is searched too: a real run's specific phrases found only 3.
THIN = 30

if os.environ.get("SWARM_STAND_IN") == "1":
    # Local checks with no network and no cost. Never on by default.
    from . import stand_in

    arxiv.search, arxiv.read = stand_in.search, stand_in.read


class Run:
    def __init__(self, text: str) -> None:
        self.id = uuid.uuid4().hex[:12]
        self.text = text
        self.created = time.time()
        self.events: list[dict] = []
        self.listeners: set[asyncio.Queue] = set()
        self.done = False

    @classmethod
    def from_saved(cls, data: dict) -> "Run":
        run = cls.__new__(cls)
        run.id, run.text, run.created, run.events = data["id"], data["input"], data["created"], data["events"]
        run.listeners, run.done = set(), True
        return run

    def emit(self, event: dict) -> None:
        self.events.append(event)
        for q in self.listeners:
            q.put_nowait(event)

    def step(self, id_: str, label: str, done: bool = False) -> None:
        self.emit({"type": "step", "id": id_, "label": label, "done": done})

    def start(self) -> asyncio.Task:
        async def guarded():
            try:
                await self._run()
            except Exception as e:
                self.emit({"type": "error", "message": str(e) or e.__class__.__name__})
            finally:
                self.done = True
                try:
                    store.save(self.id, self.text, self.created, self.events)
                except OSError as e:
                    print(f"Couldn't save run {self.id}: {e}")

        return asyncio.create_task(guarded())

    async def _run(self) -> None:
        began = time.perf_counter()
        llm = get_llm()

        self.step("reader", "Reading what you're looking for")
        reader = await understand(llm, self.text)
        self.step("reader", f"Looking for open problems in {reader.field}", True)

        # Each key term gets its own search too: in a real run the model named "outcome supervision" as the term for
        # the question, then searched only for broader phrases.
        searches = list(reader.queries)
        for t in reader.terms[:TERM_SEARCHES]:
            if not any(t["term"].lower() == p.lower() for q in searches for p in q) and (term := phrases([t["term"]])):
                searches.append(term)
        shown = list(dict.fromkeys(p for q in searches for p in q))
        self.step("search", "Searching arXiv for " + ", ".join(f"\u201c{p}\u201d" for p in shown))
        results: list[list] = []
        failed = 0
        for query in searches:
            try:
                found_here = await arxiv.search(query, PAPERS)
                # Every phrase must appear, which can match nothing; then each phrase is tried on its own.
                if not found_here and len(query) > 1:
                    for phrase in query:
                        found_here += await arxiv.search([phrase], PAPERS)
                results.append(found_here)
            except Exception as e:
                # One search failing shouldn't sink the run if the others found papers.
                failed += 1
                print(f"arXiv search failed for {query}: {e}")
        # Surveys and position papers are where a field writes down its own open questions, not one method's caveats.
        try:
            results.append(await arxiv.search([searches[0][0], "survey"], PAPERS // 4))
        except Exception as e:
            print(f"arXiv survey search failed: {e}")
        found = arxiv.merge_by_rank(results, PAPERS)
        if len(found) < THIN and reader.broad:
            # The specific results stay first; the wider search only fills the rest.
            try:
                found = arxiv.merge_by_rank([found + await arxiv.search([reader.broad], PAPERS)], PAPERS)
            except Exception as e:
                print(f"arXiv wider search failed: {e}")
        if not found and failed == len(searches):
            raise ValueError("Swarm couldn't reach arXiv just now. Try again in a minute.")
        if not found:
            raise ValueError("Swarm found no recent papers on this. Try a broader area.")
        reader.terms = terms_in(reader.terms, found)
        self.emit(
            {
                "type": "reader",
                "question": self.text,
                "field": reader.field,
                "level": reader.level,
                "hardware": reader.hardware,
                "terms": reader.terms,
                "queries": reader.queries,
            }
        )
        self.emit({"type": "papers", "papers": [p.meta() for p in found]})

        async def answer_first() -> None:
            # Runs alongside the reading, from abstracts alone, so the answer to the question asked comes first.
            if result := await answer(llm, reader, self.text, found):
                self.emit({"type": "answer", **result})

        answering = asyncio.create_task(answer_first())
        self.step("search", f"Found {len(found)} papers from the last six months", True)

        try:
            self.step("read", f"Reading {len(found)} papers at once")
            await arxiv.read(found)
            full = sum(p.source == "full text" for p in found)
            by_id = {p.id: p for p in found}

            async def one(paper):
                kept, proposed = await extract(llm, paper)
                self.emit(
                    {
                        "type": "read",
                        "paper_id": paper.id,
                        "source": paper.source,
                        "statements": len(kept),
                        "proposed": proposed,
                        "quotes": [s.quote for s in kept[:3]],
                        # Tokens so far in this run, for the page's live log.
                        "tokens": sum(u["input"] + u["output"] for u in llm.usage.values()),
                    }
                )
                return kept, proposed

            results = await asyncio.gather(*(one(p) for p in found))
            statements = [s for kept, _ in results for s in kept]
            proposed = sum(n for _, n in results)
            self.step("read", f"Read {len(found)} papers, {full} in full", True)

            self.step("group", "Finding problems more than one paper raises")
            if not statements:
                raise ValueError("These papers don't state open problems Swarm could quote. Try a broader area.")
            problems = await group(llm, statements, by_id, self.text)
            if not problems:
                raise ValueError("Swarm couldn't group what these papers say. Try again in a minute.")
            self.emit({"type": "problems", "problems": [p.to_dict() for p in problems]})
            self.step("group", f"Found {len(problems)} open problems", True)

            self.step("check", "Searching newer work on each problem and writing explanations")

            async def check() -> None:
                # Each problem gets its own arXiv search, so a fix published outside this run's papers still turns up.
                related = {}
                for p in problems:
                    try:
                        related[p.id] = await arxiv.search(p.query, 20) if p.query else []
                    except Exception as e:
                        print(f"arXiv search failed for {p.query!r}: {e}")
                await check_addressed(llm, problems, by_id, related)

            await asyncio.gather(check(), explain(llm, reader, problems, by_id), answering)
            # Problems a newer paper may already address move to the end, keeping their order otherwise.
            problems.sort(key=lambda p: p.addressed is not None)
            self.emit({"type": "problems", "problems": [p.to_dict() for p in problems]})
            self.step("check", "Checked newer work and explained", True)

            self.emit(
                {
                    "type": "done",
                    "started": int(self.created),
                    "seconds": round(time.perf_counter() - began, 1),
                    "papers": len(found),
                    "full_text": full,
                    "quotes_proposed": proposed,
                    "quotes_kept": len(statements),
                    "tokens": sum(u["input"] + u["output"] for u in llm.usage.values()),
                    "calls": {tier: u["calls"] for tier, u in llm.usage.items()},
                }
            )

        except Exception:
            # The answer to their question is still worth showing when the open problems can't be found.
            await answering
            raise


RUNS: dict[str, Run] = {}
