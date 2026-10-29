import asyncio
import re

import pytest

from swarm.papers import Paper
from swarm.problems import (
    _GENERIC,
    WRITING,
    NotResearch,
    Problem,
    Reader,
    Statement,
    answer,
    check_addressed,
    diverse,
    explain,
    extract,
    grounded_links,
    grounded_title,
    group,
    needs_for,
    phrases,
    plain,
    shared_claim,
    stock_ending_dropped,
    terms_in,
    understand,
)


class Reply:
    """Answers every model call with one fixed reply and remembers the prompts it saw."""

    def __init__(self, reply):
        self.reply = reply
        self.prompts = []

    async def json(self, tier, system, user, task="", **_):
        if task == "members":
            # The line check agrees with the grouping unless a test says otherwise.
            return {"keep": [int(n) for n in re.findall(r"^(\d+)\. ", user, re.MULTILINE)]}
        self.prompts.append((tier, user))
        self.system = system
        return self.reply


def run(coro):
    return asyncio.run(coro)


def paper(pid, authors=("A",), published="2026-09-01", text="", abstract=""):
    p = Paper(id=pid, title=f"Paper {pid}", authors=list(authors), published=published, abstract=abstract)
    p.text = text
    return p


def test_not_research_stops_the_run():
    with pytest.raises(NotResearch):
        run(understand(Reply({"is_research": False}), "hello there"))


def test_no_searches_means_nothing_to_research():
    with pytest.raises(NotResearch):
        run(understand(Reply({"is_research": True, "queries": []}), "do AI labelers grade outcomes"))


def test_terms_become_searches_when_none_are_usable():
    terms = [
        {"term": "Reinforcement Learning from Human Feedback (RLHF)", "meaning": "x"},
        {"term": "Process supervision", "meaning": "y"},
        {"term": "A term far too long to search for as one phrase", "meaning": "z"},
    ]
    r = run(understand(Reply({"queries": [["a phrase much longer than four words"]], "terms": terms}), "rlhf"))
    assert r.queries == [["RLHF"], ["Process supervision"]]


def test_plain_words_become_field_searches():
    llm = Reply(
        {
            "queries": [["process supervision", "reward model"], "outcome AND supervision", ['"a"'], ["b"]],
            "terms": [{"term": "Process supervision", "meaning": "Grading each step."}, {"meaning": "no term"}],
            "hardware": "a supercomputer",
        }
    )
    r = run(understand(llm, "do AI labelers grade decisions or outcomes"))
    assert r.queries == [["process supervision", "reward model"], ["outcome", "supervision"], ["a"]]
    assert r.terms == [{"term": "Process supervision", "meaning": "Grading each step."}]
    assert (r.hardware, r.level) == ("one GPU", "curious beginner")
    assert llm.prompts[0][0] == "super"


@pytest.mark.parametrize(
    ("raw", "out"),
    [
        (["process supervision", ' "reward  model" '], ["process supervision", "reward model"]),
        ("outcome AND supervision", ["outcome", "supervision"]),
        ("process supervision, reward model", ["process supervision", "reward model"]),
        (["far too many words in this one phrase", "ok"], ["ok"]),
        (["a", "b", "c", "d"], ["a", "b", "c"]),
        (["hallucination detection", "one GPU"], ["hallucination detection"]),
        (["GPU kernels", "lab automation"], ["GPU kernels", "lab automation"]),
        ([], []),
    ],
)
def test_searches_are_a_few_short_phrases(raw, out):
    assert phrases(raw) == out


def test_terms_not_in_any_paper_are_dropped():
    found = [paper("1", abstract="We study process supervision for math reasoning.")]
    terms = [{"term": "Process supervision", "meaning": "x"}, {"term": "Outcome hacking", "meaning": "y"}]
    assert [t["term"] for t in terms_in(terms, found)] == ["Process supervision"]


