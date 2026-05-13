#!/usr/bin/env python3
"""
Phase-2.4B-Stable 禁止事项验证脚本
检查是否违反了稳定运行期的禁止规则。

原则：只读验证，不修改策略、不修改baseline、不触发交易。
"""

import json
import datetime
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent

PROHIBITED_ACTIONS = [
    "auto_learn",
    "modify_baseline",
    "adjust_weights",
    "auto_trade",
    "ai_autonomy",
]


def _today() -> str:
    return datetime.datetime.now().strftime("%Y-%m-%d")


def _safe_load_json(path: Path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def check_baseline_modifications():
    """检查baseline是否被修改"""
    baseline_dir = BASE_DIR / "baselines"
    if not baseline_dir.exists():
        return {"status": "safe", "message": "baseline目录不存在"}

    modified_files = []
    today_date = datetime.datetime.now().date()
    for baseline_file in baseline_dir.glob("*.json"):
        mtime = datetime.datetime.fromtimestamp(baseline_file.stat().st_mtime)
        if mtime.date() == today_date:
            modified_files.append(baseline_file.name)

    if modified_files:
        return {
            "status": "violation",
            "message": f"baseline文件今日被修改: {', '.join(modified_files)}",
            "files": modified_files,
        }
    return {"status": "safe", "message": "baseline未被修改"}


def check_auto_trading():
    """检查是否有自动交易"""
    portfolio_dir = BASE_DIR / "portfolio"
    trade_log = portfolio_dir / "trade_log.json"
    today = _today()

    if trade_log.exists():
        data = _safe_load_json(trade_log) or {}
        today_trades = []
        for trade in data.get("trades", []):
            trade_time = str(trade.get("time", ""))
            if today in trade_time and trade.get("auto", False):
                today_trades.append(trade)
        if today_trades:
            return {
                "status": "violation",
                "message": f"今日有{len(today_trades)}笔自动交易",
                "trades": today_trades,
            }
    return {"status": "safe", "message": "无自动交易"}


def check_ai_autonomy():
    """检查AI自治操作"""
    monitor_dir = BASE_DIR / "system_monitor"
    decision_log = monitor_dir / "decision_logs.json"
    today = _today()

    if decision_log.exists():
        data = _safe_load_json(decision_log) or {}
        today_decisions = []
        for decision in data.get("decisions", []):
            decision_time = str(decision.get("timestamp", ""))
            if today in decision_time and decision.get("ai_autonomous", False):
                today_decisions.append(decision)
        if today_decisions:
            return {
                "status": "violation",
                "message": f"今日有{len(today_decisions)}项AI自治决策",
                "decisions": today_decisions,
            }
    return {"status": "safe", "message": "无AI自治操作"}


def check_weight_adjustments():
    """检查权重调整"""
    strategies_dir = BASE_DIR / "strategies"
    if not strategies_dir.exists():
        return {"status": "safe", "message": "策略目录不存在"}

    today_date = datetime.datetime.now().date()
    for strategy_file in strategies_dir.glob("*_weights.json"):
        mtime = datetime.datetime.fromtimestamp(strategy_file.stat().st_mtime)
        if mtime.date() == today_date:
            return {
                "status": "violation",
                "message": f"权重配置文件今日被修改: {strategy_file.name}",
                "file": strategy_file.name,
            }
    return {"status": "safe", "message": "无权重调整"}


def check_auto_learning():
    """检查自动学习"""
    experience_dir = BASE_DIR / "validated_experience"
    if not experience_dir.exists():
        return {"status": "safe", "message": "无自动学习"}

    today_date = datetime.datetime.now().date()
    for exp_file in experience_dir.glob("*.json"):
        mtime = datetime.datetime.fromtimestamp(exp_file.stat().st_mtime)
        if mtime.date() != today_date:
            continue
        exp_data = _safe_load_json(exp_file) or {}
        if exp_data.get("source") == "auto_learning":
            return {
                "status": "violation",
                "message": f"今日有自动学习经验: {exp_file.name}",
                "file": exp_file.name,
            }
    return {"status": "safe", "message": "无自动学习"}


def verify_prohibitions():
    """验证所有禁止事项"""
    print("正在验证Phase-2.4B-Stable禁止事项...")
    print("=" * 60)

    checks = {
        "baseline_modification": check_baseline_modifications(),
        "auto_trading": check_auto_trading(),
        "ai_autonomy": check_ai_autonomy(),
        "weight_adjustment": check_weight_adjustments(),
        "auto_learning": check_auto_learning(),
    }

    violations = []
    for action, result in checks.items():
        emoji = "✅" if result["status"] == "safe" else "❌"
        print(f"{emoji} {action}: {result['message']}")
        if result["status"] == "violation":
            violations.append({"action": action, "message": result["message"], "details": result})

    print("\n" + "=" * 60)
    if violations:
        print(f"⚠️  发现 {len(violations)} 项违规:")
        for violation in violations:
            print(f"  - {violation['message']}")

        report = {
            "timestamp": datetime.datetime.now().isoformat(),
            "date": _today(),
            "phase": "Phase-2.4B",
            "violations_found": len(violations),
            "violations": violations,
            "prohibited_actions": PROHIBITED_ACTIONS,
        }
        violation_dir = BASE_DIR / "system_health" / "violations"
        violation_dir.mkdir(parents=True, exist_ok=True)
        report_file = violation_dir / f"violations_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"\n违规报告已保存到: {report_file}")
        return False

    print("✅ 所有禁止事项均未违规")
    return True


def main():
    is_safe = verify_prohibitions()
    if not is_safe:
        print("\n⚠️ 警告: Phase-2.4B稳定运行期已违反禁止规则")
        print("请立即停止违规操作，保持系统只读观察模式")

    print("\nPhase-2.4B 稳定运行规则:")
    print("  1. 禁止自动学习")
    print("  2. 禁止修改baseline")
    print("  3. 禁止调整权重")
    print("  4. 禁止自动交易")
    print("  5. 禁止AI自治")
    return is_safe


if __name__ == "__main__":
    main()
