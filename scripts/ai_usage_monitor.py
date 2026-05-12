#!/usr/bin/env python3
"""
ai_usage_monitor.py - Daily AI Usage Report
每天 07:00 汇总昨日 Hermes Main / robot-1~10 / OpenClaw 使用情况
推送飞书 AI Usage Daily Report
"""
import os, sys, json, re, glob
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional
import argparse

# =============================================================================
# 路径配置
# =============================================================================
HOME          = Path.home()
HERMES_BASE   = HOME / ".hermes"
CRON_BASE     = HOME / "project_ai_trading"
MONITORING_DIR= CRON_BASE / "monitoring"
REPORTS_DIR   = CRON_BASE / "reports" / "ai_usage_daily"
LOG_DIR       = CRON_BASE / "cron" / "logs"

MONITORING_DIR.mkdir(parents=True, exist_ok=True)
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

HERMES_GROUP_ID = "oc_174834d2967c4dfbdd692464f85398e0"

# =============================================================================
# 模型配置（各 Robot 的默认配置）
# =============================================================================
MODEL_CONFIG = {
    "hermes_main": {
        "name": "Hermes Main",
        "type": "hermes",
        "default_model": "deepseek-v3.2",
        "provider": "qianfan",
        "log_path": HERMES_BASE / "sessions",
    },
    "openclaw": {
        "name": "OpenClaw",
        "type": "openclaw",
        "default_model": "MiniMax-M2.5",
        "provider": "minimax-cn",
        "log_path": LOG_DIR,
    },
}
for i in range(1, 11):
    MODEL_CONFIG[f"robot_{i}"] = {
        "name": f"robot-{i}",
        "type": "robot",
        "default_model": "deepseek-v3.2" if i in (5, 9, 10) else "MiniMax-M2.7",
        "provider": "qianfan" if i in (5, 9, 10) else "minimax-cn",
        "log_path": HERMES_BASE / f"robot-{i}" / "sessions",
    }

# =============================================================================
# 工具函数
# =============================================================================
def load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text())
    except:
        return {}

def save_json(path: Path, data: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2))

def parse_ts(ts: str) -> Optional[datetime]:
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00").split("+")[0])
    except:
        return None

def get_session_files(base: Path, day: date) -> List[Path]:
    """获取指定日期的 session jsonl 文件"""
    if not base.exists():
        return []
    prefix = day.strftime("%Y%m%d")
    return sorted(base.glob(f"{prefix}_*.jsonl"))

# =============================================================================
# 1. 解析 Hermes / Robot session 文件
# =============================================================================
def parse_session_file(fp: Path) -> dict:
    """解析单个 session jsonl，返回统计 dict"""
    stats = {
        "task_count": 0,
        "call_count": 0,
        "error_count": 0,
        "tool_calls": {},
        "models_used": set(),
        "last_active": None,
        "token_estimate": 0,
        "feishu_push_count": 0,
        "trade_actions": [],
        "latencies": [],
    }
    prev_ts = None
    try:
        lines = fp.read_text().splitlines()
    except:
        return stats

    for raw in lines:
        try:
            d = json.loads(raw)
        except:
            continue
        role  = d.get("role", "")
        ts    = d.get("timestamp", "")
        model = d.get("model", "")
        if model:
            stats["models_used"].add(model)

        t = parse_ts(ts)
        if t:
            if stats["last_active"] is None or t > stats["last_active"]:
                stats["last_active"] = t

        if role == "session_meta":
            stats["task_count"] += 1
            prev_ts = t

        elif role == "tool":
            stats["call_count"] += 1
            name = d.get("name", "unknown")
            stats["tool_calls"][name] = stats["tool_calls"].get(name, 0) + 1

            # token 估算
            content = str(d.get("content", ""))
            stats["token_estimate"] += len(content) // 4

            # 延迟估算
            if prev_ts and t:
                delta = (t - prev_ts).total_seconds()
                if 0 < delta < 60:
                    stats["latencies"].append(delta)
                prev_ts = t

            # 错误检测（极严格：只计真正的错误日志行）
            # 排除工具 content 中的脚本注释/错误处理代码
            content = str(d.get("content", ""))
            # 真正错误特征：Traceback行 / Exception: / ERROR:开头 / panic
            # 用行级匹配，避免工具返回值中的脚本误报
            real_error = False
            for line in content.splitlines():
                line = line.strip()
                if re.match(r"Traceback \(most recent call last\)", line):
                    real_error = True; break
                if re.match(r"\w+Error\s*:", line):  # ValueError: TypeError: 等
                    real_error = True; break
                if re.match(r"ERROR:", line) and len(line) < 80:  # ERROR: 日志行
                    real_error = True; break
                if re.match(r"(panic|PANIC):", line):
                    real_error = True; break
            if real_error:
                stats["error_count"] += 1

            # 飞书推送
            if name in ("send_message", "lark_send"):
                stats["feishu_push_count"] += 1

            # 交易相关动作
            trade_keywords = ["buy", "sell", "paper_trade", "trade_log",
                              "unified_positions", "event_engine"]
            if any(k in name.lower() for k in trade_keywords) or \
               any(k in content.lower() for k in trade_keywords):
                stats["trade_actions"].append(name)

    return stats

