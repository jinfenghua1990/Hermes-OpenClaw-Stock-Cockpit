#!/usr/bin/env python3
"""
Phase-2.8C Intraday Scheduler

职责：
- Runtime 主调度器
- 串联 Runtime 主链
- Runtime freshness blocking
- Runtime governance logging

System Mode:
- PAPER_ONLY
- OBSERVE_ONLY
"""

import json
from datetime import datetime
from pathlib import Path

from intraday_runtime.candidate_pool_refresh_runtime import refresh_candidate_pool
from intraday_runtime.intraday_market_data_runtime import build_runtime
from intraday_runtime.realtime_structure_refresh import refresh_runtime
from intraday_runtime.sector_runtime_engine import build_sector_runtime
from intraday_runtime.market_emotion_runtime import build_market_emotion_runtime

BASE_DIR = Path(__file__).resolve().parent.parent
LOG_DIR = BASE_DIR / "logs"
LOG_FILE = LOG_DIR / "runtime_scheduler_log.json"


RUNTIME_PIPELINE = [
    "candidate_pool_refresh",
    "market_runtime",
    "realtime_structure",
    "sector_runtime",
    "market_emotion",
]


def run_scheduler():
    now = datetime.now().isoformat()
    stages = []
    blocked = False

    try:
        candidate = refresh_candidate_pool()
        candidate_status = candidate.get("status", "UNKNOWN")

        stages.append({
            "stage": "candidate_pool_refresh",
            "status": candidate_status,
            "generated_at": now,
        })

        if candidate_status == "CRITICAL":
            blocked = True

        market = build_runtime()
        stages.append({
            "stage": "market_runtime",
            "status": market.get("status", "UNKNOWN"),
            "generated_at": now,
        })

        structure = refresh_runtime()
        structure_status = structure.get("status", "UNKNOWN")

        stages.append({
            "stage": "realtime_structure",
            "status": structure_status,
            "stale_count": structure.get("stale_count", 0),
            "generated_at": now,
        })

        if structure.get("stale_count", 0) > 0:
            blocked = True

        sector = build_sector_runtime()
        stages.append({
            "stage": "sector_runtime",
            "status": sector.get("status", "UNKNOWN"),
            "generated_at": now,
        })

        emotion = build_market_emotion_runtime()
        stages.append({
            "stage": "market_emotion",
            "status": emotion.get("status", "UNKNOWN"),
            "market_emotion": emotion.get("market_emotion"),
            "generated_at": now,
        })

        final_status = "BLOCKED" if blocked else "PASS"

    except Exception as e:
        final_status = "FAILED"
        stages.append({
            "stage": "runtime_exception",
            "status": "FAILED",
            "error": str(e),
            "generated_at": now,
        })

    payload = {
        "phase": "Phase-2.8C",
        "runtime_type": "intraday_scheduler",
        "system_mode": "PAPER_ONLY_OBSERVE_ONLY",
        "generated_at": now,
        "pipeline": RUNTIME_PIPELINE,
        "final_status": final_status,
        "paper_decision_allowed": final_status == "PASS",
        "stages": stages,
    }

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    LOG_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"✅ Intraday Scheduler finished: {final_status}")
    return payload


if __name__ == "__main__":
    run_scheduler()
