"""Speed test: fire N short structured calls concurrently and report time, latency, tokens and errors.

This is the test behind the model choice in the README: Super handled 1,000 concurrent calls, Nano hit its limit.

Usage: python scripts/speedtest.py --model <model-id> --n 100 --concurrency 50
"""

import argparse
import asyncio
import os
import statistics
import time

from dotenv import load_dotenv
from openai import AsyncOpenAI

load_dotenv()

BASE_URL = "https://api.tokenfactory.nebius.com/v1/"

# A short prompt with a short JSON answer, kept as it was when the README's numbers were measured.
PROMPT = """You are Maya, 34, a nurse in Ohio who cooks on weekends and hates food waste.
Read this pitch and decide if you would buy.

Pitch: "FreshBox delivers pre-portioned ingredients for 3 dinners a week, $59/week."

Answer as JSON only: {"decision": "buy" | "maybe" | "bounce", "reason": "<one sentence>"}"""


async def one_call(client, model, sem, results, extra):
    async with sem:
        start = time.perf_counter()
        try:
            r = await client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": PROMPT}],
                max_tokens=250,
                **extra,
            )
            results.append(
                {
                    "ok": True,
                    "latency": time.perf_counter() - start,
                    "in": r.usage.prompt_tokens if r.usage else 0,
                    "out": r.usage.completion_tokens if r.usage else 0,
                }
            )
        except Exception as e:
            results.append({"ok": False, "latency": time.perf_counter() - start, "error": str(e)[:200]})


async def main(model, n, concurrency, think):
    client = AsyncOpenAI(base_url=BASE_URL, api_key=os.environ["NEBIUS_API_KEY"], max_retries=2)
    sem = asyncio.Semaphore(concurrency)
    results = []
    start = time.perf_counter()
    # Matches the swarm: decisions run with Nemotron thinking off.
    extra = {} if think else {"extra_body": {"chat_template_kwargs": {"enable_thinking": False}}}
    await asyncio.gather(*(one_call(client, model, sem, results, extra) for _ in range(n)))
    wall = time.perf_counter() - start

    ok = [r for r in results if r["ok"]]
    errors = [r for r in results if not r["ok"]]
    print(f"model={model} n={n} concurrency={concurrency} think={think}")
    print(f"wall time: {wall:.1f}s  ({len(ok) / wall:.1f} successful calls/s)")
    print(f"success: {len(ok)}/{n}  errors: {len(errors)}")
    if ok:
        lat = sorted(r["latency"] for r in ok)
        print(f"latency p50={statistics.median(lat):.2f}s p95={lat[int(len(lat) * 0.95) - 1]:.2f}s")
        print(f"tokens: {sum(r['in'] for r in ok)} in, {sum(r['out'] for r in ok)} out")
    for e in {r["error"] for r in errors}:
        print(f"  error: {e}")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--model", required=True)
    p.add_argument("--n", type=int, default=100)
    p.add_argument("--concurrency", type=int, default=50)
    p.add_argument("--think", action="store_true")
    a = p.parse_args()
    asyncio.run(main(a.model, a.n, a.concurrency, a.think))
