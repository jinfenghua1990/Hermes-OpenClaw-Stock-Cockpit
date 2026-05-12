#!/usr/bin/env bash
# heartbeat_monitor.sh - Phase-1.6 系统心跳监控
# 每30分钟执行，仅验证系统稳定性
# 禁止用于交易决策

BASE="$HOME/project_ai_trading"
MONITOR_DIR="$BASE/system_monitor"
STATUS_FILE="$MONITOR_DIR/system_status.json"
LOG_FILE="$MONITOR_DIR/heartbeat.log"
SCHEDULER_LOG="$BASE/cron/logs/scheduler.log"

mkdir -p "$MONITOR_DIR"

now=$(date '+%Y-%m-%d %H:%M:%S')
now_ts=$(date +%s)

# ── Scheduler 状态 ────────────────────────────────────
if [ -f "$SCHEDULER_LOG" ]; then
    last_line=$(tail -1 "$SCHEDULER_LOG")
    scheduler_last=$(echo "$last_line" | grep -oE '^[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}' | tail -1)
    scheduler_status=$(echo "$last_line" | grep -q "✓" && echo "ok" || echo "error")
else
    scheduler_last="N/A"
    scheduler_status="no_log"
fi

# ── Cron 错误计数 ────────────────────────────────────
if [ -f "$SCHEDULER_LOG" ]; then
    cron_errors=$(tail -50 "$SCHEDULER_LOG" 2>/dev/null | grep -cE "error|failed|ERROR" 2>/dev/null || echo "0")
    cron_jobs=$(tail -20 "$SCHEDULER_LOG" 2>/dev/null | grep -oE '\[scheduled job [^]]+\]' | sort -u | wc -l | tr -d ' ')
else
    cron_errors=0
    cron_jobs=0
fi

# ── 数据源最后执行时间 ────────────────────────────────────
openclaw_last="N/A"
[ -f "$SCHEDULER_LOG" ] && openclaw_last=$(grep "openclaw_fetch" "$SCHEDULER_LOG" 2>/dev/null | tail -1 | grep -oE '^[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}')

feature_last="N/A"
[ -f "$SCHEDULER_LOG" ] && feature_last=$(grep -E "feature_engine|Feature Engine" "$SCHEDULER_LOG" 2>/dev/null | tail -1 | grep -oE '^[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}')

# ── 报告数量 ────────────────────────────────────
reports_pre_market=$(find "$BASE/reports/pre_market" -name "*.json" -type f 2>/dev/null | wc -l | tr -d ' ')
reports_intraday=$(find "$BASE/reports/intraday" -name "*.json" -type f 2>/dev/null | wc -l | tr -d ' ')
reports_daily=$(find "$BASE/reports/daily_review" -name "*.json" -type f 2>/dev/null | wc -l | tr -d ' ')

# ── 关键文件检查 ────────────────────────────────────
file_age() {
    local f="$1"
    [ -f "$f" ] && echo $(($now_ts - $(stat -f "%m" "$f" 2>/dev/null || stat -c "%Y" "$f" 2>/dev/null))) || echo "null"
}

file_exists() {
    [ -f "$1" ] && echo "true" || echo "false"
}

# ── 输出 JSON（Python 确保格式） ─────────────────────────
python3 - "$scheduler_last" "$scheduler_status" "$cron_errors" "$cron_jobs" \
    "$openclaw_last" "$feature_last" \
    "$reports_pre_market" "$reports_intraday" "$reports_daily" \
    "$BASE" "$now" <<'PYEOF'
import json, sys, subprocess
from pathlib import Path

scheduler_last  = sys.argv[1]
scheduler_status = sys.argv[2]
cron_errors = int(sys.argv[3])
cron_jobs = int(sys.argv[4])
openclaw_last = sys.argv[5]
feature_last = sys.argv[6]
reports_pre_market = int(sys.argv[7])
reports_intraday = int(sys.argv[8])
reports_daily = int(sys.argv[9])
base = sys.argv[10]
now = sys.argv[11]
now_ts = int(subprocess.check_output(["date", "+%s"]).strip())

def file_status(f):
    p = Path(f)
    if p.exists():
        age = now_ts - int(p.stat().st_mtime)
        return {"path": f, "exists": True, "age_seconds": age, "status": "fresh"}
    return {"path": f, "exists": False, "age_seconds": None, "status": "missing"}

files = [
    file_status(f"{base}/reports/pre_market/pre_market_report.json"),
    file_status(f"{base}/reports/intraday/intraday_signal_am.json"),
    file_status(f"{base}/cron/logs/scheduler.log"),
    file_status(f"{base}/configs/candidate_stocks.json"),
    file_status(f"{base}/configs/risk_rules.json"),
    file_status(f"{base}/configs/feishu_webhook.json"),
]

status = {
    "report_type": "system_heartbeat",
    "timestamp": now,
    "phase": "Phase-1.6 OBSERVE_ONLY",
    "heartbeat_purpose": "系统稳定性验证 | 禁止用于交易决策",
    "scheduler": {
        "last_entry": scheduler_last,
        "status": scheduler_status
    },
    "cron_jobs": {
        "active_count": cron_jobs,
        "recent_errors": cron_errors
    },
    "data_sources": {
        "openclaw_fetch_last": openclaw_last,
        "feature_engine_last": feature_last
    },
    "reports": {
        "pre_market_count": reports_pre_market,
        "intraday_count": reports_intraday,
        "daily_review_count": reports_daily
    },
    "files": files,
    "monitoring": {
        "heartbeat_interval": "30m",
        "next_allowed_trade_ref": [
            "reports/pre_market/",
            "reports/intraday/",
            "reports/daily_review/"
        ]
    },
    "trade_prohibited": {
        "reason": "Heartbeat数据仅用于系统稳定性验证",
        "禁止": [
            "买入判断", "卖出判断",
            "strategy_positions写入",
            "baseline统计", "风控交易决策"
        ],
        "正式交易参考": [
            "reports/pre_market/",
            "reports/intraday/",
            "reports/daily_review/"
        ]
    }
}

status_file = Path(base) / "system_monitor" / "system_status.json"
status_file.write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

# heartbeat log
log_file = Path(base) / "system_monitor" / "heartbeat.log"
log_file.write_text(f"[{now}] heartbeat OK (scheduler={scheduler_status}, errors={cron_errors})\n", encoding="utf-8")

print("OK")
PYEOF