def aggregate_sessions(base: Path, day: date) -> dict:
    """聚合指定日期所有 session 文件"""
    total = {
        "task_count": 0, "call_count": 0, "error_count": 0,
        "tool_calls": {}, "models_used": set(),
        "last_active": None, "token_estimate": 0,
        "feishu_push_count": 0, "trade_actions": [],
        "latencies": [],
    }
    for fp in get_session_files(base, day):
        s = parse_session_file(fp)
        total["task_count"]      += s["task_count"]
        total["call_count"]     += s["call_count"]
        total["error_count"]    += s["error_count"]
        total["token_estimate"] += s["token_estimate"]
        total["feishu_push_count"] += s["feishu_push_count"]
        for k, v in s["tool_calls"].items():
            total["tool_calls"][k] = total["tool_calls"].get(k, 0) + v
        total["models_used"].update(s["models_used"])
        total["trade_actions"].extend(s["trade_actions"])
        total["latencies"].extend(s["latencies"])
        if s["last_active"] and (total["last_active"] is None or
                                   s["last_active"] > total["last_active"]):
            total["last_active"] = s["last_active"]

    if total["latencies"]:
        total["avg_latency"] = sum(total["latencies"]) / len(total["latencies"])
    else:
        total["avg_latency"] = 0.0

    return total

