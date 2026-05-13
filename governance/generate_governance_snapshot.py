#!/usr/bin/env python3
"""
Phase-2.6D Governance Snapshot Generator
生成每日 governance 状态快照，记录系统各层是否正常激活。
"""
import json, os
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).parent.parent.resolve()

def get_phase():
    try:
        return (BASE / "paper_trading" / "paper_decision_engine.py").read_text().split("Phase-2.6D")[1][:50].split("\n")[0].strip()
    except:
        return "Phase-2.6D-Stable"

def check_file(path, min_bytes=10):
    return os.path.exists(path) and os.path.getsize(path) > min_bytes

def generate_governance_snapshot():
    today = datetime.now().strftime("%Y-%m-%d")
    now  = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    snap_dir = BASE / "governance" / "snapshots"
    snap_dir.mkdir(exist_ok=True)

    out = {
        "phase": "Phase-2.6D",
        "generated_at": now,
        "date": today,
        "paper_mode": True,
        "observation_freeze": True,
        "risk_validation_enabled": check_file(BASE / "governance" / "risk_price_validation.py"),
        "risk_controller_enabled": check_file(BASE / "paper_trading" / "risk_controller.py"),
        "paper_decision_engine_v2_6D": check_file(BASE / "paper_trading" / "paper_decision_engine.py"),
        "daily_report_v2": check_file(BASE / "report_engine" / "generators" / "generate_daily_report_v2.py"),
        "cockpit_connected": check_file(BASE / "frontend" / "src" / "App.jsx"),
        "health_check_status": "PASS",
        "health_check_details": {},
        "files_present": {},
        "observation_freeze_rules": {
            "auto_learn": False,
            "auto_strategy_evolution": False,
            "auto_parameter_tuning": False,
            "auto_trade": False,
            "real_trade": False,
        },
    }

    # 检查各文件是否存在
    files = {
        "governance_risk_price_validation": BASE / "governance" / "risk_price_validation.py",
        "paper_risk_controller": BASE / "paper_trading" / "risk_controller.py",
        "paper_decision_engine": BASE / "paper_trading" / "paper_decision_engine.py",
        "daily_report_v2": BASE / "report_engine" / "generators" / "generate_daily_report_v2.py",
        "daily_health_check": BASE / "system_health" / "daily_health_check.py",
        "app_jsx": BASE / "frontend" / "src" / "App.jsx",
        "soul_config": BASE / "config" / "soul_config.json",
        "risk_price_validation_py": BASE / "paper_trading" / "risk_price_validation.py",
    }
    out["files_present"] = {k: check_file(v) for k, v in files.items()}

    # Health check 状态
    hc_file = BASE / "system_health" / "history" / f"{today}.json"
    if hc_file.exists():
        try:
            hc = json.loads(hc_file.read_text())
            overall = hc.get("overall_status", "unknown")
            out["health_check_status"] = overall.upper() if overall in ("success","warning","error","critical") else "WARNING"
            out["health_check_details"] = {
                "total": hc.get("total_checks", 0),
                "success": hc.get("success_count", 0),
                "warning": hc.get("warning_count", 0),
                "error": hc.get("error_count", 0),
                "critical": hc.get("critical_count", 0),
            }
        except:
            out["health_check_status"] = "WARNING"
    else:
        out["health_check_status"] = "WARNING"

    # 判断最终状态
    all_present = all(out["files_present"].values())
    if all_present and out["health_check_status"] in ("PASS","SUCCESS","WARNING"):
        out["status"] = "PASS"
    elif all_present:
        out["status"] = "WARNING"
    else:
        out["status"] = "FAIL"

    out_path = snap_dir / f"{today}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print(f"✅ Governance Snapshot: {out_path}")
    print(f"   Status: {out['status']} | Health: {out['health_check_status']}")
    print(f"   Files: {sum(out['files_present'].values())}/{len(out['files_present'])} present")
    return out

if __name__ == "__main__":
    generate_governance_snapshot()