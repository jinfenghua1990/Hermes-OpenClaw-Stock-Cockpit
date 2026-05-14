#!/usr/bin/env python3
"""
Phase-2.8C Runtime Replay Index

职责：
- 为 Runtime Replay Snapshot 建立时间索引
- 提供 Runtime Timeline 基础
- 后续支持 Replay Review / Runtime Audit

System Mode:
- PAPER_ONLY
- OBSERVE_ONLY
"""

import json
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
SNAPSHOT_DIR = BASE_DIR / "runtime_replay" / "snapshots"
OUT_FILE = BASE_DIR / "runtime_replay" / "runtime_replay_index.json"


def _load(path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return default if default is not None else {}


def build_runtime_replay_index():
    now = datetime.now().isoformat()
    items = []

    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

    for file in sorted(SNAPSHOT_DIR.glob("runtime_replay_*.json")):
        payload = _load(file, {})

        scheduler = payload.get("runtime", {}).get("scheduler", {})
        emotion = payload.get("runtime", {}).get("market_emotion", {})
        arbitration = payload.get("runtime", {}).get("ai_arbitration", {})

        items.append({
            "snapshot_file": file.name,
            "snapshot_id": payload.get("snapshot_id", file.stem),
            "generated_at": payload.get("generated_at", "UNKNOWN"),
            "scheduler_status": scheduler.get("final_status", "UNKNOWN"),
            "market_emotion": emotion.get("market_emotion", "UNKNOWN"),
            "arbitration_result": arbitration.get("arbitration_result", "UNKNOWN"),
        })

    payload = {
        "phase": "Phase-2.8C",
        "runtime_type": "runtime_replay_index",
        "system_mode": "PAPER_ONLY_OBSERVE_ONLY",
        "generated_at": now,
        "snapshot_count": len(items),
        "timeline": items,
        "governance_constraints": {
            "auto_trade": False,
            "auto_learning": False,
            "baseline_mutation": False,
        },
    }

    OUT_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Runtime Replay Index generated: snapshots={len(items)}")
    return payload


if __name__ == "__main__":
    build_runtime_replay_index()
