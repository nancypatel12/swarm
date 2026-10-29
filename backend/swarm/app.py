"""HTTP API for Swarm. Start a run, then follow it as a stream of server-sent events."""

import asyncio
import json
import os
import re
import time
from collections import deque

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from . import store
from .llm import spent_today, spent_total
from .runs import RUNS, Run

load_dotenv()

app = FastAPI(title="Swarm")
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("FRONTEND_ORIGINS", "http://localhost:3000").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)

MAX_INPUT = 2000
# A public demo spends real credits. A run costs about 130,000 tokens, so these defaults allow about 8 runs a day and
# about 150 in all, and one visitor can't use more than a few of them. The spend is kept on disk, so a restart
# doesn't reset it. SWARM_PAUSED turns off new runs at once; saved runs and examples keep working.
MAX_RUNS_PER_HOUR = int(os.environ.get("SWARM_MAX_RUNS_PER_HOUR", "6"))
RUNS_PER_VISITOR = int(os.environ.get("SWARM_RUNS_PER_VISITOR", "3"))
DAILY_TOKENS = int(os.environ.get("SWARM_DAILY_TOKENS", "1000000"))
TOTAL_TOKENS = int(os.environ.get("SWARM_TOTAL_TOKENS", "20000000"))
# Behind a proxy every request comes from the proxy, so the visitor's address is the last one it adds. Only trust
# that header when a proxy is really in front, or anyone could claim to be a new visitor.
TRUST_PROXY = os.environ.get("SWARM_TRUST_PROXY") == "1"
_visitors: dict[str, deque[float]] = {}
KEEP_RUNS = 50
CACHE_SECONDS = 24 * 3600
_recent: deque[float] = deque()
_by_input: dict[str, str] = {}


class NewRun(BaseModel):
    input: str


def input_key(text: str) -> str:
    """Case and spacing don't change what was asked, so they don't change the key."""
    return re.sub(r"\s+", " ", text.strip().lower())


def find_run(run_id: str) -> Run | None:
    if run := RUNS.get(run_id):
        return run
    data = store.load(run_id)
    return Run.from_saved(data) if data else None


def cached_run(key: str, now: float) -> Run | None:
    """The same question within a day returns the same run: it saves credits, and two different answers to one
    question would undermine both. Failed runs aren't reused."""
    run = find_run(_by_input.get(key, ""))
    if not run or now - run.created > CACHE_SECONDS or any(e["type"] == "error" for e in run.events):
        return None
    return run


def paused() -> bool:
    return os.environ.get("SWARM_PAUSED") == "1"


def accepting() -> bool:
    """Whether a new run could start right now, for the page's status line."""
    return not paused() and spent_total() < TOTAL_TOKENS and spent_today() < DAILY_TOKENS


def visitor(request: Request) -> str:
    if TRUST_PROXY:
        # Hosts behind Cloudflare, like Render, set this header themselves and drop any copy a visitor sends.
        if cloudflare := request.headers.get("cf-connecting-ip", "").strip():
            return cloudflare
        if forwarded := request.headers.get("x-forwarded-for", ""):
            return forwarded.split(",")[-1].strip()
    return request.client.host if request.client else "unknown"


def charge(now: float, who: str) -> None:
    """Checks every limit before a new run starts, cheapest to explain first. Cached answers never get here."""
    if paused():
        raise HTTPException(503, "New runs are paused. Open the example, or any saved link, which still work.")
    if spent_total() >= TOTAL_TOKENS:
        raise HTTPException(429, "Swarm has used its budget for the demo. Open the example, which still works.")
    if spent_today() >= DAILY_TOKENS:
        raise HTTPException(429, "Swarm has used today's budget. Open the example, or try again tomorrow.")
    mine = _visitors.setdefault(who, deque())
    while mine and now - mine[0] > 24 * 3600:
        mine.popleft()
    if len(mine) >= RUNS_PER_VISITOR:
        message = f"You've started {RUNS_PER_VISITOR} runs today. Open the example, or come back tomorrow."
        raise HTTPException(429, message)
    while _recent and now - _recent[0] > 3600:
        _recent.popleft()
    if len(_recent) >= MAX_RUNS_PER_HOUR:
        raise HTTPException(429, "Swarm is busy right now. Try again in a few minutes.")
    mine.append(now)
    _recent.append(now)


def forget_old_runs() -> None:
    """Finished runs are saved to disk, so memory only needs the newest ones."""
    for run_id, run in sorted(RUNS.items(), key=lambda kv: kv[1].created)[: max(0, len(RUNS) - KEEP_RUNS)]:
        if run.done:
            del RUNS[run_id]


def remember_saved_runs() -> None:
    """After a restart, the same question still returns the run it made before."""
    for r in sorted(store.saved(), key=lambda r: r["created"]):
        if not r["failed"] and time.time() - r["created"] <= CACHE_SECONDS:
            _by_input[input_key(r["input"])] = r["id"]


remember_saved_runs()


@app.get("/api/health")
def health():
    return {"ok": True, "accepting": accepting()}


@app.get("/api/examples")
def examples():
    return store.examples()


@app.post("/api/runs")
async def create_run(body: NewRun, request: Request):
    text = body.input.strip()[:MAX_INPUT]
    if len(text.split()) < 2:
        raise HTTPException(400, "Tell Swarm a little more, for example: diffusion models for audio.")
    key = input_key(text)
    if existing := cached_run(key, time.time()):
        return {"id": existing.id, "cached": True}
    charge(time.time(), visitor(request))
    forget_old_runs()
    run = Run(text)
    RUNS[run.id] = run
    _by_input[key] = run.id
    run.start()
    return {"id": run.id}


@app.get("/api/runs/{run_id}/events")
async def events(run_id: str):
    run = find_run(run_id)
    if not run:
        raise HTTPException(404, "This run has expired. Start a new one.")
    queue: asyncio.Queue = asyncio.Queue()

    async def stream():
        # Replay first, then follow live, so reconnecting never misses anything.
        backlog = list(run.events)
        run.listeners.add(queue)
        try:
            for e in backlog:
                yield f"data: {json.dumps(e)}\n\n"
            while not run.done or not queue.empty():
                try:
                    yield f"data: {json.dumps(await asyncio.wait_for(queue.get(), timeout=15))}\n\n"
                except TimeoutError:
                    yield ": keepalive\n\n"
        finally:
            run.listeners.discard(queue)

    return StreamingResponse(stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})