# =============================================================================
# 2. 解析 OpenClaw 日志
# =============================================================================
def parse_openclaw_logs(log_dir: Path, day: date) -> dict:
    """解析 OpenClaw 日志文件"""
    stats = {
        "task_count": 0, "call_count": 0, "error_count": 0,
        "tool_calls": {}, "last_active": None,
        "openclaw_tui_calls": 0,
        "script_execution_count": 0,
        "file_edit_count": 0,
        "dry_run_count": 0,
        "paper_trade_executor_calls": 0,
        "event_engine_calls": 0,
        "failed_tool_calls": 0,
        "models_used": set(),
        "token_estimate": 0,
        "feishu_push_count": 0,
        "trade_actions": [],
        "latencies": [],
    }
    date_str = day.strftime("%Y%m%d")
    # 匹配 openclaw_YYYYMMDD_HHMM.log
    pattern = f"openclaw_{date_str[:4]}??_{date_str[4:]}??.log"
    files = sorted(log_dir.glob(pattern))

    for fp in files:
        try:
            lines = fp.read_text().splitlines()
        except:
            continue

        for line in lines:
            # 时间戳
            m = re.match(r"\[(\d{2}:\d{2}:\d{2})\]", line)
            if m:
                ts_str = f"{day.isoformat()}T{m.group(1)}"
                t = parse_ts(ts_str)
                if t and (stats["last_active"] is None or t > stats["last_active"]):
                    stats["last_active"] = t

            # 统计计数器
            if "正在获取" in line:
                stats["call_count"] += 1
            if "获取成功" in line or "✅" in line:
                stats["task_count"] += 1
            # 严格错误检测（避免 benign 日志误判）
            if any(p in line for p in ["Traceback", "ERROR:", "Exception", "failed:"]):
                stats["error_count"] += 1

            # OpenClaw 特定动作
            if "export MX_APIKEY" in line:
                stats["dry_run_count"] += 1
            if "paper_trade" in line.lower() or "paper_trade_executor" in line.lower():
                stats["paper_trade_executor_calls"] += 1
            if "event_engine" in line.lower():
                stats["event_engine_calls"] += 1
            if "tui" in line.lower() or "TUI" in line:
                stats["openclaw_tui_calls"] += 1
            if re.search(r"script.*\.sh|\.py.*执行", line):
                stats["script_execution_count"] += 1
            if re.search(r"edit|patch|write_file|write_file", line):
                stats["file_edit_count"] += 1
            if "飞书" in line or "send_message" in line.lower():
                stats["feishu_push_count"] += 1

            # 交易相关
            if any(k in line for k in ["买入", "卖出", "buy", "sell", "trade"]):
                stats["trade_actions"].append(line[:60])

    # 额外统计 notification_router log
    nr_file = log_dir / "notification_router.log"
    if nr_file.exists():
        for line in nr_file.read_text().splitlines():
            if day.strftime("%Y-%m-%d") in line:
                stats["feishu_push_count"] += 1
                if any(p in line for p in ["Traceback", "ERROR:", "Exception"]):
                    stats["error_count"] += 1

    if stats["latencies"]:
        stats["avg_latency"] = sum(stats["latencies"]) / len(stats["latencies"])
    else:
        stats["avg_latency"] = 0.0

    return stats

# =============================================================================
# 3. 读取 trade_log
# =============================================================================
def get_trade_stats(day: date) -> dict:
    trade_log = CRON_BASE / "portfolio" / "trade_log.json"
    if not trade_log.exists():
        return {}
    d = load_json(trade_log)
    today_str = day.isoformat()
    trades = [t for t in d.get("trades", []) if t.get("trade_date") == today_str]
    rejects = [r for r in d.get("rejects", []) if today_str in str(r)]
    return {
        "trade_count": len(trades),
        "reject_count": len(rejects),
        "success_count": sum(1 for t in trades if t.get("success")),
        "symbols": list({t.get("symbol") for t in trades}),
    }

# =============================================================================
# 4. 判断 status
# =============================================================================
def get_status(error_count: int, last_active: Optional[datetime],
                yesterday: date) -> str:
    if error_count > 10:
        return "error"
    if error_count > 3:
        return "warning"
    if last_active:
        delta = (datetime.now() - last_active).total_seconds()
        if delta > 86400 * 2:   # 超过2天未活跃
            return "warning"
    return "normal"

