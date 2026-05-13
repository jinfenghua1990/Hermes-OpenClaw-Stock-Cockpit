#!/usr/bin/env python3
"""
Runtime Overview Panel Builder
聚合 runtime_event_health / runtime_usage_summary / system_health / coverage / governance_status
输出: dashboard/runtime_overview_panel.json
"""
import json
import sys
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
PANEL_PATH = BASE_DIR / "dashboard" / "runtime_overview_panel.json"
REPORT_DIR = BASE_DIR / "reports"


def build_runtime_overview_panel() -> dict:
    panel = json.loads(PANEL_PATH.read_text(encoding="utf-8"))

    # 1. runtime_event_health
    reh_path = REPORT_DIR / "runtime_event_health.json"
    if reh_path.exists():
        reh = json.loads(reh_path.read_text(encoding="utf-8"))
        panel["runtime_event_health"] = reh

    # 2. runtime_usage_summary
    rus_path = REPORT_DIR / "runtime_usage_summary.json"
    if rus_path.exists():
        rus = json.loads(rus_path.read_text(encoding="utf-8"))
        panel["runtime_usage_summary"] = {
            "total_modules": len(rus.get("modules", [])),
            "layers": rus.get("layers", {}),
        }

    # 3. system_health (from daily_health_check output)
    health_path = REPORT_DIR / "daily_health_report.json"
    if health_path.exists():
        hr = json.loads(health_path.read_text(encoding="utf-8"))
        checks = hr.get("checks", {})
        passed = sum(1 for v in checks.values() if v.get("status") == "pass")
        warning = sum(1 for v in checks.values() if v.get("status") == "warning")
        error = sum(1 for v in checks.values() if v.get("status") == "error")
        panel["system_health"] = {
            "health_check_status": hr.get("overall_status", "unknown"),
            "checks_passed": passed,
            "checks_warning": warning,
            "checks_error": error,
            "factor_cache_valid": hr.get("checks", {}).get("factor_cache", {}).get("valid_count", 0),
            "mode_candidates": hr.get("checks", {}).get("mode_scan", {}).get("total_candidates", 0),
        }

    # 4. coverage
    phase_path = BASE_DIR / "config" / "phase_2_4b_status.json"
    if phase_path.exists():
        ps = json.loads(phase_path.read_text(encoding="utf-8"))
        panel["coverage"] = {
            "total_coverage_pct": ps.get("coverage_pct", 0),
            "factor_cache_valid": ps.get("factor_cache_valid", 0),
            "mode_candidates": ps.get("mode_candidates", 0),
        }

    # 5. governance_status
    freeze_path = REPORT_DIR / "freeze_integrity.json"
    if freeze_path.exists():
        fi = json.loads(freeze_path.read_text(encoding="utf-8"))
        panel["governance_status"] = {
            "freeze_state": "ACTIVE",
            "observe_only": fi.get("observe_only", False),
            "auto_trade_disabled": fi.get("auto_trade_disabled", False),
            "auto_learn_disabled": fi.get("auto_learn_disabled", False),
            "robot_6_10_frozen": fi.get("robot_6_10_frozen", False),
            "freeze_integrity": fi.get("status", "unknown"),
        }

    # timestamp
    panel["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 写入
    PANEL_PATH.write_text(json.dumps(panel, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return panel


if __name__ == "__main__":
    panel = build_runtime_overview_panel()
    reh = panel.get("runtime_event_health", {})
    gs = panel.get("governance_status", {})
    print(f"Runtime Overview Panel")
    print(f"  Runtime Health: {reh.get('status', '?')} ({reh.get('active_today', '?')}/{reh.get('total_modules', '?')})")
    print(f"  Governance:     {gs.get('freeze_integrity', '?')} (OBSERVE_ONLY={gs.get('observe_only', '?')})")
    print(f"  → {PANEL_PATH}")
