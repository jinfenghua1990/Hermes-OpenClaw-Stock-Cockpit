#!/usr/bin/env python3
"""
Phase-2.8C Runtime Health Aggregator

职责：
- 聚合 Runtime 主链健康状态
- 区分 PASS / WARNING / BLOCKED / FAILED
- 为 Cockpit / Feishu / Governance Report 提供统一健康摘要

System Mode:
- PAPER_ONLY
- OBSERVE_ONLY
"""

import json
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
OUT_DIR = BASE_DIR / "runtime_health"
OUT_FILE = OUT_DIR / "runtime_health_summary.json"

SOURCE_FILES = {
    "scheduler": BASE_DIR / "logs" / "runtime_scheduler_log.json",
    "candidate_pool": BASE_DIR / "intraday_runtime" / "candidate_pool_refresh_status.json",
    "sector_runtime": BASE_DIR / "runtime_data" / "sector_runtime.json",
    "market_emotion": BASE_DIR / "runtime_data" / "market_emotion_runtime.json",
    "ai_arbitration": BASE_DIR / "runtime_data" / "ai_arbitration_runtime.json",
    "feishu_router": BASE_DIR / "runtime_data" / "intraday_feishu_router.json",
}

CRITICAL_STATUSES = {"CRITICAL", "FAILED", "BLOCKED"}
WARNING_STATUSES = {"WARNING", "PASS_STATIC_FALLBACK"}
PASS_STATUSES = {"PASS", "PASS_DYNAMIC"}


def _load(path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return default if default is not None else {}


def _status_of(name, payload):
    if name == "scheduler":
        return payload.get("final_status", "MISSING")
    return payload.get("status", "MISSING")


def build_runtime_health_summary():
    now = datetime.now().isoformat()
    items = []
    critical_count = 0
    warning_count = 0
    pass_count = 0
    missing_count = 0

    for name, path in SOURCE_FILES.items():
        payload = _load(path, {})
        status = _status_of(name, payload)

        if not payload:
            status = "MISSING"
            missing_count += 1
        elif status in CRITICAL_STATUSES:
            critical_count += 1
        elif status in WARNING_STATUSES:
            warning_count += 1
        elif status in PASS_STATUSES:
            pass_count += 1
        else:
            warning_count += 1

        items.append({
            "name": name,
            "status": status,
            "source": str(path),
            "updated_at": payload.get("generated_at") or payload.get("updated_at") or "UNKNOWN",
        })

    if critical_count:
        overall = "FAILED"
    elif missing_count:
        overall = "WARNING"
    elif warning_count:
        overall = "WARNING"
    else:
        overall = "PASS"

    payload = {
        "phase": "Phase-2.8C",
        "runtime_type": "runtime_health_aggregator",
        "system_mode": "PAPER_ONLY_OBSERVE_ONLY",
        "generated_at": now,
        "overall_status": overall,
        "pass_count": pass_count,
        "warning_count": warning_count,
        "critical_count": critical_count,
        "missing_count": missing_count,
        "items": items,
        "governance_constraints": {
            "auto_trade": False,
            "auto_learning": False,
            "baseline_mutation": False,
        },
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Runtime Health Summary generated: {overall}")
    return payload


if __name__ == "__main__":
    build_runtime_health_summary()