# =============================================================================
# 5. 生成每日报告 JSON
# =============================================================================
def generate_daily_report(yesterday: date) -> dict:
    report = {
        "schema_version": "1.0",
        "report_date": yesterday.isoformat(),
        "generated_at": datetime.now().isoformat(),
        "entities": {},
        "summary": {
            "total_errors": 0,
            "total_tasks": 0,
            "total_calls": 0,
            "error_entities": [],
            "warning_entities": [],
            "red_alert": False,
            "red_alert_reasons": [],
        },
    }
    all_entities = []

    # Hermes Main
    main_sessions = HERMES_BASE / "sessions"
    main_stats = aggregate_sessions(main_sessions, yesterday)
    main_cfg = MODEL_CONFIG["hermes_main"]
    trade_stats = get_trade_stats(yesterday)
    entity = {
        "name": "Hermes Main",
        "type": "hermes",
        "model": list(main_stats["models_used"])[0] if main_stats["models_used"] else main_cfg["default_model"],
        "provider": main_cfg["provider"],
        "yesterday_task_count": main_stats["task_count"],
        "yesterday_call_count": main_stats["call_count"],
        "error_count": main_stats["error_count"],
        "avg_latency": round(main_stats["avg_latency"], 2),
        "last_active_time": main_stats["last_active"].isoformat() if main_stats["last_active"] else None,
        "token_estimate": main_stats["token_estimate"],
        "feishu_push_count": main_stats["feishu_push_count"],
        "trade_related_actions": len(main_stats["trade_actions"]),
        "status": get_status(main_stats["error_count"], main_stats["last_active"], yesterday),
        "top_tools": dict(sorted(main_stats["tool_calls"].items(),
                                 key=lambda x: -x[1])[:5]),
    }
    report["entities"]["hermes_main"] = entity
    all_entities.append(entity)

    # OpenClaw
    ocfg = MODEL_CONFIG["openclaw"]
    oc_stats = parse_openclaw_logs(LOG_DIR, yesterday)
    entity = {
        "name": "OpenClaw",
        "type": "openclaw",
        "model": ocfg["default_model"],
        "provider": ocfg["provider"],
        "yesterday_task_count": oc_stats["task_count"],
        "yesterday_call_count": oc_stats["call_count"],
        "error_count": oc_stats["error_count"],
        "avg_latency": round(oc_stats["avg_latency"], 2),
        "last_active_time": oc_stats["last_active"].isoformat() if oc_stats["last_active"] else None,
        "token_estimate": oc_stats["token_estimate"],
        "feishu_push_count": oc_stats["feishu_push_count"],
        "trade_related_actions": len(oc_stats["trade_actions"]),
        "status": get_status(oc_stats["error_count"], oc_stats["last_active"], yesterday),
        "openclaw_tui_calls": oc_stats["openclaw_tui_calls"],
        "script_execution_count": oc_stats["script_execution_count"],
        "file_edit_count": oc_stats["file_edit_count"],
        "dry_run_count": oc_stats["dry_run_count"],
        "paper_trade_executor_calls": oc_stats["paper_trade_executor_calls"],
        "event_engine_calls": oc_stats["event_engine_calls"],
        "failed_tool_calls": oc_stats["failed_tool_calls"],
        "top_tools": dict(sorted(oc_stats["tool_calls"].items(),
                                 key=lambda x: -x[1])[:5]),
    }
    report["entities"]["openclaw"] = entity
    all_entities.append(entity)

    # Robots
    for i in range(1, 11):
        key = f"robot_{i}"
        cfg = MODEL_CONFIG[key]
        sess_dir = HERMES_BASE / f"robot-{i}" / "sessions"
        stats = aggregate_sessions(sess_dir, yesterday)
        entity = {
            "name": f"robot-{i}",
            "type": "robot",
            "model": list(stats["models_used"])[0] if stats["models_used"] else cfg["default_model"],
            "provider": cfg["provider"],
            "yesterday_task_count": stats["task_count"],
            "yesterday_call_count": stats["call_count"],
            "error_count": stats["error_count"],
            "avg_latency": round(stats["avg_latency"], 2),
            "last_active_time": stats["last_active"].isoformat() if stats["last_active"] else None,
            "token_estimate": stats["token_estimate"],
            "feishu_push_count": stats["feishu_push_count"],
            "trade_related_actions": len(stats["trade_actions"]),
            "status": get_status(stats["error_count"], stats["last_active"], yesterday),
            "top_tools": dict(sorted(stats["tool_calls"].items(),
                                     key=lambda x: -x[1])[:5]),
        }
        report["entities"][key] = entity
        all_entities.append(entity)

    # Summary
    report["summary"]["total_errors"] = sum(
        e["error_count"] for e in all_entities)
    report["summary"]["total_tasks"] = sum(
        e["yesterday_task_count"] for e in all_entities)
    report["summary"]["total_calls"] = sum(
        e["yesterday_call_count"] for e in all_entities)
    report["summary"]["error_entities"] = [
        e["name"] for e in all_entities if e["status"] == "error"]
    report["summary"]["warning_entities"] = [
        e["name"] for e in all_entities if e["status"] == "warning"]

    # red_alert 判断
    reasons = []
    if report["summary"]["total_errors"] > 30:
        reasons.append(f"总错误数 {report['summary']['total_errors']} > 30")
    if report["summary"]["total_errors"] > 10:
        report["summary"]["warning_entities"].append("total_errors_high")
    if trade_stats.get("reject_count", 0) > 5:
        reasons.append(f"交易拒绝 {trade_stats['reject_count']} > 5")
    if any(e["status"] == "error" for e in all_entities):
        reasons.append("存在 error 状态实体")
    if report["entities"].get("openclaw", {}).get("paper_trade_executor_calls", 0) > 0 and \
       report["entities"].get("openclaw", {}).get("error_count", 0) > 2:
        reasons.append("paper_trade_executor 异常")

    report["summary"]["red_alert"] = len(reasons) > 0
    report["summary"]["red_alert_reasons"] = reasons
    report["trade_stats"] = trade_stats

    # Top robots
    robots = [e for e in all_entities if e["type"] == "robot"]
    report["summary"]["top_robots"] = sorted(
        robots, key=lambda x: -x["yesterday_task_count"])[:3]

    return report

