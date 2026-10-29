"""A stand-in for Nemotron and arXiv, used by tests and by local runs with SWARM_STAND_IN=1.

It returns well-formed answers about a dozen made-up papers, so the pipeline and the page can be checked with no
network and no cost. Nothing it returns is real, and it must never be shown as a result.
"""

import asyncio
import random
import re
from collections import defaultdict

from .papers import Paper

# Made-up papers. Each one's closing section states one or two unsolved problems in its own words.
CLOSINGS = {
    "long": "Generating coherent audio longer than one minute remains an open problem for diffusion models.",
    "metric": "Automatic metrics for generated music still correlate poorly with human listening judgments.",
    "speed": "Sampling is still too slow for real-time use on consumer hardware, which limits live applications.",
}
PAPERS = [
    ("2610.00001", "Long-form audio diffusion with memory", ["A. Rivera", "B. Okafor"], "2026-10-02", ["long"]),
    ("2610.00002", "Listening tests for music generation", ["C. Lindqvist"], "2026-09-28", ["metric"]),
    ("2609.00003", "Fast samplers for speech diffusion", ["D. Haddad", "E. Novak"], "2026-09-15", ["speed"]),
    ("2609.00004", "Hierarchical latents for song generation", ["F. Mensah", "A. Rivera"], "2026-09-03", ["long"]),
    ("2608.00005", "Benchmarking audio quality metrics", ["G. Sato", "H. Ibarra"], "2026-08-20", ["metric"]),
    ("2608.00006", "Distilled diffusion for sound effects", ["I. Kowalski"], "2026-08-11", ["speed", "long"]),
    ("2607.00007", "Text to ambience with diffusion", ["J. Adeyemi", "K. Brandt"], "2026-07-30", ["long"]),
    ("2607.00008", "On the evaluation of generated speech", ["L. Moreau"], "2026-07-14", ["metric", "speed"]),
    ("2606.00009", "Streaming diffusion for voice", ["M. Chen", "D. Haddad"], "2026-06-25", ["speed"]),
    ("2606.00010", "A survey of audio diffusion", ["N. Petrov"], "2026-06-09", []),
]
# A newer paper the run's own search misses and only the search for the long-audio problem finds.
LATER = Paper(
    id="2610.00011",
    title="Minute-long music with segment memory",
    authors=["O. Lindgren"],
    published="2026-10-20",
    abstract="We address coherent generation of audio longer than one minute with a memory of earlier segments.",
)


async def search(phrases: list[str], limit: int, months: int = 6) -> list[Paper]:
    await asyncio.sleep(0.2)
    if phrases[0].startswith("problem"):
        return [LATER] if "long" in phrases[0] else []
    return [
        Paper(id=pid, title=title, authors=authors, published=date, abstract=f"A study of {title}.")
        for pid, title, authors, date, _ in PAPERS[:limit]
    ]


async def read(papers: list[Paper]) -> None:
    await asyncio.sleep(0.3)
    topics = {pid: keys for pid, *_, keys in PAPERS}
    for p in papers:
        if found := " ".join(CLOSINGS[k] for k in topics.get(p.id, [])):
            p.text, p.source = f"## 6 Limitations\nOur results are encouraging. {found}", "full text"
        else:
            p.text = p.abstract


LABELS = {"long": "Long audio", "metric": "Metrics disagree with listeners", "speed": "Too slow for real time"}


class StandInLLM:
    def __init__(self) -> None:
        self.rng = random.Random(1)
        self.usage = defaultdict(lambda: {"calls": 0, "input": 0, "output": 0})
        self.models = dict.fromkeys(("nano", "super", "ultra"), "stand-in")

    async def json(self, tier: str, system: str, user: str, *, task: str, **_) -> dict:
        self.usage[tier]["calls"] += 1
        await asyncio.sleep(self.rng.uniform(0.05, 0.4) if task == "extract" else 0.1)
        if task == "reader":
            return {
                "is_research": True,
                "field": "diffusion models for audio",
                "broad": "audio diffusion",
                "terms": [
                    {"term": "Diffusion", "meaning": "Models that learn to turn noise into data step by step."},
                    {"term": "Sampler", "meaning": "The procedure that generates new audio from a trained model."},
                    # In no stand-in paper, so it must be dropped.
                    {"term": "Flux capacitor", "meaning": "Not a real term."},
                ],
                "queries": [["diffusion", "audio"], ["fast sampling"]],
                "level": "master's student",
                "hardware": "one GPU",
            }
        if task == "extract":
            text = user.split("<text>", 1)[1]
            found = [(k, s) for k, s in CLOSINGS.items() if s in text]
            # One invented quote per paper, which the word-for-word check must drop.
            invented = {"quote": "This sentence appears in no paper at all, anywhere.", "label": "Made up"}
            return {"statements": [{"quote": s, "label": LABELS[k]} for k, s in found] + [invented]}
        if task == "group":
            lines = re.findall(r"^(\d+)\. (.+)$", user, re.MULTILINE)
            groups = defaultdict(list)
            for n, label in lines:
                groups[label].append(int(n))
            return {
                "problems": [
                    {"title": label, "query": [f"problem {label.lower()}"], "lines": ns} for label, ns in groups.items()
                ]
            }
        if task == "members":
            return {"keep": [int(n) for n in re.findall(r"^(\d+)\. ", user, re.MULTILINE)]}
        if task == "addressed":
            match = re.search(r"\[(\S+)\] [^\n]+\n(We address [^\n]+)", user)
            if match and "Long audio" in user:
                return {"paper_id": match.group(1), "quote": match.group(2)}
            return {"paper_id": None, "quote": None}
        if task == "answer":
            ids = re.findall(r"^\[(\S+)\] ", user, re.MULTILINE)
            return {
                "answer": [
                    {"text": "Stand-in papers on long audio say it's still hard \u2014 for now.", "papers": ids[:2]},
                    # Cites a paper that isn't in the set, so it must be dropped.
                    {"text": "An invented claim.", "papers": ["0000.00000"]},
                ],
                "read_first": [{"paper_id": pid, "why": "A stand-in reason."} for pid in [*ids[:3], ids[0]]],
            }
        if task == "explain":
            ids = re.findall(r"^(p\d+): ", user, re.MULTILINE)
            return {
                "problems": [
                    {
                        "id": pid,
                        "explanation": "A stand-in explanation in plain words.",
                        "needs": "one GPU",
                        "first_step": "A stand-in first experiment.",
                    }
                    for pid in ids
                ]
            }
        raise ValueError(f"unknown task {task}")
