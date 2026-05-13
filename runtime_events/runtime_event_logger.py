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
    "OpenClaw":             "execution_layer",
    "kline_update":         "execution_layer",
    "coverage_monitor":     "execution_layer",
    "report_pipeline":      "execution_layer",
    "feature_engine":       "execution_layer",
    "position_adapter":     "execution_layer",
    "paper_trade_executor": "execution_layer",
    "event_engine":         "governance_layer",
    # governance_layer
    "replay_engine":        "governance_layer",
    "governance_controller":"governance_layer",
    "audit_engine":         "governance_layer",
    "runtime_usage_builder":"governance_layer",
    "team_governance":      "governance_layer",
    "daily_health_check":   "governance_layer",
    "verify_prohibitions":  "governance_layer",
    # cockpit_layer
    "dashboard_snapshot":   "cockpit_layer",
    "cockpit_sync":         "cockpit_layer",
    "rolling_snapshot":     "cockpit_layer",
    "heartbeat_monitor":    "cockpit_layer",
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


if __name__ == "__main__":
    log_event_cli()