# =============================================================================
# 6. 生成 Markdown 报告
# =============================================================================
def generate_markdown(report: dict) -> str:
    yesterday = report["report_date"]
    summary = report["summary"]
    entities = report["entities"]
    trade = report.get("trade_stats", {})

    lines = [
        f"# AI Usage Daily Report",
        f"**日期**: {yesterday}",
        f"**统计区间**: 昨日 00:00 - 23:59",
        f"**生成时间**: {report['generated_at'][:19]}",
        "",
        "---",
        "",
        "## Hermes Main",
    ]

    e = entities.get("hermes_main", {})
    status_icon = "✅" if e.get("status") == "normal" else ("⚠️" if e.get("status") == "warning" else "🔴")
    lines += [
        f"| 项目 | 值 |",
        f"|------|-----|",
        f"| model | {e.get('model','-')} |",
        f"| provider | {e.get('provider','-')} |",
        f"| tasks | {e.get('yesterday_task_count',0)} |",
        f"| calls | {e.get('yesterday_call_count',0)} |",
        f"| errors | {e.get('error_count',0)} |",
        f"| avg_latency | {e.get('avg_latency',0):.2f}s |",
        f"| tokens(est) | {e.get('token_estimate',0)} |",
        f"| 飞书推送 | {e.get('feishu_push_count',0)} |",
        f"| 交易动作 | {e.get('trade_related_actions',0)} |",
        f"| status | {status_icon} {e.get('status','-')} |",
    ]

    # OpenClaw
    o = entities.get("openclaw", {})
    status_icon = "✅" if o.get("status") == "normal" else ("⚠️" if o.get("status") == "warning" else "🔴")
    lines += [
        "",
        "## OpenClaw",
        f"| 项目 | 值 |",
        f"|------|-----|",
        f"| model | {o.get('model','-')} |",
        f"| provider | {o.get('provider','-')} |",
        f"| script_exec | {o.get('script_execution_count',0)} |",
        f"| file_edit | {o.get('file_edit_count',0)} |",
        f"| dry_run | {o.get('dry_run_count',0)} |",
        f"| paper_trade_exec | {o.get('paper_trade_executor_calls',0)} |",
        f"| event_engine | {o.get('event_engine_calls',0)} |",
        f"| errors | {o.get('error_count',0)} |",
        f"| failed_tool | {o.get('failed_tool_calls',0)} |",
        f"| 飞书推送 | {o.get('feishu_push_count',0)} |",
        f"| status | {status_icon} {o.get('status','-')} |",
    ]

    # Top Robots
    lines += ["", "## Top Robots (by tasks)"]
    for rank, e in enumerate(summary.get("top_robots", []), 1):
        status_icon = "✅" if e.get("status") == "normal" else ("⚠️" if e.get("status") == "warning" else "🔴")
        lines += [
            f"",
            f"### {rank}. {e['name']}",
            f"| 项目 | 值 |",
            f"|------|-----|",
            f"| model | {e.get('model','-')} |",
            f"| tasks | {e.get('yesterday_task_count',0)} |",
            f"| errors | {e.get('error_count',0)} |",
            f"| 交易动作 | {e.get('trade_related_actions',0)} |",
            f"| status | {status_icon} {e.get('status','-')} |",
        ]

    # All Robots summary table
    lines += ["", "## All Robots Overview"]
    lines += ["| Robot | Model | Tasks | Errors | Status |"]
    lines += ["|-------|-------|-------|--------|-------|"]
    for key in sorted(entities.keys()):
        e = entities[key]
        if e["type"] != "robot":
            continue
        icon = "✅" if e.get("status")=="normal" else ("⚠️" if e.get("status")=="warning" else "🔴")
        lines.append(f"| {e['name']} | {e.get('model','-')} | {e.get('yesterday_task_count',0)} | {e.get('error_count',0)} | {icon} {e.get('status','-')} |")

    # Anomalies
    lines += ["", "## 异常"]
    anomalies = []
    if summary["error_entities"]:
        anomalies.append(f"🔴 error状态: {', '.join(summary['error_entities'])}")
    if summary["warning_entities"]:
        anomalies.append(f"⚠️  warning状态: {', '.join(summary['warning_entities'])}")
    if summary["total_errors"] > 3:
        anomalies.append(f"🔴 总错误数 {summary['total_errors']} > 3")
    if not anomalies:
        anomalies.append("无异常")
    lines += anomalies

    # Trade Summary
    if trade:
        lines += ["", "## 交易统计"]
        lines += [
            f"| 项目 | 值 |",
            f"|------|-----|",
            f"| 成交笔数 | {trade.get('trade_count',0)} |",
            f"| 成功 | {trade.get('success_count',0)} |",
            f"| 拒绝 | {trade.get('reject_count',0)} |",
            f"| 标的 | {', '.join(trade.get('symbols',[])) or '无'} |",
        ]

    # Conclusion
    lines += ["", "## 结论"]
    if summary["red_alert"]:
        lines += ["🔴 **red_alert 已触发**"]
        for r in summary["red_alert_reasons"]:
            lines.append(f"  - {r}")
        lines += ["", "⚠️ **建议**: 需人工介入检查，确认后继续 Phase-1.9B"]
    elif summary["warning_entities"]:
        lines += ["⚠️ **可正常运行**，但存在 warning:"]
        for w in summary["warning_entities"]:
            lines.append(f"  - {w}")
        lines += ["", "✅ **建议**: 可保持 Phase-1.9B 运行"]
    else:
        lines += ["✅ **可正常运行**", "✅ **建议**: 保持 Phase-1.9B 继续观察"]

    return "\n".join(lines)

