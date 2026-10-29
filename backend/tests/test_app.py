import json
import time

import pytest
from fastapi.testclient import TestClient

from swarm import app, llm, runs, stand_in, store


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("SWARM_STAND_IN", "1")
    monkeypatch.setattr(runs.arxiv, "search", stand_in.search)
    monkeypatch.setattr(runs.arxiv, "read", stand_in.read)
    app._recent.clear()
    app._visitors.clear()
    app._by_input.clear()
    runs.RUNS.clear()
    with TestClient(app.app) as c:
        yield c


def follow(client, run_id) -> list[dict]:
    with client.stream("GET", f"/api/runs/{run_id}/events") as r:
        return [json.loads(line[6:]) for line in r.iter_lines() if line.startswith("data: ")]


def test_a_full_run_on_the_stand_in(client):
    run_id = client.post("/api/runs", json={"input": "diffusion models for audio, I have one GPU"}).json()["id"]
    events = follow(client, run_id)
    types = [e["type"] for e in events]
    assert "error" not in types, [e for e in events if e["type"] == "error"]
    # Two searches return the same papers; each is read once, and its kept quotes come with it.
    assert types.count("read") == len(stand_in.PAPERS)
    reads = [e for e in events if e["type"] == "read"]
    assert all(len(e["quotes"]) == e["statements"] for e in reads if e["statements"] <= 3)
    # Every paper had one invented quote, which the check threw out; the live log shows both counts.
    assert all(e["proposed"] == e["statements"] + 1 for e in reads)
    assert all(p["abstract"] for p in next(e for e in events if e["type"] == "papers")["papers"])
    terms = next(e for e in events if e["type"] == "reader")["terms"]
    assert [t["term"] for t in terms] == ["Diffusion", "Sampler"]

    problems = [e for e in events if e["type"] == "problems"][-1]["problems"]
    titles = [p["title"] for p in problems]
    assert "Made up" not in titles and set(titles) == {
        "Long audio",
        "Metrics disagree with listeners",
        "Too slow for real time",
    }
    # Every quote shown is in its paper; the invented one per paper was dropped.
    done = next(e for e in events if e["type"] == "done")
    assert done["quotes_proposed"] - done["quotes_kept"] == len(stand_in.PAPERS)
    # Rivera wrote two of the long-audio papers, so four papers make three independent groups.
    long = next(p for p in problems if p["title"] == "Long audio")
    assert len(long["papers"]) == 4 and long["groups"] == 3
    # Only the long-audio problem's own search finds the newer paper, and that moves the problem to the end.
    assert "2610.00011" not in [p["id"] for p in next(e for e in events if e["type"] == "papers")["papers"]]
    assert long["addressed"]["paper"]["id"] == "2610.00011" and problems[-1] is long
    assert all(p["addressed"] is None for p in problems[:-1])
    assert all(p["explanation"] and p["needs"] and p["first_step"] for p in problems)
    # The answer to the question cites only papers from the run, without dashes, and repeats no paper to read.
    ans = next(e for e in events if e["type"] == "answer")
    ids = {p["id"] for p in next(e for e in events if e["type"] == "papers")["papers"]}
    assert [s["text"] for s in ans["sentences"]] == ["Stand-in papers on long audio say it's still hard, for now."]
    assert len(ans["read_first"]) == 3 and {r["paper_id"] for r in ans["read_first"]} <= ids

    # Saved, so it replays after a restart, and the same question returns the same run.
    runs.RUNS.clear()
    assert follow(client, run_id) == events
    assert client.post("/api/runs", json={"input": "Diffusion  models for audio, I have one GPU"}).json() == {
        "id": run_id,
        "cached": True,
    }


def test_one_failed_search_does_not_sink_the_run(client, monkeypatch):
    async def flaky(phrases, limit, months=6):
        if phrases == ["fast sampling"]:
            raise TimeoutError
        return await stand_in.search(phrases, limit, months)

    monkeypatch.setattr(runs.arxiv, "search", flaky)
    run_id = client.post("/api/runs", json={"input": "diffusion for audio, again"}).json()["id"]
    events = follow(client, run_id)
    assert "error" not in [e["type"] for e in events] and events[-1]["type"] == "done"


def test_a_search_that_finds_nothing_tries_each_phrase(client, monkeypatch):
    asked = []

    async def strict(phrases, limit, months=6):
        asked.append(phrases)
        return [] if len(phrases) > 1 else await stand_in.search(phrases, limit, months)

    monkeypatch.setattr(runs.arxiv, "search", strict)
    run_id = client.post("/api/runs", json={"input": "diffusion for audio, strict"}).json()["id"]
    events = follow(client, run_id)
    assert events[-1]["type"] == "done"
    assert asked[:3] == [["diffusion", "audio"], ["diffusion"], ["audio"]]
    # Each key term also gets its own search, unless a search already uses it.
    assert ["Sampler"] in asked and ["Diffusion"] not in asked
    labels = [e["label"] for e in events if e["type"] == "step" and e["id"] == "search"]
    assert "\u201cdiffusion\u201d" in labels[0] and "\u201cfast sampling\u201d" in labels[0]


def test_too_few_papers_widen_the_search_to_the_fields_name(client, monkeypatch):
    asked = []

    async def narrow(phrases, limit, months=6):
        asked.append(phrases)
        found = await stand_in.search(phrases, limit, months)
        return found if phrases == ["audio diffusion"] else found[:1]

    monkeypatch.setattr(runs.arxiv, "search", narrow)
    run_id = client.post("/api/runs", json={"input": "diffusion for audio, narrow"}).json()["id"]
    events = follow(client, run_id)
    assert events[-1]["type"] == "done"
    assert asked.count(["audio diffusion"]) == 1
    found = next(e for e in events if e["type"] == "papers")["papers"]
    assert len(found) > 1


