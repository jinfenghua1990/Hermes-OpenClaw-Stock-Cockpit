#!/bin/bash
# ============================================================
# Phase-1.6 cron #1: OpenClaw 数据抓取
# 调度时间: 08:20 / 10:25 / 13:25 / 15:20
# 前置: 无
# 后置: robot-3 feature_engine.sh
# ============================================================
set -e

CRON_BASE="/Users/gino/project_ai_trading"
source "${CRON_BASE}/cron/scripts/cron_utils.sh"

STAGE="openclaw_fetch"
TIMESTAMP=$(date '+%Y-%m-%dT%H:%M:%S')
LOG="${CRON_BASE}/cron/logs/openclaw_$(date '+%Y%m%d_%H%M').log"

log_info "========== ${STAGE} 开始 =========="
log_info "时间: ${TIMESTAMP}"

# 记录到日志文件
exec > >(tee -a "${LOG}")
exec 2>&1

# 检查候选股列表
STOCKS_FILE="${CRON_BASE}/configs/candidate_stocks.json"
if [ ! -f "${STOCKS_FILE}" ]; then
    log_warn "候选股列表不存在，使用默认5只"
fi

# 候选股
STOCKS=("301282:金禄电子" "300476:胜宏科技" "002130:沃尔核材" "603629:利通电子" "002463:沪电股份")
MX_DATA="/Users/gino/.hermes/skills/mx-data/mx_data.py"
OUT_DIR="/Users/gino/mx_data_output"

# 清理旧数据（只清理当天数据避免混淆）
today=$(date '+%Y%m%d')
for stock in "${STOCKS[@]}"; do
    code="${stock%%:*}"
    rm -f ${OUT_DIR}/mx_data_*${code}*_${today}* 2>/dev/null || true
done

# 抓取所有股票数据（每查询间隔5秒避免112）
success=0; fail=0
for stock in "${STOCKS[@]}"; do
    code="${stock%%:*}"
    name="${stock##*:}"
    log_info "正在获取 ${name}(${code})..."
    
    # 并行抓多个指标
    python3 "${MX_DATA}" "${name} ${code} MA5 MA20 RSI 量比" "${OUT_DIR}" 2>&1 | tail -2
    sleep 5
    python3 "${MX_DATA}" "${name} ${code} 最低价 最高价 开盘价" "${OUT_DIR}" 2>&1 | tail -2
    sleep 5
    python3 "${MX_DATA}" "${name} ${code} 昨收" "${OUT_DIR}" 2>&1 | tail -2
    sleep 5
    python3 "${MX_DATA}" "${name} ${code} 收盘价 10日" "${OUT_DIR}" 2>&1 | tail -2
    sleep 5
    python3 "${MX_DATA}" "${name} ${code} 最新价" "${OUT_DIR}" 2>&1 | tail -2
    sleep 5
    
    # 检查是否成功
    raw_count=$(ls ${OUT_DIR}/mx_data_*${code}*_raw.json 2>/dev/null | wc -l | tr -d ' ')
    if [ "$raw_count" -gt 0 ]; then
        log_info "✅ ${name} 获取成功 (${raw_count} 个文件)"
        success=$((success+1))
    else
        log_warn "⚠️ ${name} 未获取到数据"
        fail=$((fail+1))
    fi
    sleep 3
done

log_info "========== ${STAGE} 完成 =========="
log_info "成功: ${success}/${#STOCKS[@]}, 失败: ${fail}"

# 更新状态
update_status "${TIMESTAMP}"

if [ $fail -eq ${#STOCKS[@]} ]; then
    abort_pipeline "${STAGE}" "全部股票数据获取失败"
fi

log_info "✅ ${STAGE} 成功，下一步: feature_engine.sh"
