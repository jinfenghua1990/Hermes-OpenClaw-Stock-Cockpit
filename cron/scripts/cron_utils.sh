#!/bin/bash
# ============================================================
# Phase-1.6 cron 工具库
# 包含: 日志记录 / 错误写入 / 数据质量检查 / 中断控制
# ============================================================

CRON_BASE="/Users/gino/project_ai_trading"
STATUS_DIR="${CRON_BASE}/cron/status"
ERROR_FILE="${STATUS_DIR}/cron_errors.jsonl"
STAGE_FILE="${STATUS_DIR}/cron_status.json"

RED='\033[0;31m'; YEL='\033[1;33m'; GRN='\033[0;32m'; NC='\033[0m'

log_info()  { echo -e "${GRN}[$(date '+%H:%M:%S')]${NC} $1"; }
log_warn()  { echo -e "${YEL}[$(date '+%H:%M:%S')] WARN:${NC} $1"; }
log_error() { echo -e "${RED}[$(date '+%H:%M:%S')] ERROR:${NC} $1"; }

log_cron_error() {
    stage="$1"; err="$2"; recoverable="${3:-true}"
    ts=$(date '+%Y-%m-%dT%H:%M:%S')
    echo "{\"timestamp\":\"${ts}\",\"stage\":\"${stage}\",\"error\":\"${err//\"/\\\"}\",\"recoverable\":${recoverable}}" >> "${ERROR_FILE}"
}

update_status() {
    last_run="$1"
    python3 "${CRON_BASE}/cron/scripts/_update_status.py" "${STAGE_FILE}" "${last_run}"
}

check_data_quality() {
    features_file="${CRON_BASE}/features/daily_features.json"
    if [ ! -f "${features_file}" ]; then
        log_error "daily_features.json 不存在"
        echo "DATA_QUALITY_WARNING"
        return 1
    fi
    result=$(python3 "${CRON_BASE}/cron/scripts/_check_quality.py" "${features_file}" 2>&1)
    ret=$?
    if [ $ret -eq 2 ]; then
        echo "DATA_QUALITY_WARNING: ${result}"
        return 1
    elif [ $ret -ne 0 ]; then
        echo "DATA_QUALITY_ERROR: ${result}"
        return 1
    fi
    echo "DATA_QUALITY_OK"
    return 0
}

abort_pipeline() {
    stage="$1"; err="$2"
    log_error "${stage} 失败: ${err}"
    log_cron_error "${stage}" "${err}"
    update_status "FAILED:${stage}"
    exit 1
}