def test_the_answer_survives_when_no_problems_are_found(client, monkeypatch):
    async def nothing(llm, paper):
        return [], 0

    monkeypatch.setattr(runs, "extract", nothing)
    run_id = client.post("/api/runs", json={"input": "diffusion for audio, nothing open"}).json()["id"]
    types = [e["type"] for e in follow(client, run_id)]
    assert "answer" in types and types[-1] == "error"


def test_too_short_input_is_refused(client):
    assert client.post("/api/runs", json={"input": "audio"}).status_code == 400


def test_runs_per_hour_are_capped(client, monkeypatch):
    monkeypatch.setattr(app, "MAX_RUNS_PER_HOUR", 1)
    monkeypatch.setattr(app, "RUNS_PER_VISITOR", 10)
    assert client.post("/api/runs", json={"input": "audio diffusion"}).status_code == 200
    r = client.post("/api/runs", json={"input": "speech recognition"})
    assert r.status_code == 429 and "busy" in r.json()["detail"]


def test_daily_budget_stops_new_runs(client, monkeypatch):
    monkeypatch.setattr(app, "spent_today", lambda: app.DAILY_TOKENS)
    r = client.post("/api/runs", json={"input": "audio diffusion"})
    assert r.status_code == 429 and "today's budget" in r.json()["detail"]


def test_failed_runs_are_not_reused(client):
    store.save("aaaaaaaaaaaa", "audio diffusion", time.time(), [{"type": "error", "message": "x"}])
    app._by_input[app.input_key("audio diffusion")] = "aaaaaaaaaaaa"
    assert app.cached_run(app.input_key("audio diffusion"), time.time()) is None


def test_unknown_or_malformed_runs_are_not_found(client):
    assert client.get("/api/runs/bbbbbbbbbbbb/events").status_code == 404
    assert store.load("../../etc/passwd") is None


def test_examples_are_listed(client, monkeypatch, tmp_path):
    monkeypatch.setattr(store, "EXAMPLES_DIR", tmp_path)
    (tmp_path / "cccccccccccc.json").write_text(json.dumps({"id": "cccccccccccc", "input": "x", "label": "Audio"}))
    assert client.get("/api/examples").json() == [{"id": "cccccccccccc", "label": "Audio"}]


def test_spend_is_kept_on_disk_across_restarts():
    llm.spend(1000)
    llm.spend(500)
    assert (llm.spent_today(), llm.spent_total()) == (1500, 1500)
    # A new day starts today's count over, but never the total.
    ledger = store.spend_ledger()
    store.save_spend_ledger({**ledger, "day": "2026-01-01"})
    llm.spend(100)
    assert (llm.spent_today(), llm.spent_total()) == (100, 1600)


def test_the_total_budget_stops_new_runs_but_not_the_example(client, monkeypatch):
    monkeypatch.setattr(app, "TOTAL_TOKENS", 1000)
    llm.spend(1000)
    r = client.post("/api/runs", json={"input": "audio diffusion"})
    assert r.status_code == 429 and "budget for the demo" in r.json()["detail"]
    assert client.get("/api/health").json() == {"ok": True, "accepting": False}


def test_one_visitor_gets_a_few_runs_a_day_and_repeats_are_free(client, monkeypatch):
    monkeypatch.setattr(app, "RUNS_PER_VISITOR", 2)
    for text in ("audio diffusion", "speech recognition", "audio diffusion"):
        assert client.post("/api/runs", json={"input": text}).status_code == 200
    r = client.post("/api/runs", json={"input": "image segmentation"})
    assert r.status_code == 429 and "2 runs today" in r.json()["detail"]


def test_visitors_behind_a_proxy_are_told_apart_only_when_the_proxy_is_trusted(client, monkeypatch):
    monkeypatch.setattr(app, "RUNS_PER_VISITOR", 1)
    monkeypatch.setattr(app, "TRUST_PROXY", True)
    for n, text in enumerate(("audio diffusion", "speech recognition")):
        headers = {"x-forwarded-for": f"1.1.1.1, 10.0.0.{n}"}
        assert client.post("/api/runs", json={"input": text}, headers=headers).status_code == 200


def test_the_pause_switch_stops_new_runs_at_once(client, monkeypatch):
    monkeypatch.setenv("SWARM_PAUSED", "1")
    r = client.post("/api/runs", json={"input": "audio diffusion"})
    assert r.status_code == 503 and "paused" in r.json()["detail"]
    assert client.get("/api/health").json()["accepting"] is False


def test_behind_cloudflare_the_visitor_is_the_address_cloudflare_saw(client, monkeypatch):
    monkeypatch.setattr(app, "RUNS_PER_VISITOR", 1)
    monkeypatch.setattr(app, "TRUST_PROXY", True)
    same_proxy = {"x-forwarded-for": "10.0.0.1"}
    for n, text in enumerate(("audio diffusion", "speech recognition")):
        headers = {**same_proxy, "cf-connecting-ip": f"203.0.113.{n}"}
        assert client.post("/api/runs", json={"input": text}, headers=headers).status_code == 200
    headers = {**same_proxy, "cf-connecting-ip": "203.0.113.0"}
    assert client.post("/api/runs", json={"input": "image segmentation"}, headers=headers).status_code == 429
