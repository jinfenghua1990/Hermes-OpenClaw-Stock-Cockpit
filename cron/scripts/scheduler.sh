#!/bin/bash
# ============================================================
# Phase-1.6 调度器 - launchd StartInterval 60秒轮询
# 每分钟检查时间，到点执行对应脚本
# ============================================================
CRON_BASE="/Users/gino/project_ai_trading"
STATUS_FILE="${CRON_BASE}/cron/status/cron_status.json"
LOG="${CRON_BASE}/cron/logs/scheduler.log"

# 加载 Runtime Event logger
source "${CRON_BASE}/runtime_events/log_event.sh"

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

# ============================================================
# 辅助：带计时执行 + 写入 Runtime Event
# ============================================================
run_with_event() {
    local module="$1"
    local layer="$2"
    local cmd="$3"
    local msg_ok="$4"
    local msg_fail="$5"

    log "→ [$MINUTES] ${module}"
    local start_ms=$(python3 -c "import time; print(int(time.time()*1000))")
    eval "$cmd" >> "${CRON_BASE}/cron/logs/cron_stdout.log" 2>&1
    local exit_code=$?
    local end_ms=$(python3 -c "import time; print(int(time.time()*1000))")
    local elapsed=$((end_ms - start_ms))

    if [ $exit_code -eq 0 ]; then
        log_event "$module" "$layer" "success" "${msg_ok}" "$elapsed"
        log "✓ [$MINUTES] ${module} done"
    else
        log_event "$module" "$layer" "error" "${msg_fail} (exit ${exit_code})" "$elapsed"
        log "✗ [$MINUTES] ${module} FAILED (exit ${exit_code})"
    fi
}

# ---- 盘前 ----
if [ "$MINUTES" = "0820" ]; then
    run_with_event "OpenClaw" "execution_layer" \
        "/bin/bash \"${CRON_BASE}/cron/scripts/openclaw_fetch.sh\"" \
        "盘前数据抓取完成" "盘前数据抓取失败"
fi

if [ "$MINUTES" = "0825" ]; then
    run_with_event "feature_engine" "execution_layer" \
        "/bin/bash \"${CRON_BASE}/cron/scripts/feature_engine.sh\"" \
        "Feature Engine 盘前计算完成" "Feature Engine 盘前计算失败"
fi

if [ "$MINUTES" = "0830" ]; then
    log "→ [08:30] pre_market 全链路"
    local start_ms=$(python3 -c "import time; print(int(time.time()*1000))")
    /bin/bash "${CRON_BASE}/cron/scripts/openclaw_fetch.sh" >> "${CRON_BASE}/cron/logs/cron_stdout.log" 2>&1
    /bin/bash "${CRON_BASE}/cron/scripts/feature_engine.sh" >> "${CRON_BASE}/cron/logs/cron_stdout.log" 2>&1
    python3 "${CRON_BASE}/scripts/position_adapter.py" >> "${CRON_BASE}/cron/logs/cron_stdout.log" 2>&1
    /bin/bash "${CRON_BASE}/cron/scripts/main_aggregate.sh" pre_market >> "${CRON_BASE}/cron/logs/cron_stdout.log" 2>&1
    local end_ms=$(python3 -c "import time; print(int(time.time()*1000))")
    log_event "report_pipeline" "execution_layer" "success" "盘前报告生成完成" $((end_ms-start_ms))
    log "✓ [08:30] pre_market done"
    python3 "${CRON_BASE}/cron/scripts/notification_router.py" pre_market &
fi

# ---- 上午日内 ----
if [ "$MINUTES" = "1025" ]; then
    run_with_event "OpenClaw" "execution_layer" \
        "/bin/bash \"${CRON_BASE}/cron/scripts/openclaw_fetch.sh\"" \
        "上午数据抓取完成" "上午数据抓取失败"
fi

