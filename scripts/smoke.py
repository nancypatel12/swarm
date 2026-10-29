"""Smoke test: confirm both API keys work and list the NVIDIA models Token Factory serves."""

import os
import sys

from dotenv import load_dotenv
from openai import OpenAI
from tavily import TavilyClient

load_dotenv()

BASE_URL = "https://api.tokenfactory.nebius.com/v1/"


def check_nebius() -> bool:
    key = os.getenv("NEBIUS_API_KEY")
    if not key:
        print("NEBIUS_API_KEY is empty in .env")
        return False
    client = OpenAI(base_url=BASE_URL, api_key=key)
    try:
        models = [m.id for m in client.models.list().data]
    except Exception as e:
        print(f"Nebius: listing models failed: {e}")
        return False

    nvidia = sorted(m for m in models if "nvidia" in m.lower() or "nemotron" in m.lower())
    print(f"Nebius: {len(models)} models available, {len(nvidia)} from NVIDIA:")
    for m in nvidia:
        print(f"  {m}")
    if not nvidia:
        return False

    # One tiny completion proves billing works, not just auth.
    model = nvidia[0]
    try:
        r = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "Reply with the single word: ready"}],
            max_tokens=20,
        )
        print(f"Nebius: {model} replied: {r.choices[0].message.content!r}")
    except Exception as e:
        print(f"Nebius: completion with {model} failed: {e}")
        return False
    return True


def check_tavily() -> bool:
    key = os.getenv("TAVILY_API_KEY")
    if not key:
        print("TAVILY_API_KEY is empty in .env")
        return False
    try:
        r = TavilyClient(api_key=key).search("meal kit subscription customer complaints", max_results=3)
    except Exception as e:
        print(f"Tavily: search failed: {e}")
        return False
    print(f"Tavily: {len(r.get('results', []))} results, e.g. {r['results'][0]['url'] if r.get('results') else 'none'}")
    return True


if __name__ == "__main__":
    ok = check_nebius() & check_tavily()
    sys.exit(0 if ok else 1)
