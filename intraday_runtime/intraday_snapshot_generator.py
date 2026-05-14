#!/usr/bin/env python3
"""
Phase-2.8C Intraday Snapshot Generator

每15分钟生成 intraday snapshot。
"""

import json
import uuid
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
OUT_DIR = BASE_DIR / "intraday_runtime" / "snapshots"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def _load(path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return default or {}


def generate_intraday_snapshot():
    now = datetime.now()
    today = now.strftime("%Y-%m-%d")
    slot = now.strftime("%H%M")

    runtime = _load(BASE_DIR / "intraday_runtime" / "intraday_runtime_status.json", {})
    position = _load(BASE_DIR / "position_runtime" / "position_runtime_summary.json", {})

    snapshot = {
        "phase": "Phase-2.8C",
        "snapshot_type": "intraday_runtime_snapshot",
        "snapshot_uuid": str(uuid.uuid4())[:8],
        "generated_at": now.isoformat(),
        "slot": slot,
        "runtime": runtime,
        "position_runtime": position,
        "paper_only_lock": True,
        "observe_only_lock": True,
    }

    out = OUT_DIR / f"{today}_{slot}.json"
    out.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")

    latest = OUT_DIR / "latest.json"
    latest.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"✅ Intraday Snapshot generated: {out}")
    return snapshot


if __name__ == "__main__":
    generate_intraday_snapshot()
