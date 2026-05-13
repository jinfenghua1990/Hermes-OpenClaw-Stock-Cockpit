#!/usr/bin/env python3
"""
Runtime Event Health Gate
检查所有 enabled 模块是否在今天产生了 runtime event。
数据源: governance/module_runtime_schema.yaml + runtime_events/*.jsonl
输出:   reports/runtime_event_health.json
"""

import json
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
SCHEMA_PATH = BASE_DIR / "governance" / "module_runtime_schema.yaml"
EVENTS_DIR = BASE_DIR / "runtime_events"
REPORT_PATH = BASE_DIR / "reports" / "runtime_event_health.json"


def parse_yaml_modules(schema_path: Path) -> list[dict]:
    """从 module_runtime_schema.yaml 中提取 enabled 模块（轻量解析，不依赖 pyyaml）"""
    modules = []
    current_layer = ""

    with open(schema_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    i = 0
    while i < len(lines):
        stripped = lines[i].rstrip()

        # 检测层级名 (如 "  execution_layer:")
        if stripped.startswith("  ") and stripped.strip().endswith("_layer:"):
            current_layer = stripped.strip()[:-1]  # 去冒号
            i += 1
            continue

        # 检测模块 "- name: xxx"
        if stripped.strip().startswith("- name:"):
            name = stripped.strip().split(":", 1)[1].strip()
            enabled = True  # 默认 true

            # 向前看几行找 enabled
            for j in range(i + 1, min(i + 5, len(lines))):
                inner = lines[j].strip()
                if inner.startswith("enabled:"):
                    val = inner.split(":", 1)[1].strip().lower()
                    enabled = (val == "true")
                    break
                if inner.startswith("- name:") or inner.startswith("  - name:"):
                    break

            if enabled:
                modules.append({"name": name, "layer": current_layer})

        i += 1

    return modules


def check_runtime_event_health() -> dict:
    """主检查逻辑"""
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # 1. 读取 schema 中 enabled 模块
    enabled_modules = parse_yaml_modules(SCHEMA_PATH)
    total_modules = len(enabled_modules)

    # 2. 读取每个模块的 jsonl
    active_today = []
    missing_today = []
    warning_modules = []
    error_modules = []

    for mod in enabled_modules:
        name = mod["name"]
        jsonl_path = EVENTS_DIR / f"{name}.jsonl"

        # 检查 jsonl 是否存在
        if not jsonl_path.exists():
            missing_today.append(name)
            continue

        # 读取最后一条事件
        last_event = None
        with open(jsonl_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        last_event = json.loads(line)
                    except json.JSONDecodeError:
                        pass

        if last_event is None:
            missing_today.append(name)
            continue

        # 检查 timestamp 是否为今天
        ts = last_event.get("timestamp", "")
        is_today = ts.startswith(today_str)

        if not is_today:
            missing_today.append(name)
            continue

        # 检查 status
        status = last_event.get("status", "unknown")
        if status == "error":
            error_modules.append(name)
        elif status == "warning":
            warning_modules.append(name)

        active_today.append(name)

    # 3. 判定总体状态
    if error_modules:
        overall_status = "error"
    elif missing_today:
        overall_status = "warning"
    else:
        overall_status = "pass"

    result = {
        "date": today_str,
        "total_modules": total_modules,
        "active_today": len(active_today),
        "missing_today": missing_today,
        "warning_modules": warning_modules,
        "error_modules": error_modules,
        "status": overall_status,
    }

    # 4. 写入报告
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    return result


if __name__ == "__main__":
    result = check_runtime_event_health()

    status_icon = {"pass": "✅", "warning": "⚠️", "error": "❌"}.get(result["status"], "?")
    print(f"Runtime Event Health Gate — {status_icon} {result['status'].upper()}")
    print(f"  模块: {result['active_today']}/{result['total_modules']} 活跃")

    if result["missing_today"]:
        print(f"  ⚠️  今日无事件: {', '.join(result['missing_today'])}")
    if result["warning_modules"]:
        print(f"  ⚠️  Warning模块: {', '.join(result['warning_modules'])}")
    if result["error_modules"]:
        print(f"  ❌ Error模块: {', '.join(result['error_modules'])}")

    print(f"\n报告: {REPORT_PATH}")
