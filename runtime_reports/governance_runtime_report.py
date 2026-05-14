#!/usr/bin/env python3
"""
Phase-2.8C Governance Runtime Report

职责：
- Runtime Governance Summary
- Runtime freshness governance
- WHY_SKIP / WHY_BLOCK trace

System Mode:
- PAPER_ONLY
- OBSERVE_ONLY
"""

import json
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
LOG_FILE = BASE_DIR / "logs" / "runtime_scheduler_log.json"
OUT_FILE = BASE_DIR / "runtime_reports" / "governance_runtime_report.md"


def _load(path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return default if default is not None else {}


def build_report():
    scheduler = _load(LOG_FILE, {})
    stages = scheduler.get("stages", [])
    final_status = scheduler.get("final_status", "UNKNOWN")

    stale_count = sum(stage.get("stale_count", 0) for stage in stages)
    blocked_count = sum(1 for stage in stages if stage.get("status") == "BLOCKED")
    failed_count = sum(1 for stage in stages if stage.get("status") == "FAILED")

    freshness_status = "STALE" if stale_count else "FRESH"

    reasons = []
    for stage in stages:
        if stage.get("status") in ("FAILED", "BLOCKED", "CRITICAL"):
            reasons.append(f"- WHY_BLOCK: {stage.get('stage')} status={stage.get('status')}")
        elif stage.get("stale_count", 0):
            reasons.append(f"- WHY_SKIP: {stage.get('stage')} stale_count={stage.get('stale_count')}")

    report = f'''# Governance Runtime Report

Generated At: {datetime.now().isoformat()}

## Runtime Summary

- Final Status: {final_status}
- Freshness Status: {freshness_status}
- Stale Count: {stale_count}
- Blocked Count: {blocked_count}
- Failed Count: {failed_count}

## Runtime Stages

'''

    for stage in stages:
        report += f"- {stage.get('stage')}: {stage.get('status')}\n"

    report += "\n## Governance Trace\n\n"

    if reasons:
        report += "\n".join(reasons)
    else:
        report += "- No governance block triggered\n"

    report += "\n## System Mode\n\n- PAPER_ONLY\n- OBSERVE_ONLY\n"

    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(report, encoding="utf-8")

    print("Governance Runtime Report generated")
    return report


if __name__ == "__main__":
    build_report()
