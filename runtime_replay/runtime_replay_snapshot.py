#!/usr/bin/env python3
"""
Phase-2.8C Runtime Replay Snapshot

职责：
- 保存每一次盘中 Runtime 的快照
- 为后续 Runtime Replay / Governance Review 提供时间序列基础

System Mode:
- PAPER_ONLY
- OBSERVE_ONLY
"""

import json
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
REPLAY_DIR = BASE_DIR / "runtime_replay" / "snapshots"
LATEST_FILE = BASE_DIR / "runtime_replay" / "latest_runtime_replay_snapshot.json"

SOURCE_FILES = {
    "scheduler": BASE_DIR / "logs" / "runtime_scheduler_log.json",
    "sector_runtime": BASE_DIR / "runtime_data" / "sector_runtime.json",
    "market_emotion": BASE_DIR / "runtime_data" / "market_emotion_runtime.json",
    "ai_arbitration": BASE_DIR / "runtime_data" / "ai_arbitration_runtime.json",
    "structure_runtime": BASE_DIR / "intraday_runtime" / "realtime_structure_runtime.json",
    "feishu_router": BASE_DIR / "runtime_data" / "intraday_feishu_router.json",
}


def _load(path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return default if default is not None else {}


def build_replay_snapshot():
    now = datetime.now()
    stamp = now.strftime("%Y%m%d_%H%M%S")

    payload = {
        "phase": "Phase-2.8C",
        "runtime_type": "runtime_replay_snapshot",
        "system_mode": "PAPER_ONLY_OBSERVE_ONLY",
        "generated_at": now.isoformat(),
        "snapshot_id": stamp,
        "sources": {},
        "runtime": {},
        "governance": {
            "auto_trade": False,
            "auto_learning": False,
            "baseline_mutation": False,
        },
    }

    for name, path in SOURCE_FILES.items():
        payload["sources"][name] = str(path)
        payload["runtime"][name] = _load(path, {})

    REPLAY_DIR.mkdir(parents=True, exist_ok=True)
    out_file = REPLAY_DIR / f"runtime_replay_{stamp}.json"
    out_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    LATEST_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Runtime Replay Snapshot generated: {out_file}")
    return payload


if __name__ == "__main__":
    build_replay_snapshot()
