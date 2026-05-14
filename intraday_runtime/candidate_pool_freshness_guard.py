#!/usr/bin/env python3
"""
Phase-2.8C Candidate Pool Freshness Guard

职责：
- 检测 candidate pool 是否 stale
- 阻止旧候选池进入 intraday runtime
"""

import json
from datetime import datetime, timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
CANDIDATE_FILE = BASE_DIR / "portfolio" / "candidate_rankings.json"
OUT_FILE = BASE_DIR / "intraday_runtime" / "candidate_pool_freshness_status.json"

STALE_HOURS = 20


def run_guard():
    status = {
        "phase": "Phase-2.8C",
        "generated_at": datetime.now().isoformat(),
        "candidate_pool_exists": CANDIDATE_FILE.exists(),
        "status": "UNKNOWN",
        "runtime_data_stale_or_missing": False,
    }

    if not CANDIDATE_FILE.exists():
        status.update({
            "status": "CRITICAL",
            "runtime_data_stale_or_missing": True,
            "reason": "candidate_pool_missing",
        })
    else:
        modified = datetime.fromtimestamp(CANDIDATE_FILE.stat().st_mtime)
        age = datetime.now() - modified

        status.update({
            "candidate_pool_modified_at": modified.isoformat(),
            "candidate_pool_age_hours": round(age.total_seconds() / 3600, 2),
        })

        if age > timedelta(hours=STALE_HOURS):
            status.update({
                "status": "WARNING",
                "runtime_data_stale_or_missing": True,
                "reason": "stale_candidate_pool",
            })
        else:
            status.update({
                "status": "PASS",
                "reason": "fresh_candidate_pool",
            })

    OUT_FILE.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"✅ Candidate Pool Freshness Guard: {status['status']}")
    return status


if __name__ == "__main__":
    run_guard()