if [ "$MINUTES" = "1028" ]; then
    run_with_event "feature_engine" "execution_layer" \
        "/bin/bash \"${CRON_BASE}/cron/scripts/feature_engine.sh\"" \
        "Feature Engine 上午计算完成" "Feature Engine 上午计算失败"
fi

if [ "$MINUTES" = "1030" ]; then
    local start_ms=$(python3 -c "import time; print(int(time.time()*1000))")
    /bin/bash "${CRON_BASE}/cron/scripts/main_aggregate.sh" intraday_am >> "${CRON_BASE}/cron/logs/cron_stdout.log" 2>&1
    local end_ms=$(python3 -c "import time; print(int(time.time()*1000))")
    log_event "report_pipeline" "execution_layer" "success" "上午日内报告生成" $((end_ms-start_ms))
    log "✓ [10:30] intraday_am done"
fi

# ---- 下午日内 ----
if [ "$MINUTES" = "1325" ]; then
    run_with_event "OpenClaw" "execution_layer" \
        "/bin/bash \"${CRON_BASE}/cron/scripts/openclaw_fetch.sh\"" \
        "下午数据抓取完成" "下午数据抓取失败"
fi

if [ "$MINUTES" = "1328" ]; then
    run_with_event "feature_engine" "execution_layer" \
        "/bin/bash \"${CRON_BASE}/cron/scripts/feature_engine.sh\"" \
        "Feature Engine 下午计算完成" "Feature Engine 下午计算失败"
fi

if [ "$MINUTES" = "1330" ]; then
    local start_ms=$(python3 -c "import time; print(int(time.time()*1000))")
    /bin/bash "${CRON_BASE}/cron/scripts/main_aggregate.sh" intraday_pm >> "${CRON_BASE}/cron/logs/cron_stdout.log" 2>&1
    local end_ms=$(python3 -c "import time; print(int(time.time()*1000))")
    log_event "report_pipeline" "execution_layer" "success" "下午日内报告生成" $((end_ms-start_ms))
    log "✓ [13:30] intraday_pm done"
fi

# ---- 收盘 ----
if [ "$MINUTES" = "1520" ]; then
    run_with_event "OpenClaw" "execution_layer" \
        "/bin/bash \"${CRON_BASE}/cron/scripts/openclaw_fetch.sh\"" \
        "收盘数据抓取完成" "收盘数据抓取失败"
fi

if [ "$MINUTES" = "1525" ]; then
    run_with_event "feature_engine" "execution_layer" \
        "/bin/bash \"${CRON_BASE}/cron/scripts/feature_engine.sh\"" \
        "Feature Engine 收盘计算完成" "Feature Engine 收盘计算失败"
fi

if [ "$MINUTES" = "1528" ]; then
    run_with_event "kline_update" "execution_layer" \
        "/bin/bash \"${CRON_BASE}/cron/scripts/robot4_match.sh\"" \
        "K线更新+模式匹配完成" "K线更新+模式匹配失败"
fi

if [ "$MINUTES" = "1529" ]; then
    run_with_event "audit_engine" "governance_layer" \
        "/bin/bash \"${CRON_BASE}/cron/scripts/robot5_risk.sh\"" \
        "风控审计完成" "风控审计失败"
fi

if [ "$MINUTES" = "1530" ]; then
    local start_ms=$(python3 -c "import time; print(int(time.time()*1000))")
    python3 "${CRON_BASE}/scripts/position_adapter.py" >> "${CRON_BASE}/cron/logs/cron_stdout.log" 2>&1
    /bin/bash "${CRON_BASE}/cron/scripts/main_aggregate.sh" daily_review >> "${CRON_BASE}/cron/logs/cron_stdout.log" 2>&1
    local end_ms=$(python3 -c "import time; print(int(time.time()*1000))")
    log_event "report_pipeline" "execution_layer" "success" "收盘复盘报告生成" $((end_ms-start_ms))
    log "✓ [15:30] daily_review done"
    python3 "${CRON_BASE}/cron/scripts/notification_router.py" daily_review &
fi
