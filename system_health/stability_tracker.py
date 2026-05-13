#!/usr/bin/env python3
"""
Phase-2.4C 稳定性追踪器
每日记录关键指标，7日后生成 summary。
数据: system_health/stability_tracker.json
"""
import json
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
TRACKER_PATH = BASE_DIR / "system_health" / "stability_tracker.json"
PHASE_DIR = BASE_DIR / "reports" / "phase_2_4c"
PHASE_DIR.mkdir(parents=True, exist_ok=True)

OBSERVE_DAYS = 7


def load_tracker() -> dict:
    if TRACKER_PATH.exists():
        return json.loads(TRACKER_PATH.read_text(encoding="utf-8"))
    return {"phase": "Phase-2.4C", "start_date": "", "days": {}, "completed": False}


def save_tracker(tracker: dict):
    TRACKER_PATH.write_text(json.dumps(tracker, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def collect_daily_metrics() -> dict:
    """收集当日关键指标"""
    today = datetime.now().strftime("%Y-%m-%d")
    metrics = {"date": today, "checks": {}}

    # 1. runtime_event_health
    try:
        reh_path = BASE_DIR / "reports" / "runtime_event_health.json"
        if reh_path.exists():
            reh = json.loads(reh_path.read_text(encoding="utf-8"))
            metrics["checks"]["runtime_event_health"] = {
                "status": reh.get("status", "unknown"),
                "active_today": reh.get("active_today", 0),
                "total_modules": reh.get("total_modules", 0),
            }
    except Exception as e:
        metrics["checks"]["runtime_event_health"] = {"status": "error", "error": str(e)}

    # 2. snapshot_consistency
    try:
        sc_path = BASE_DIR / "reports" / "snapshot_consistency.json"
        if sc_path.exists():
            sc = json.loads(sc_path.read_text(encoding="utf-8"))
            metrics["checks"]["snapshot_consistency"] = {
                "status": sc.get("status", "unknown"),
                "consistent": sc.get("consistent", False),
                "modules": sc.get("runtime_usage_modules", 0),
            }
    except Exception as e:
        metrics["checks"]["snapshot_consistency"] = {"status": "error", "error": str(e)}

    # 3. freeze_integrity
    try:
        fi_path = BASE_DIR / "reports" / "freeze_integrity.json"
        if fi_path.exists():
            fi = json.loads(fi_path.read_text(encoding="utf-8"))
            metrics["checks"]["freeze_integrity"] = {
                "status": fi.get("status", "unknown"),
                "all_passed": fi.get("all_checks_passed", False),
            }
    except Exception as e:
        metrics["checks"]["freeze_integrity"] = {"status": "error", "error": str(e)}

    # 4. daily_health_check (从 history 读取)
    try:
        hh_path = BASE_DIR / "system_health" / "history" / f"{today}.json"
        if hh_path.exists():
            hh = json.loads(hh_path.read_text(encoding="utf-8"))
            checks = hh.get("checks", {})
            passed = sum(1 for v in checks.values() if v.get("status") in ("success", "pass"))
            warning = sum(1 for v in checks.values() if v.get("status") == "warning")
            error = sum(1 for v in checks.values() if v.get("status") == "error")
            metrics["checks"]["daily_health_check"] = {
                "status": hh.get("overall_status", "unknown"),
                "passed": passed,
                "warning": warning,
                "error": error,
            }
    except Exception as e:
        metrics["checks"]["daily_health_check"] = {"status": "error", "error": str(e)}

    # 5. SOUL_MODE
    try:
        soul_path = BASE_DIR / "config" / "soul_config.json"
        if soul_path.exists():
            soul = json.loads(soul_path.read_text(encoding="utf-8"))
            metrics["checks"]["soul_mode"] = {
                "status": "pass" if soul.get("SOUL_MODE") == "OBSERVE_ONLY" else "error",
                "mode": soul.get("SOUL_MODE", "unknown"),
            }
    except Exception as e:
        metrics["checks"]["soul_mode"] = {"status": "error", "error": str(e)}

    # 6. dashboard_snapshot
    try:
        snap_path = BASE_DIR / "system_monitor" / "system_snapshot.json"
        if snap_path.exists():
            snap = json.loads(snap_path.read_text(encoding="utf-8"))
            dm = snap.get("runtime_events", {}).get("total_modules", 0)
            metrics["checks"]["dashboard_snapshot"] = {
                "status": "pass" if dm == 17 else "warning",
                "total_modules": dm,
            }
    except Exception as e:
        metrics["checks"]["dashboard_snapshot"] = {"status": "error", "error": str(e)}

    # 7. runtime_usage_summary
    try:
        rus_path = BASE_DIR / "reports" / "runtime_usage_summary.json"
        if rus_path.exists():
            rus = json.loads(rus_path.read_text(encoding="utf-8"))
            rm = len(rus.get("modules", []))
            metrics["checks"]["runtime_usage_summary"] = {
                "status": "pass" if rm == 17 else "warning",
                "total_modules": rm,
            }
    except Exception as e:
        metrics["checks"]["runtime_usage_summary"] = {"status": "error", "error": str(e)}

    # ── 综合判定 ──
    # freeze_integrity 必须 pass，否则 pipeline 应停止
    freeze_ok = metrics["checks"].get("freeze_integrity", {}).get("status") == "pass"
    runtime_ok = metrics["checks"].get("runtime_event_health", {}).get("status") == "pass"
    consistency_ok = metrics["checks"].get("snapshot_consistency", {}).get("status") == "pass"
    soul_ok = metrics["checks"].get("soul_mode", {}).get("status") == "pass"

    critical_passed = freeze_ok and runtime_ok and consistency_ok and soul_ok
    metrics["overall"] = "pass" if critical_passed else ("error" if not freeze_ok else "warning")
    metrics["freeze_ok"] = freeze_ok
    metrics["pipeline_should_stop"] = not freeze_ok

    return metrics


def record_daily():
    """记录当日指标到 tracker"""
    tracker = load_tracker()
    metrics = collect_daily_metrics()
    today = metrics["date"]

    # 设置开始日期
    if not tracker["start_date"]:
        tracker["start_date"] = today

    tracker["days"][today] = metrics
    save_tracker(tracker)

    # 检查是否完成7天
    days_count = len(tracker["days"])
    if days_count >= OBSERVE_DAYS:
        tracker["completed"] = True
        save_tracker(tracker)
        generate_summary(tracker)

    return metrics, days_count


def generate_summary(tracker: dict):
    """7日结束生成 summary"""
    lines = []
    lines.append("# Phase-2.4C 稳定性观察报告")
    lines.append("")
    lines.append(f"- **观察期**: {tracker['start_date']} ~ {list(tracker['days'].keys())[-1]}")
    lines.append(f"- **观察天数**: {len(tracker['days'])} / {OBSERVE_DAYS}")
    lines.append(f"- **完成**: {'是' if tracker['completed'] else '否'}")
    lines.append("")

    lines.append("## 每日检查结果")
    lines.append("")
    lines.append("| 日期 | Overall | Runtime Health | Consistency | Freeze | Soul Mode | Health Check |")
    lines.append("|------|---------|---------------|-------------|--------|-----------|-------------|")

    for date, m in tracker["days"].items():
        checks = m.get("checks", {})
        reh = checks.get("runtime_event_health", {}).get("status", "?")
        sc = checks.get("snapshot_consistency", {}).get("status", "?")
        fi = checks.get("freeze_integrity", {}).get("status", "?")
        sm = checks.get("soul_mode", {}).get("status", "?")
        hc = checks.get("daily_health_check", {}).get("status", "?")
        ov = m.get("overall", "?")
        lines.append(f"| {date} | {ov} | {reh} | {sc} | {fi} | {sm} | {hc} |")

    lines.append("")
    lines.append("## 禁止事项确认")
    lines.append("")
    lines.append("- ❌ 不新增 robot")
    lines.append("- ❌ 不改 baseline")
    lines.append("- ❌ 不新增策略")
    lines.append("- ❌ 不自动学习")
    lines.append("- ❌ 不调权重")
    lines.append("- ❌ 不做 cockpit frontend")
    lines.append("- ❌ 不做重构")
    lines.append("")

    # 异常记录
    anomalies = []
    for date, m in tracker["days"].items():
        if m.get("overall") != "pass":
            anomalies.append(f"- {date}: {m.get('overall')} — {json.dumps(m.get('checks', {}), ensure_ascii=False)[:200]}")

    if anomalies:
        lines.append("## 异常记录")
        lines.append("")
        lines.extend(anomalies)
    else:
        lines.append("## 异常记录")
        lines.append("")
        lines.append("无异常 ✅")

    lines.append("")
    lines.append("---")
    lines.append(f"*生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*")

    summary_path = PHASE_DIR / "phase_2_4c_stability_summary.md"
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    metrics, days_count = record_daily()

    icon = "✅" if metrics["overall"] == "pass" else "⚠️" if metrics["overall"] == "warning" else "❌"
    print(f"{icon} Phase-2.4C Daily: {metrics['date']}")
    print(f"  Overall: {metrics['overall']}")

    checks = metrics.get("checks", {})
    for name, check in checks.items():
        ci = "✅" if check.get("status") in ("pass", "success") else "⚠️" if check.get("status") == "warning" else "❌"
        print(f"  {ci} {name}: {check.get('status', '?')}")

    if metrics.get("pipeline_should_stop"):
        print("🚨 freeze_integrity 不通过 — Pipeline 应立即停止！")

    print(f"  累计天数: {days_count}/{OBSERVE_DAYS}")

    if days_count >= OBSERVE_DAYS:
        print(f"\n📊 7日观察完成！报告: reports/phase_2_4c/phase_2_4c_stability_summary.md")
