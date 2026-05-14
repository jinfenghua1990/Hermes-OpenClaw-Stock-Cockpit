#!/usr/bin/env python3
"""
Phase-2.8D Intraday Scheduler

职责：
- Runtime 主调度器
- 串联 Runtime 主链
- Runtime freshness blocking
- Runtime governance logging
- Runtime replay generation
- Scanner Adapter → Candidate Pool → Runtime Chain

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
from intraday_runtime.ai_arbitration_runtime import build_runtime as build_ai_arbitration
from intraday_runtime.intraday_feishu_router import build_feishu_routes
from intraday_runtime.intraday_quote_snapshot import build_snapshot as build_quote_snapshot
from intraday_runtime.intraday_runtime_factors_builder import build_intraday_factors
from runtime_reports.governance_runtime_report import build_report as build_governance_report
from runtime_reports.market_runtime_report import build_report as build_market_report
import subprocess
from runtime_reports.position_runtime_report import build_report as build_position_report
from runtime_replay.runtime_replay_snapshot import build_replay_snapshot
from runtime_adapters.scanner_to_candidate_rankings_adapter import main as run_scanner_adapter

BASE_DIR = Path(__file__).resolve().parent.parent
LOG_DIR = BASE_DIR / "logs"
LOG_FILE = LOG_DIR / "runtime_scheduler_log.json"

RUNTIME_PIPELINE = [
    "candidate_pool_refresh",
    "market_runtime",
    "realtime_structure",
    "sector_runtime",
    "market_emotion",
    "ai_arbitration",
    "runtime_reports",
    "feishu_router",
    "runtime_replay",
]

CRITICAL_BLOCK_STATUSES = {
    "CRITICAL",
    "FAILED",
}


def _should_block_runtime(stage_status):
    return stage_status in CRITICAL_BLOCK_STATUSES


def run_scheduler():
    now = datetime.now().isoformat()
    stages = []
    blocked = False

    try:
        # === Phase-2.8D: 盘中实时行情链路 ===
        # Step 1: 拉取 AkShare 全市场实时快照
        print("[scheduler] Phase-2.8D: Step 1 - Fetching AkShare intraday snapshot...")
        build_quote_snapshot()
        print("[scheduler] AkShare snapshot done → runtime_data/intraday_quote_snapshot.json")

        # Step 2: 合并 factors + snapshot → intraday_runtime_factors.json
        print("[scheduler] Phase-2.8D: Step 2 - Building intraday runtime factors...")
        build_intraday_factors()
        print("[scheduler] Intraday factors done → runtime_data/intraday_runtime_factors.json")

        # Step 3: Scanner Adapter 读 intraday_runtime_factors（今日真实涨跌幅）
        print("[scheduler] Phase-2.8D: Step 3 - Running Scanner Adapter...")
        run_scanner_adapter()
        print("[scheduler] Scanner Adapter done → candidate_rankings.json updated")

        candidate = refresh_candidate_pool()
        candidate_status = candidate.get("status", "UNKNOWN")

        stages.append({
            "stage": "candidate_pool_refresh",
            "status": candidate_status,
            "generated_at": now,
        })

        if _should_block_runtime(candidate_status):
            blocked = True

        market = build_runtime()
        market_status = market.get("status", "UNKNOWN")

        stages.append({
            "stage": "market_runtime",
            "status": market_status,
            "generated_at": now,
        })

        if _should_block_runtime(market_status):
            blocked = True

        structure = refresh_runtime()
        structure_status = structure.get("status", "UNKNOWN")

        stages.append({
            "stage": "realtime_structure",
            "status": structure_status,
            "stale_count": structure.get("stale_count", 0),
            "generated_at": now,
        })

        # WARNING stale 不阻断 Runtime，只进入 Governance。
        if _should_block_runtime(structure_status):
            blocked = True

        sector = build_sector_runtime()
        sector_status = sector.get("status", "UNKNOWN")

        stages.append({
            "stage": "sector_runtime",
            "status": sector_status,
            "generated_at": now,
        })

        if _should_block_runtime(sector_status):
            blocked = True

        emotion = build_market_emotion_runtime()
        emotion_status = emotion.get("status", "UNKNOWN")

        stages.append({
            "stage": "market_emotion",
            "status": emotion_status,
            "market_emotion": emotion.get("market_emotion"),
            "generated_at": now,
        })

        if _should_block_runtime(emotion_status):
            blocked = True

        arbitration = build_ai_arbitration()
        arbitration_status = arbitration.get("status", "UNKNOWN")

        stages.append({
            "stage": "ai_arbitration",
            "status": arbitration_status,
            "arbitration_result": arbitration.get("arbitration_result"),
            "generated_at": now,
        })

        if _should_block_runtime(arbitration_status):
            blocked = True

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
        "governance_mode": "WARNING_DOES_NOT_BLOCK_RUNTIME",
        "stages": stages,
    }

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    LOG_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    if final_status != "FAILED":
        build_governance_report()
        build_market_report()
        build_position_report()
        build_feishu_routes()
        build_replay_snapshot()

    print(f"Intraday Scheduler finished: {final_status}")
    return payload


if __name__ == "__main__":
    run_scheduler()
