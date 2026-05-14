#!/usr/bin/env python3
"""
Phase-2.8C Intraday Feishu Router

This module only builds routing payloads for runtime alerts.
It does not call any external webhook and does not place real orders.

System Mode:
- PAPER_ONLY
- OBSERVE_ONLY
"""

import json
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
LOG_FILE = BASE_DIR / "logs" / "runtime_scheduler_log.json"
OUT_DIR = BASE_DIR / "runtime_data"
OUT_FILE = OUT_DIR / "intraday_feishu_router.json"


def _load(path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return default if default is not None else {}


def build_feishu_routes():
    now = datetime.now().isoformat()
    scheduler = _load(LOG_FILE, {})
    final_status = scheduler.get("final_status", "UNKNOWN")
    stages = scheduler.get("stages", [])
    routes = []

    for stage in stages:
        stage_name = stage.get("stage", "unknown_stage")
        stage_status = stage.get("status", "UNKNOWN")
        stale_count = stage.get("stale_count", 0)
        market_emotion = stage.get("market_emotion")

        if stage_status in ("FAILED", "CRITICAL", "BLOCKED"):
            routes.append({
                "route_type": "GOVERNANCE",
                "severity": "HIGH",
                "event_type": "runtime_block_or_fail",
                "stage": stage_name,
                "message": f"Runtime stage abnormal: {stage_name} status={stage_status}",
                "should_notify": True,
                "created_at": now,
            })
        elif stage_name == "realtime_structure" and stale_count:
            routes.append({
                "route_type": "STRUCTURE",
                "severity": "MEDIUM",
                "event_type": "structure_stale",
                "stage": stage_name,
                "message": f"Structure stale count={stale_count}",
                "should_notify": True,
                "created_at": now,
            })
        elif stage_name == "market_emotion" and market_emotion in ("COLD", "HOT"):
            routes.append({
                "route_type": "RISK",
                "severity": "MEDIUM",
                "event_type": "market_emotion_extreme",
                "stage": stage_name,
                "message": f"Market emotion={market_emotion}",
                "should_notify": True,
                "created_at": now,
            })

    if final_status == "PASS":
        routes.append({
            "route_type": "RUNTIME",
            "severity": "LOW",
            "event_type": "runtime_ok",
            "stage": "scheduler",
            "message": "Runtime finished. Deep details are in runtime_reports.",
            "should_notify": False,
            "created_at": now,
        })

    payload = {
        "phase": "Phase-2.8C",
        "runtime_type": "intraday_feishu_router",
        "system_mode": "PAPER_ONLY_OBSERVE_ONLY",
        "generated_at": now,
        "source": str(LOG_FILE),
        "final_status": final_status,
        "route_count": len(routes),
        "notify_count": sum(1 for item in routes if item.get("should_notify")),
        "routes": routes,
        "status": "PASS",
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Intraday Feishu Router generated: routes={len(routes)} notify={payload['notify_count']}")
    return payload


if __name__ == "__main__":
    build_feishu_routes()
