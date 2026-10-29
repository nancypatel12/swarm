"""Runs saved to disk, so a restart loses nothing and a shared link keeps working through judging.

A saved run is its events, which is all the page needs to replay it. Examples are saved runs checked into the repo
with a label, so anyone can see a finished result in one click without spending credits.
"""

import json
import os
import re
from pathlib import Path

DATA_DIR = Path(os.environ.get("SWARM_DATA_DIR", Path(__file__).resolve().parent.parent / "data"))
EXAMPLES_DIR = Path(__file__).resolve().parent.parent / "examples"
_ID = re.compile(r"^[0-9a-f]{12}$")


def save(run_id: str, text: str, created: float, events: list[dict]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    data = {"id": run_id, "input": text, "created": created, "events": events}
    tmp = DATA_DIR / f"{run_id}.json.tmp"
    tmp.write_text(json.dumps(data))
    # Written then renamed, so a crash mid-write never leaves half a run behind.
    tmp.replace(DATA_DIR / f"{run_id}.json")


def load(run_id: str) -> dict | None:
    # Run ids come from the address bar, so only well-formed ones ever touch the disk.
    if not _ID.match(run_id):
        return None
    for folder in (EXAMPLES_DIR, DATA_DIR):
        path = folder / f"{run_id}.json"
        if path.exists():
            return json.loads(path.read_text())
    return None


def saved() -> list[dict]:
    """Every saved run, without its events, for rebuilding the same-input cache after a restart."""
    if not DATA_DIR.exists():
        return []
    out = []
    for path in DATA_DIR.glob("*.json"):
        try:
            d = json.loads(path.read_text())
            out.append({"id": d["id"], "input": d["input"], "created": d["created"], "failed": _failed(d)})
        except (ValueError, KeyError):
            continue
    return out


def examples() -> list[dict]:
    if not EXAMPLES_DIR.exists():
        return []
    out = []
    for path in sorted(EXAMPLES_DIR.glob("*.json")):
        d = json.loads(path.read_text())
        out.append({"id": d["id"], "label": d.get("label") or d["input"][:60]})
    return out


def spend_ledger() -> dict:
    """Tokens spent today and in total, on disk, so a restart can't reset the budget."""
    path = DATA_DIR / "spend.json"
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return {"day": "", "today": 0, "total": 0}


def save_spend_ledger(ledger: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    tmp = DATA_DIR / "spend.json.tmp"
    tmp.write_text(json.dumps(ledger))
    tmp.replace(DATA_DIR / "spend.json")


def _failed(d: dict) -> bool:
    return any(e.get("type") == "error" for e in d.get("events", []))
