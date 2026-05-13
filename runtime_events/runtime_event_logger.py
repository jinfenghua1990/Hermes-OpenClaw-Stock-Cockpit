#!/usr/bin/env python3
"""
Runtime Event Logger - 统一运行时事件流
所有模块通过此 logger 输出 event，追加到 runtime_events/{module_name}.jsonl

用法:
    from runtime_events.runtime_event_logger import log_event
    log_event(module="coverage_monitor", layer="execution_layer", status="success", message="coverage updated", runtime_ms=182)

CLI 用法 (shell 脚本中):
    python3 runtime_events/log_event.py <module> <layer> <status> <message> [runtime_ms]
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# 项目根目录
BASE_DIR = Path(__file__).resolve().parent.parent
EVENTS_DIR = BASE_DIR / "runtime_events"

# ============================================================
# EVENT 格式
# {
#   "timestamp":  "2026-05-13T09:00:00Z",   # UTC ISO8601
#   "module":     "coverage_monitor",          # 模块名
#   "layer":      "execution_layer",           # 层级
#   "status":     "success",                   # success / warning / error / running
#   "message":    "coverage updated",          # 人类可读消息
#   "runtime_ms": 182                          # 运行耗时(毫秒), 可选
# }
# ============================================================

VALID_STATUSES = {"success", "warning", "error", "running"}
VALID_LAYERS = {
    "execution_layer",
    "governance_layer",
    "cockpit_layer",
}

# 模块到层级的映射（避免每次调用都要传）
MODULE_LAYER_MAP = {
    # execution_layer
    "openclaw_fetch_sh":     "execution_layer",
    "feature_engine_sh":     "execution_layer",
    "coverage_monitor":      "execution_layer",
    "report_pipeline":       "execution_layer",
    "daily_pipeline":        "execution_layer",
    "paper_trade_executor":  "execution_layer",
    "notification_router":    "execution_layer",
    "position_manager":       "execution_layer",
    "pnl_tracker":           "execution_layer",
    # governance_layer
    "risk_controller":       "governance_layer",
    "scheduler_sh":           "governance_layer",
    "replay_market_day":     "governance_layer",
    "event_engine":          "governance_layer",
    "daily_health_check":    "governance_layer",
    "position_adapter":       "governance_layer",
    "robot5_risk_sh":        "governance_layer",
    "main_aggregate_sh":     "governance_layer",
    # cockpit_layer
    "rolling_snapshot":       "cockpit_layer",
    "heartbeat_monitor":      "cockpit_layer",
    "robot4_match_sh":       "cockpit_layer",
    "cockpit_frontend":      "cockpit_layer",
}


def log_event(
    module: str,
    layer: Optional[str] = None,
    status: str = "success",
    message: str = "",
    runtime_ms: Optional[int] = None,
) -> None:
    """写入一条 Runtime Event 到 {module}.jsonl"""
    # 自动推断 layer
    if layer is None:
        layer = MODULE_LAYER_MAP.get(module, "execution_layer")

    if layer not in VALID_LAYERS:
        layer = "execution_layer"
    if status not in VALID_STATUSES:
        status = "running"

    event = {
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "module": module,
        "layer": layer,
        "status": status,
        "message": message,
    }
    if runtime_ms is not None:
        event["runtime_ms"] = runtime_ms

    # 确保目录存在
    EVENTS_DIR.mkdir(parents=True, exist_ok=True)

    # 追加写入 JSONL
    filepath = EVENTS_DIR / f"{module}.jsonl"
    with open(filepath, "a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")

    # shell 脚本可读 stdout（非强制）
    # print(json.dumps(event, ensure_ascii=False))


def log_event_cli() -> None:
    """CLI 入口: python3 runtime_events/log_event.py <module> <layer> <status> <message> [runtime_ms]"""
    if len(sys.argv) < 4:
        print("Usage: python3 runtime_events/log_event.py <module> <layer> <status> <message> [runtime_ms]", file=sys.stderr)
        sys.exit(1)

    module = sys.argv[1]
    layer = sys.argv[2] if sys.argv[2] != "auto" else None
    status = sys.argv[3]
    message = sys.argv[4]
    runtime_ms = int(sys.argv[5]) if len(sys.argv) > 5 and sys.argv[5].isdigit() else None

    log_event(module=module, layer=layer, status=status, message=message, runtime_ms=runtime_ms)
    print(f"✅ event logged: {module}/{status}")


def list_event_files() -> list:
    """返回所有 event 文件列表"""
    EVENTS_DIR.mkdir(parents=True, exist_ok=True)
    return sorted(EVENTS_DIR.glob("*.jsonl"))


def read_events(module: str) -> list[dict]:
    """读取指定模块的全部事件"""
    filepath = EVENTS_DIR / f"{module}.jsonl"
    if not filepath.exists():
        return []
    events = []
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                events.append(json.loads(line))
    return events


def summarize_events() -> dict:
    """汇总所有 runtime_events/*.jsonl，返回结构化摘要供 dashboard/日报使用"""
    EVENTS_DIR.mkdir(parents=True, exist_ok=True)

    # 从 MODULE_LAYER_MAP 动态构建层模块列表
    layer_modules = {"execution_layer": [], "governance_layer": [], "cockpit_layer": []}
    for mod, layer in MODULE_LAYER_MAP.items():
        if layer in layer_modules:
            layer_modules[layer].append(mod)

    # 读取所有 jsonl，取每个模块最后一条事件
    module_latest = {}
    for jsonl_file in EVENTS_DIR.glob("*.jsonl"):
        events = []
        with open(jsonl_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        events.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
        if events:
            module_latest[jsonl_file.stem] = events[-1]

    # 按层统计 active 模块（以 layer_modules 的模块为全集）
    layer_active = {"execution_layer": 0, "governance_layer": 0, "cockpit_layer": 0}
    for mod in layer_modules["execution_layer"] + layer_modules["governance_layer"] + layer_modules["cockpit_layer"]:
        if mod in module_latest:
            layer = MODULE_LAYER_MAP.get(mod, "execution_layer")
            if layer in layer_active:
                layer_active[layer] += 1

    total_active = sum(layer_active.values())

    # 取最近5条事件（按时间倒序）
    all_latest = sorted(module_latest.values(), key=lambda e: e.get("timestamp", ""), reverse=True)
    latest_events = [{
        "module": evt.get("module", ""),
        "layer": evt.get("layer", ""),
        "status": evt.get("status", ""),
        "timestamp": evt.get("timestamp", ""),
        "message": evt.get("message", ""),
    } for evt in all_latest[:5]]

    return {
        "total_modules": len(MODULE_LAYER_MAP),
        "active_modules": total_active,
        "layers": {
            "execution_layer": {"total": len(layer_modules["execution_layer"]), "active": layer_active["execution_layer"]},
            "governance_layer": {"total": len(layer_modules["governance_layer"]), "active": layer_active["governance_layer"]},
            "cockpit_layer": {"total": len(layer_modules["cockpit_layer"]), "active": layer_active["cockpit_layer"]},
        },
        "latest_events": latest_events,
    }


if __name__ == "__main__":
    log_event_cli()