def test_extract_keeps_only_quotes_found_in_the_paper():
    p = paper("1", text="Real-time sampling on a laptop remains out of reach for now.")
    llm = Reply(
        {
            "statements": [
                {"quote": "Real-time sampling on a laptop remains out of reach", "label": "Too slow"},
                {"quote": "Nobody has tried this on music before at all", "label": "Made up"},
                {"quote": "Real-time sampling on a laptop remains out of reach", "label": ""},
            ]
        }
    )
    kept, proposed = run(extract(llm, p))
    assert [s.label for s in kept] == ["Too slow"] and proposed == 3
    # Paper text comes from the web, so it's marked as data.
    assert "<text>" in llm.prompts[0][1]


def test_groups_rank_by_independent_authors_and_ignore_bad_lines():
    papers = {
        "1": paper("1", ("A",)),
        "2": paper("2", ("A", "B")),  # same lab as paper 1
        "3": paper("3", ("C",)),
        "4": paper("4", ("D",)),
    }
    statements = [Statement(pid, f"quote {pid}", "same lab twice" if pid in "12" else "two labs") for pid in "1234"]
    llm = Reply(
        {
            "problems": [
                {"title": "same lab twice", "lines": [1, 2]},
                {"title": "two labs", "lines": [3, 4, 4, 99, "x"]},
                {"title": "", "lines": [1]},
            ]
        }
    )
    problems = run(group(llm, statements, papers))
    assert [(p.title, p.groups, len(p.statements)) for p in problems] == [("Two labs", 2, 2), ("Same lab twice", 1, 2)]
    assert [p.id for p in problems] == ["p1", "p2"]


def test_a_failed_question_read_says_so_plainly():
    class Broken:
        async def json(self, *a, **k):
            raise ValueError("reader: no valid JSON after 3 tries")

    with pytest.raises(ValueError, match="couldn't read your question"):
        run(understand(Broken(), "do AI labelers grade outcomes"))


def test_grouping_retries_with_one_statement_per_paper_and_reads_text_numbers():
    class FailsFirst:
        def __init__(self):
            self.sizes = []

        async def json(self, tier, system, user, task="", **_):
            if task == "members":
                return {"keep": [1, 2]}
            self.sizes.append(user.count("\n1. ") + user.count("\n2. ") + user.count("\n3. "))
            if len(self.sizes) == 1:
                raise ValueError("cut off")
            return {"problems": [{"title": "both papers", "lines": ["1", " 2 "]}]}

    papers = {"1": paper("1", ("A",)), "2": paper("2", ("B",))}
    a, b, c = "occlusion breaks tracking", "slow resets", "occlusion breaks depth"
    statements = [Statement("1", a, "x"), Statement("1", b, "x"), Statement("2", c, "x")]
    llm = FailsFirst()
    [p] = run(group(llm, statements, papers))
    assert [s.quote for s in p.statements] == [a, c] and p.groups == 2
    assert len(llm.sizes) == 2


def test_super_explains_when_ultra_fails():
    class UltraDown:
        def __init__(self):
            self.tiers = []

        async def json(self, tier, *a, **k):
            self.tiers.append(tier)
            if tier == "ultra":
                raise TimeoutError
            return {"problems": [{"id": "p1", "explanation": "Plain.", "needs": "one GPU", "first_step": "Try."}]}

    problems = [Problem("p1", "A", [Statement("1", "q", "A")])]
    llm = UltraDown()
    run(explain(llm, Reader("audio", [["audio"]], [], "beginner", "one GPU"), problems))
    assert llm.tiers == ["ultra", "super"] and problems[0].explanation == "Plain."


def test_catch_all_groups_are_dropped_and_the_question_is_given():
    papers = {str(i): paper(str(i), (f"author {i}",)) for i in range(20)}
    statements = [Statement(str(i), f"q{i}", "a specific problem") for i in range(20)]
    llm = Reply(
        {
            "problems": [
                {"title": "limitations", "lines": list(range(1, 14))},
                {"title": "a specific problem", "lines": [14, 15]},
            ]
        }
    )
    problems = run(group(llm, statements, papers, "do AI labelers grade outcomes?"))
    assert [p.title for p in problems] == ["A specific problem"]
    assert "do AI labelers grade outcomes?" in llm.prompts[0][1]


