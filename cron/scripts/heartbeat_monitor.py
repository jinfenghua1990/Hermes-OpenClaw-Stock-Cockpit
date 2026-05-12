#!/usr/bin/env python3
"""heartbeat_monitor.py - Phase-1.6 Heartbeat (10min)
只检查系统是否活着，不生成报告，不调用大模型。
"""
import json, subprocess, re
from pathlib import Path
from datetime import datetime

BASE = Path.home() / "project_ai_trading"
OUT_DIR = BASE / "system_monitor"
OUT_FILE = OUT_DIR / "system_status.json"
LOG_FILE = OUT_DIR / "heartbeat.log"
SCHEDULER_LOG = BASE / "cron/logs/scheduler.log"

OUT_DIR.mkdir(parents=True, exist_ok=True)
now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
now_ts = int(subprocess.check_output(["date", "+%s"]).strip())

# ── Scheduler 存活检查 ────────────────────────────────────
if SCHEDULER_LOG.exists():
    lines = SCHEDULER_LOG.read_text(encoding="utf-8").splitlines()
    last_line = lines[-1] if lines else ""
    m = re.search(r'^(\d{4}-\d{2}-\d{2} \d{2}:\d{2})', last_line)
    scheduler_last = m.group(1) if m else "N/A"
    scheduler_status = "ok" if "✓" in last_line else "error"
    cron_errors = sum(1 for l in lines[-50:] if re.search(r'error|failed|ERROR', l))
else:
    scheduler_last = "N/A"
    scheduler_status = "no_log"
    cron_errors = 0

# ── OpenClaw 最近执行时间 ────────────────────────────────────
content = SCHEDULER_LOG.read_text(encoding="utf-8") if SCHEDULER_LOG.exists() else ""
openclaw_last = "N/A"
for line in reversed(content.splitlines()):
    if "openclaw_fetch" in line:
        m = re.search(r'^(\d{4}-\d{2}-\d{2} \d{2}:\d{2})', line)
        openclaw_last = m.group(1) if m else "N/A"
        break

feature_last = "N/A"
for line in reversed(content.splitlines()):
    if re.search(r'feature_engine|Feature Engine', line):
        m = re.search(r'^(\d{4}-\d{2}-\d{2} \d{2}:\d{2})', line)
        feature_last = m.group(1) if m else "N/A"
        break

# ── 关键文件状态 ────────────────────────────────────
def file_status(f):
    if f.exists():
        age = now_ts - int(f.stat().st_mtime)
        return {"path": str(f), "exists": True, "age_seconds": age, "status": "fresh"}
    return {"path": str(f), "exists": False, "age_seconds": None, "status": "missing"}

files = [
    file_status(BASE / "reports/pre_market/pre_market_report.json"),
    file_status(BASE / "reports/intraday/intraday_signal_am.json"),
    file_status(SCHEDULER_LOG),
    file_status(BASE / "configs/candidate_stocks.json"),
    file_status(BASE / "configs/feishu_webhook.json"),
]

# ── 输出 ────────────────────────────────────
status = {
    "report_type": "heartbeat",
    "timestamp": now,
    "phase": "Phase-1.6 OBSERVE_ONLY",
    "scheduler": {"last_entry": scheduler_last, "status": scheduler_status},
    "cron_errors": cron_errors,
    "data_sources": {
        "openclaw_fetch_last": openclaw_last,
        "feature_engine_last": feature_last
    },
    "files": files,
    "trade_reference": ["reports/pre_market/", "reports/intraday/", "reports/daily_review/"],
    "prohibited": ["买入判断", "卖出判断", "strategy_positions写入", "自动交易", "baseline修改"]
}

OUT_FILE.write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
LOG_FILE.write_text(f"[{now}] heartbeat OK (scheduler={scheduler_status})\n", encoding="utf-8")
print("OK")
