#!/usr/bin/env python3
"""
Governance Freeze Integrity Check
检查 OBSERVE_ONLY / auto_trade / auto_learn / adjust_weights / modify_baseline / robot_6~10 冻结状态。
输出: reports/freeze_integrity.json
"""
import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
REPORT_DIR = BASE_DIR / "reports"


def check_freeze_integrity() -> dict:
    soul_path = BASE_DIR / "config" / "soul_config.json"

    # 默认值
    observe_only = False
    auto_trade_disabled = False
    auto_learn_disabled = False
    adjust_weights_disabled = False
    modify_baseline_disabled = False

    if soul_path.exists():
        with open(soul_path, "r", encoding="utf-8") as f:
            soul = json.load(f)

        observe_only = soul.get("SOUL_MODE") == "OBSERVE_ONLY"
        auto_trade_disabled = "auto_trade" in soul.get("forbidden_actions", [])
        auto_learn_disabled = "auto_learn" in soul.get("forbidden_actions", [])
        adjust_weights_disabled = "adjust_weights" in soul.get("forbidden_actions", [])
        modify_baseline_disabled = "modify_baseline" in soul.get("forbidden_actions", [])

        # 额外检查 learning_enabled / auto_strategy_mutation / auto_weight_adjustment
        if not soul.get("learning_enabled", True):
            auto_learn_disabled = True
        if not soul.get("auto_strategy_mutation", True):
            modify_baseline_disabled = True
        if not soul.get("auto_weight_adjustment", True):
            adjust_weights_disabled = True

    # robot_6~10 冻结检查
    robot_6_10_frozen = False
    freeze_path = BASE_DIR / "governance" / "freeze_status.json"
    if freeze_path.exists():
        with open(freeze_path, "r", encoding="utf-8") as f:
            freeze = json.load(f)
        # 检查方式1: robots dict (deployed=false)
        robots = freeze.get("robots", {})
        if robots:
            frozen_count = 0
            for i in range(6, 11):
                rid = f"robot_{i}"
                if not robots.get(rid, {}).get("deployed", True):
                    frozen_count += 1
            robot_6_10_frozen = frozen_count >= 5
        else:
            # 检查方式2: reserved_team 列表存在且 official_team 不含 robot_6~10
            reserved = freeze.get("reserved_team", [])
            official = freeze.get("official_team", [])
            reserved_set = set(reserved)
            expected_reserved = {f"robot_{i}" for i in range(6, 11)}
            robot_6_10_frozen = expected_reserved.issubset(reserved_set) and not any(r in official for r in expected_reserved)

    all_passed = observe_only and auto_trade_disabled and auto_learn_disabled and adjust_weights_disabled and modify_baseline_disabled and robot_6_10_frozen
    status = "pass" if all_passed else "error"

    result = {
        "observe_only": observe_only,
        "auto_trade_disabled": auto_trade_disabled,
        "auto_learn_disabled": auto_learn_disabled,
        "adjust_weights_disabled": adjust_weights_disabled,
        "modify_baseline_disabled": modify_baseline_disabled,
        "robot_6_10_frozen": robot_6_10_frozen,
        "all_checks_passed": all_passed,
        "status": status,
    }

    # 写入报告
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = REPORT_DIR / "freeze_integrity.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    return result


if __name__ == "__main__":
    result = check_freeze_integrity()
    icon = "✅" if result["status"] == "pass" else "❌"
    print(f"{icon} Freeze Integrity: {result['status'].upper()}")
    checks = [
        ("OBSERVE_ONLY", result["observe_only"]),
        ("auto_trade=False", result["auto_trade_disabled"]),
        ("auto_learn=False", result["auto_learn_disabled"]),
        ("adjust_weights=False", result["adjust_weights_disabled"]),
        ("modify_baseline=False", result["modify_baseline_disabled"]),
        ("robot_6~10 frozen", result["robot_6_10_frozen"]),
    ]
    for label, ok in checks:
        print(f"  {'✅' if ok else '❌'} {label}")