def test_a_title_must_share_a_word_with_its_quotes():
    s = [Statement("1", "Our theoretical results are agnostic to model scale.", "Untested at larger scale")]
    assert grounded_title("AI labelers grading decisions vs outcomes", s) == "Untested at larger scale"
    assert grounded_title("Results unverified at larger scale", s) == "Results unverified at larger scale"


def test_model_text_loses_its_dashes_but_keeps_its_words():
    assert plain("It works \u2014 mostly \u2014 on small models.") == "It works, mostly, on small models."
    assert plain(" Scores, \u2013 then ranks ") == "Scores, then ranks"


@pytest.mark.parametrize(
    ("step", "needs", "out"),
    [
        ("Replicate it on a 1-2B parameter model", "a lab", "one GPU"),
        ("Fine-tune a 7B model", "a lab", "one GPU"),
        ("Train a 70B model from scratch", "a lab", "a lab"),
        ("Read the paper and list its assumptions", "a lab", "a lab"),
        ("Fine-tune a 7B model", "a laptop", "a laptop"),
        ("Test the policy on a real robot arm with a new object", "one GPU", "a lab"),
        ("Record a scene with a depth camera", "a laptop", "a lab"),
        ("Simulate a physical robot arm in MuJoCo", "one GPU", "one GPU"),
    ],
)
def test_needs_agrees_with_the_first_step(step, needs, out):
    assert needs_for(step, needs) == out


def test_the_answer_cites_only_papers_in_the_set():
    found = [paper(str(i), abstract=f"Abstract {i}.") for i in range(20)]
    llm = Reply(
        {
            "answer": [
                {"text": "Most work grades outcomes \u2014 not steps.", "papers": ["1", "1", "2"]},
                {"text": "Made up.", "papers": ["99"]},
                {"text": "", "papers": ["3"]},
            ],
            "read_first": [{"paper_id": "2", "why": "Closest."}, {"paper_id": "2"}, {"paper_id": "19"}],
        }
    )
    result = run(answer(llm, Reader("rl", [["rl"]], [], "student", "one GPU"), "grade outcomes?", found))
    assert result["sentences"] == [{"text": "Most work grades outcomes, not steps.", "papers": ["1", "2"]}]
    # Only the 15 most relevant papers are given, so paper 19 can't be picked.
    assert result["read_first"] == [{"paper_id": "2", "why": "Closest."}]
    assert llm.prompts[0][0] == "ultra" and WRITING in llm.system


def test_the_answer_falls_back_to_super_and_can_be_empty():
    class UltraDown:
        def __init__(self):
            self.tiers = []

        async def json(self, tier, *a, **k):
            self.tiers.append(tier)
            if tier == "ultra":
                raise TimeoutError
            return {"answer": [], "read_first": []}

    llm = UltraDown()
    assert run(answer(llm, Reader("rl", [["rl"]], [], "student", "one GPU"), "q", [paper("1")])) is None
    assert llm.tiers == ["ultra", "super"]


def test_a_failed_grouping_call_finds_nothing_rather_than_crashing():
    class Broken:
        async def json(self, *a, **k):
            raise ValueError("group: no valid JSON after 3 tries")

    assert run(group(Broken(), [Statement("1", "q", "x")], {"1": paper("1")})) == []


def test_addressed_needs_a_real_quote_from_a_newer_paper():
    papers = {
        "old": paper("old", published="2026-07-01"),
        "new": paper("new", published="2026-10-01", abstract="We solve long audio generation with memory."),
    }
    problem = Problem("p1", "Long audio", [Statement("old", "q", "Long audio")])
    claim = "We solve long audio generation with memory."
    run(check_addressed(Reply({"paper_id": "new", "quote": claim}), [problem], papers))
    assert problem.addressed == {"paper": papers["new"].meta(), "quote": claim}

    problem.addressed = None
    invented = {"paper_id": "new", "quote": "We fully solve every audio problem forever."}
    run(check_addressed(Reply(invented), [problem], papers))
    assert problem.addressed is None


