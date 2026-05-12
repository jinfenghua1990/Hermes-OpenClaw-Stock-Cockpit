#!/bin/bash
# ============================================================
# Phase-1.6 调度器 - launchd StartInterval 60秒轮询
# 每分钟检查时间，到点执行对应脚本
# ============================================================
CRON_BASE="/Users/gino/project_ai_trading"
STATUS_FILE="${CRON_BASE}/cron/status/cron_status.json"
LOG="${CRON_BASE}/cron/logs/scheduler.log"

MINUTES=$(date '+%H%M')
DOW=$(date '+%u')
NOW=$(date '+%Y-%m-%d %H:%M')

# 仅工作日
if [ "$DOW" -gt 5 ]; then
    exit 0
fi

log() { echo "${NOW} [scheduler] $1" >> "$LOG"; }

# 读取上次运行时间，避免同一分钟重复执行
LAST_RUN_FILE="${CRON_BASE}/cron/status/last_run_time"
last_run=$(cat "${LAST_RUN_FILE}" 2>/dev/null || echo "")
current_min="${NOW:0:16}"

if [ "$last_run" = "$current_min" ]; then
    exit 0
fi
echo "$current_min" > "${LAST_RUN_FILE}"

# ---- 盘前 ----
if [ "$MINUTES" = "0820" ]; then
    log "→ [08:20] openclaw_fetch"
    /bin/bash "${CRON_BASE}/cron/scripts/openclaw_fetch.sh" >> "${CRON_BASE}/cron/logs/cron_stdout.log" 2>&1
    log "✓ [08:20] done"
fi

if [ "$MINUTES" = "0825" ]; then
    log "→ [08:25] feature_engine"
    /bin/bash "${CRON_BASE}/cron/scripts/feature_engine.sh" >> "${CRON_BASE}/cron/logs/cron_stdout.log" 2>&1
    log "✓ [08:25] done"
fi

if [ "$MINUTES" = "0830" ]; then
    log "→ [08:30] pre_market report"
    /bin/bash "${CRON_BASE}/cron/scripts/openclaw_fetch.sh" >> "${CRON_BASE}/cron/logs/cron_stdout.log" 2>&1
    /bin/bash "${CRON_BASE}/cron/scripts/feature_engine.sh" >> "${CRON_BASE}/cron/logs/cron_stdout.log" 2>&1
    python3 "${CRON_BASE}/scripts/position_adapter.py" >> "${CRON_BASE}/cron/logs/cron_stdout.log" 2>&1
    /bin/bash "${CRON_BASE}/cron/scripts/main_aggregate.sh" pre_market >> "${CRON_BASE}/cron/logs/cron_stdout.log" 2>&1
    log "✓ [08:30] pre_market done"
    python3 "${CRON_BASE}/cron/scripts/notification_router.py" pre_market &
fi

# ---- 上午日内 ----
if [ "$MINUTES" = "1025" ]; then
    log "→ [10:25] openclaw_fetch"
    /bin/bash "${CRON_BASE}/cron/scripts/openclaw_fetch.sh" >> "${CRON_BASE}/cron/logs/cron_stdout.log" 2>&1
    log "✓ [10:25] done"
fi

if [ "$MINUTES" = "1028" ]; then
    log "→ [10:28] feature_engine"
    /bin/bash "${CRON_BASE}/cron/scripts/feature_engine.sh" >> "${CRON_BASE}/cron/logs/cron_stdout.log" 2>&1
    log "✓ [10:28] done"
fi

if [ "$MINUTES" = "1030" ]; then
    log "→ [10:30] intraday_am"
    /bin/bash "${CRON_BASE}/cron/scripts/main_aggregate.sh" intraday_am >> "${CRON_BASE}/cron/logs/cron_stdout.log" 2>&1
    log "✓ [10:30] intraday_am done"
fi

# ---- 下午日内 ----
if [ "$MINUTES" = "1325" ]; then
    log "→ [13:25] openclaw_fetch"
    /bin/bash "${CRON_BASE}/cron/scripts/openclaw_fetch.sh" >> "${CRON_BASE}/cron/logs/cron_stdout.log" 2>&1
    log "✓ [13:25] done"
fi

if [ "$MINUTES" = "1328" ]; then
    log "→ [13:28] feature_engine"
    /bin/bash "${CRON_BASE}/cron/scripts/feature_engine.sh" >> "${CRON_BASE}/cron/logs/cron_stdout.log" 2>&1
    log "✓ [13:28] done"
fi

if [ "$MINUTES" = "1330" ]; then
    log "→ [13:30] intraday_pm"
    /bin/bash "${CRON_BASE}/cron/scripts/main_aggregate.sh" intraday_pm >> "${CRON_BASE}/cron/logs/cron_stdout.log" 2>&1
    log "✓ [13:30] intraday_pm done"
fi

# ---- 收盘 ----
if [ "$MINUTES" = "1520" ]; then
    log "→ [15:20] openclaw_fetch"
    /bin/bash "${CRON_BASE}/cron/scripts/openclaw_fetch.sh" >> "${CRON_BASE}/cron/logs/cron_stdout.log" 2>&1
    log "✓ [15:20] done"
fi

if [ "$MINUTES" = "1525" ]; then
    log "→ [15:25] feature_engine"
    /bin/bash "${CRON_BASE}/cron/scripts/feature_engine.sh" >> "${CRON_BASE}/cron/logs/cron_stdout.log" 2>&1
    log "✓ [15:25] done"
fi

if [ "$MINUTES" = "1528" ]; then
    log "→ [15:28] robot4_match"
    /bin/bash "${CRON_BASE}/cron/scripts/robot4_match.sh" >> "${CRON_BASE}/cron/logs/cron_stdout.log" 2>&1
    log "✓ [15:28] robot4 done"
fi

if [ "$MINUTES" = "1529" ]; then
    log "→ [15:29] robot5_risk"
    /bin/bash "${CRON_BASE}/cron/scripts/robot5_risk.sh" >> "${CRON_BASE}/cron/logs/cron_stdout.log" 2>&1
    log "✓ [15:29] robot5 done"
fi

if [ "$MINUTES" = "1530" ]; then
    log "→ [15:30] daily_review"
    python3 "${CRON_BASE}/scripts/position_adapter.py" >> "${CRON_BASE}/cron/logs/cron_stdout.log" 2>&1
    /bin/bash "${CRON_BASE}/cron/scripts/main_aggregate.sh" daily_review >> "${CRON_BASE}/cron/logs/cron_stdout.log" 2>&1
    log "✓ [15:30] daily_review done"
    python3 "${CRON_BASE}/cron/scripts/notification_router.py" daily_review &
fi
