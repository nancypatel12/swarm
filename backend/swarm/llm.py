"""Nemotron on Nebius Token Factory: JSON-only chat calls with retries, a concurrency cap and usage counts."""

import asyncio
import json
import os
import re
import time
from collections import defaultdict
from typing import Any

from openai import AsyncOpenAI

from . import store

BASE_URL = "https://api.tokenfactory.nebius.com/v1/"

# Each job goes to the model that does it well within this account's limits: Super translates the question and
# reads every paper at once, Ultra explains. Super does the many parallel calls because the account allows it 1,000
# requests a minute against Nano's 100: in a test, 1,000 Super calls finished in 25.7 s with no errors, while 1,000
# Nano calls hit the limit and took over 5 minutes.
TIER_ENV = {"nano": "NEMOTRON_NANO", "super": "NEMOTRON_SUPER", "ultra": "NEMOTRON_ULTRA"}

THINKING_TOKENS = 3000

_THINK = re.compile(r"<think>.*?</think>", re.DOTALL)


def parse_json(text: str) -> Any:
    """Pull the first JSON object or array out of a reply, ignoring reasoning blocks and code fences."""
    text = _THINK.sub("", text)
    starts = [i for i in (text.find("{"), text.find("[")) if i >= 0]
    if not starts:
        raise ValueError(f"no JSON in reply: {text[:200]!r}")
    value, _ = json.JSONDecoder().raw_decode(text[min(starts) :])
    return value


_limits: dict[asyncio.AbstractEventLoop, asyncio.Semaphore] = {}


def _today() -> str:
    return time.strftime("%Y-%m-%d", time.gmtime())


def spend(tokens: int) -> None:
    """Every call's tokens go into the ledger on disk, today's and the total, so a public demo can stop before it
    drains the account, even across restarts."""
    ledger = store.spend_ledger()
    if ledger.get("day") != _today():
        ledger.update(day=_today(), today=0)
    ledger["today"] = ledger.get("today", 0) + tokens
    ledger["total"] = ledger.get("total", 0) + tokens
    store.save_spend_ledger(ledger)


def spent_today() -> int:
    ledger = store.spend_ledger()
    return ledger.get("today", 0) if ledger.get("day") == _today() else 0


def spent_total() -> int:
    return store.spend_ledger().get("total", 0)


def shared_limit() -> asyncio.Semaphore:
    """One cap on calls in flight for every run on this server, so two people running Swarm at once share the
    account's rate limit instead of both tripping it. Kept per event loop, since a semaphore belongs to one loop."""
    loop = asyncio.get_running_loop()
    if loop not in _limits:
        _limits[loop] = asyncio.Semaphore(int(os.environ.get("SWARM_CONCURRENCY", "64")))
    return _limits[loop]


class LLM:
    def __init__(self) -> None:
        self.client = AsyncOpenAI(base_url=BASE_URL, api_key=os.environ["NEBIUS_API_KEY"], max_retries=3)
        self.models = {tier: os.environ.get(env, "") for tier, env in TIER_ENV.items()}
        missing = [TIER_ENV[t] for t, m in self.models.items() if not m]
        if missing:
            raise RuntimeError(f"Set {', '.join(missing)} in .env. Run scripts/smoke.py to list model ids.")
        self.limit = shared_limit()
        self.usage: dict[str, dict[str, int]] = defaultdict(lambda: {"calls": 0, "input": 0, "output": 0})

    async def json(
        self,
        tier: str,
        system: str,
        user: str,
        *,
        task: str,
        max_tokens: int = 800,
        temperature: float = 0.7,
        think: bool = True,
    ) -> Any:
        """max_tokens is the answer's budget. Nemotron 3 reasons first in a separate field, so thinking calls get
        extra room; turning thinking off cut one short structured answer from 226 tokens to 53 in a test."""
        extra = {} if think else {"extra_body": {"chat_template_kwargs": {"enable_thinking": False}}}
        last_error: Exception | None = None
        for _ in range(3):
            async with self.limit:
                r = await self.client.chat.completions.create(
                    model=self.models[tier],
                    messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
                    max_tokens=max_tokens + (THINKING_TOKENS if think else 0),
                    temperature=temperature,
                    **extra,
                )
            u = self.usage[tier]
            u["calls"] += 1
            if r.usage:
                u["input"] += r.usage.prompt_tokens
                u["output"] += r.usage.completion_tokens
                spend(r.usage.prompt_tokens + r.usage.completion_tokens)
            try:
                return parse_json(r.choices[0].message.content or "")
            except ValueError as e:
                last_error = e
        raise ValueError(f"{task}: no valid JSON after 3 tries ({last_error})")


def get_llm():
    # The stand-in exists only so the pipeline can be tested without a key. It is never on by default.
    if os.environ.get("SWARM_STAND_IN") == "1":
        from .stand_in import StandInLLM

        return StandInLLM()
    return LLM()