def test_a_paper_never_addresses_its_own_problem():
    papers = {"old": paper("old", published="2026-10-01", abstract="We solve long audio generation with memory.")}
    problem = Problem("p1", "Long audio", [Statement("old", "q", "Long audio")])
    llm = Reply({"paper_id": "old", "quote": "We solve long audio generation with memory."})
    run(check_addressed(llm, [problem], papers))
    assert problem.addressed is None and not llm.prompts


def test_a_newer_paper_from_the_problems_own_search_counts():
    papers = {"old": paper("old", published="2026-07-01")}
    outside = paper("outside", published="2026-10-01", abstract="We solve long audio generation with memory.")
    problem = Problem("p1", "Long audio", [Statement("old", "q", "Long audio")])
    llm = Reply({"paper_id": "outside", "quote": "We solve long audio generation with memory."})
    run(check_addressed(llm, [problem], papers, {"p1": [outside]}))
    assert problem.addressed["paper"]["id"] == "outside"
    assert problem.addressed["paper"]["url"] == "https://arxiv.org/abs/outside"


def test_explanations_use_ultra_and_known_hardware_only():
    problems = [Problem("p1", "A", [Statement("1", "q one", "A")]), Problem("p2", "B", [Statement("1", "q two", "B")])]
    llm = Reply(
        {
            "problems": [
                {"id": "p1", "explanation": "Plain words.", "needs": "a laptop", "first_step": "Try X."},
                {"id": "p2", "explanation": "More words.", "needs": "a quantum computer", "first_step": "Try Y."},
            ]
        }
    )
    run(explain(llm, Reader("audio", ["audio"], [], "beginner", "a laptop"), problems))
    assert (problems[0].needs, problems[1].needs) == ("a laptop", "")
    assert problems[0].first_step == "Try X." and llm.prompts[0][0] == "ultra"


def test_first_steps_name_only_real_papers_and_real_expansions():
    rlhf = "Reinforcement Learning from Human Feedback"
    real = paper("1", text="We propose S2T-RLHF for stable training.", abstract=rlhf)
    real.title = "S2T-RLHF: Hierarchical Credit Assignment for Stable Preference-Based RLHF"
    problems = [Problem("p1", "A", [Statement("1", "reward decomposition does not eliminate instability", "A")])]
    llm = Reply(
        {
            "problems": [
                {
                    "id": "p1",
                    "explanation": f"S2T-RLHF (Step-to-Sequence RLHF) uses RLHF ({rlhf}).",
                    "first_step": 'Start from the paper "Reward Decomposition for RLHF Stability" and flip rewards.',
                    "needs": "one GPU",
                }
            ]
        }
    )
    run(explain(llm, Reader("rlhf", [["rlhf"]], [], "beginner", "one GPU"), problems, {"1": real}))
    assert problems[0].first_step == f'Start from the paper "{real.title}" and flip rewards.'
    assert problems[0].explanation == f"S2T-RLHF uses RLHF ({rlhf})."
    assert real.title in llm.prompts[0][1]


class Checker:
    """Groups every line together, then lets the line check keep only some, or fail."""

    def __init__(self, keep):
        self.keep = keep

    async def json(self, tier, system, user, task="", **_):
        if task == "members":
            if self.keep is None:
                raise TimeoutError
            return {"claim": "keypoint tracking fails under occlusion.", "keep": self.keep}
        return {"problems": [{"title": "Tracking fails under occlusion", "lines": [1, 2, 3]}]}


def lab_papers():
    return {str(i): paper(str(i), (f"author {i}",)) for i in range(3)}


def lab_lines():
    return [
        Statement("0", "tracking fails under severe occlusion", "a"),
        Statement("1", "keypoints degrade under occlusions", "b"),
        Statement("2", "shorter proofs cost retention", "c"),
    ]


def test_lines_that_dont_state_the_problem_leave_the_group_and_stop_counting():
    [problem] = run(group(Checker([1, 2]), lab_lines(), lab_papers()))
    assert [s.paper_id for s in problem.statements] == ["0", "1"]
    assert problem.groups == 2
    # Trimmed, the group is retitled with the claim the check named.
    assert problem.title == "Keypoint tracking fails under occlusion"