# =============================================================================
# 7. 飞书推送
# =============================================================================
def feishu(msg: str, alert_type: str = "ai_usage_daily"):
    import subprocess
    try:
        subprocess.run(
            ["lark-cli", "im", "+messages-send",
             "--chat-id", HERMES_GROUP_ID, "--text", msg],
            capture_output=True, timeout=30
        )
        print(f"[FEISHU] 已发送: {alert_type}")
    except Exception as e:
        print(f"[FEISHU] 发送失败: {e}")

def feishu_daily_report(report: dict):
    yesterday = report["report_date"]
    summary  = report["summary"]
    entities = report["entities"]
    trade    = report.get("trade_stats", {})
    e_main   = entities.get("hermes_main", {})
    e_oc     = entities.get("openclaw", {})

    # 飞书正文（精简版）
    top = summary.get("top_robots", [])
    top_lines = []
    for rank, e in enumerate(top, 1):
        top_lines.append(f"{rank}. {e['name']} tasks={e.get('yesterday_task_count',0)}")

    status_main = e_main.get("status", "-")
    status_oc   = e_oc.get("status", "-")

    body = [
        f"📊 【AI Usage Daily Report】",
        f"日期：{yesterday}",
        f"统计区间：昨日 00:00 - 23:59",
        f"",
        f"🤖 Hermes Main:",
        f"  model: {e_main.get('model','-')} ({e_main.get('provider','-')})",
        f"  tasks: {e_main.get('yesterday_task_count',0)} | errors: {e_main.get('error_count',0)}",
        f"  status: {status_main}",
        f"",
        f"🔧 OpenClaw:",
        f"  model: {e_oc.get('model','-')} ({e_oc.get('provider','-')})",
        f"  script_exec: {e_oc.get('script_execution_count',0)} | dry_run: {e_oc.get('dry_run_count',0)}",
        f"  paper_trade: {e_oc.get('paper_trade_executor_calls',0)} | errors: {e_oc.get('error_count',0)}",
        f"  status: {status_oc}",
        f"",
        f"📋 Top Robots:",
    ]
    body += [f"  {t}" for t in top_lines]

    if summary["error_entities"] or summary["warning_entities"]:
        body.append(f"")
        if summary["error_entities"]:
            body.append(f"🔴 errors: {', '.join(summary['error_entities'])}")
        if summary["warning_entities"]:
            body.append(f"⚠️ warnings: {', '.join(summary['warning_entities'])}")

    if trade:
        body.append(f"")
        body.append(f"📈 交易: {trade.get('trade_count',0)}笔成交 / {trade.get('reject_count',0)}笔拒绝")

    body += ["", "---"]

    if summary["red_alert"]:
        body += [
            f"🔴 **red_alert**: {', '.join(summary['red_alert_reasons'])}",
            f"⚠️ 需人工介入",
        ]
    elif summary["warning_entities"]:
        body += ["⚠️ 可运行，建议检查 warning 实体", "✅ 可保持 Phase-1.9B"]
    else:
        body += ["✅ 全部正常", "✅ 可保持 Phase-1.9B 继续运行"]

    feishu("\n".join(body), "ai_usage_daily")

    # red_alert 额外推送
    if summary["red_alert"]:
        feishu(
            f"🚨 【red_alert】AI Usage 异常\n"
            f"日期：{yesterday}\n"
            f"原因：\n" + "\n".join(f"  • {r}" for r in summary["red_alert_reasons"]),
            "ai_usage_red_alert"
        )

# =============================================================================
# 8. 主流程
# =============================================================================
def daily_report():
    yesterday = (date.today() - timedelta(days=1))
    print(f"[AI Usage] 生成 {yesterday} 日报...")

    report = generate_daily_report(yesterday)

    # 保存 JSON
    json_path = MONITORING_DIR / "ai_usage_daily.json"
    save_json(json_path, report)

    # 保存 Markdown
    md = generate_markdown(report)
    md_path = REPORTS_DIR / f"ai_usage_daily_{yesterday}.md"
    md_path.write_text(md)

    print(f"[AI Usage] JSON: {json_path}")
    print(f"[AI Usage] MD: {md_path}")

    # 飞书推送
    feishu_daily_report(report)

    print(f"[AI Usage] ✅ 日报完成")
    print(f"[AI Usage] red_alert={report['summary']['red_alert']}")
    if report["summary"]["red_alert"]:
        for r in report["summary"]["red_alert_reasons"]:
            print(f"  → {r}")

    return report

# =============================================================================
# 入口
# =============================================================================
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--daily", action="store_true", help="生成每日报告")
    args = parser.parse_args()

    if args.daily:
        daily_report()
    else:
        # 直接运行生成昨天报告
        daily_report()