def test_a_failed_line_check_keeps_one_paper_so_agreement_is_never_unchecked():
    [problem] = run(group(Checker(None), lab_lines(), lab_papers()))
    assert [s.paper_id for s in problem.statements] == ["0"]
    assert problem.groups == 1


def test_lines_from_another_paper_need_a_specific_word_in_common():
    merged = [
        Statement("1", "existing VLMs do not yet produce the fine-grained, action-level critiques we need", "a"),
        Statement("2", "Diagnostics characterize behavior without a causal mechanism for grounding failure.", "b"),
    ]
    assert [s.paper_id for s in shared_claim(merged)] == ["1"]
    agree = [
        Statement("3", "keypoint annotations do not account for depth or occlusion", "c"),
        Statement("4", "keypoint policies degrade faster under occlusions than RGB-based policies", "d"),
    ]
    assert [s.paper_id for s in shared_claim(agree)] == ["3", "4"]


def test_first_steps_keep_only_the_papers_own_code_links():
    links = {"https://github.com/lab/poil"}
    step = "Clone https://github.com/lab/poil and compare with https://github.com/made/up."
    assert grounded_links(step, links) == "Clone https://github.com/lab/poil and compare with."


def test_the_stock_closing_sentence_goes_when_enough_is_left():
    three = "Tracking breaks under occlusion. Depth fails on glass. Solving this would let robots work in kitchens."
    assert stock_ending_dropped(three) == "Tracking breaks under occlusion. Depth fails on glass."
    two = "Tracking breaks under occlusion. Solving this would let robots work in kitchens."
    assert stock_ending_dropped(two) == two


def test_scale_and_compute_limits_never_become_problems():
    papers = {str(i): paper(str(i), (f"author {i}",)) for i in range(2)}
    statements = [
        Statement("0", "generalization across larger backbones remain important directions for future work", "x"),
        Statement("1", "the judge fails on some bias types and works on others", "y"),
    ]
    llm = Reply({"problems": [{"title": "judge fails on bias types", "lines": [1]}]})
    run(group(llm, statements, papers))
    # Only the bias line, labeled "y", reaches the model; the scale line is gone before the call.
    assert "1. y" in llm.prompts[0][1] and "2. " not in llm.prompts[0][1] and "1. x" not in llm.prompts[0][1]


@pytest.mark.parametrize(
    "quote, generic",
    [
        (
            "it remains an open question how well the approach generalizes to more complex and dynamic real-world "
            "robotic settings.",
            True,
        ),
        ("whether the method generalizes to other domains is left for future work", True),
        (
            "generalization to diverse platforms including bimanual and mobile robots, to diverse conditions",
            True,
        ),
        (
            "the evaluation relies on a fixed prompting setup, and results may vary under other prompts",
            True,
        ),
        (
            "although the dataset is carefully curated, its size remains moderate compared to large-scale benchmarks",
            True,
        ),
        ("the system's performance on other scientific domains (e.g., biomedical, legal) remains unvalidated.", True),
        ("self-reported confidence is poorly aligned with factual truthfulness", False),
        ("the policy fails to generalize to unseen object poses and lighting", False),
        ("tracking breaks on transparent or specular surfaces", False),
    ],
)
def test_vague_generalization_limits_are_generic_and_named_settings_are_not(quote, generic):
    assert bool(_GENERIC.search(quote)) is generic


def test_one_paper_cannot_fill_the_list():
    def problem(title, *paper_groups):
        return Problem("", title, [Statement(pid, "q", title) for pid in paper_groups], groups=len(set(paper_groups)))

    ranked = [
        problem("two labs", "1", "2"),
        problem("lab one again", "1"),
        problem("another of lab one", "1"),
        problem("lab three", "3"),
        problem("labs one and four", "1", "4"),
    ]
    assert [p.title for p in diverse(ranked, 3)] == ["two labs", "lab three", "labs one and four"]
