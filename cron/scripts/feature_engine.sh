#!/bin/bash
# ============================================================
# Phase-1.6 cron #2: robot-3 Feature Engine
# 调度时间: 08:25 / 10:28 / 13:28 / 15:25
# 前置: openclaw_fetch.sh
# 后置: main_aggregate.sh 或 robot4_match.sh + robot5_risk.sh
# ============================================================
set -e

CRON_BASE="/Users/gino/project_ai_trading"
source "${CRON_BASE}/cron/scripts/cron_utils.sh"

STAGE="feature_engine"
TIMESTAMP=$(date '+%Y-%m-%dT%H:%M:%S')
LOG="${CRON_BASE}/cron/logs/feature_$(date '+%Y%m%d_%H%M').log"

log_info "========== ${STAGE} 开始 =========="
exec > >(tee -a "${LOG}")
exec 2>&1

FEATURE_SCRIPT="${CRON_BASE}/feature_engine.py"
FEATURES_OUT="${CRON_BASE}/features/daily_features.json"

# 检查 raw.json 是否存在
raw_count=$(ls /Users/gino/mx_data_output/*_raw.json 2>/dev/null | wc -l | tr -d ' ')
log_info "当前 raw.json 数量: ${raw_count}"
if [ "$raw_count" -eq 0 ]; then
    abort_pipeline "${STAGE}" "raw.json 为空，请先运行 openclaw_fetch.sh"
fi

# 运行 Feature Engine
log_info "正在运行 Feature Engine..."
python3 "${FEATURE_SCRIPT}" > /dev/null 2>&1
result=$?

if [ $result -ne 0 ]; then
    abort_pipeline "${STAGE}" "Feature Engine 运行失败 (exit ${result})"
fi

# 检查输出
if [ ! -f "${FEATURES_OUT}" ]; then
    abort_pipeline "${STAGE}" "daily_features.json 未生成"
fi

# 数据质量检查
quality=$(check_data_quality)
log_info "数据质量: ${quality}"

if [ "$quality" != "DATA_QUALITY_OK" ]; then
    log_warn "数据质量异常: ${quality}"
    # 写入警告但不中断（因为全量中断太严格）
    log_cron_error "${STAGE}" "数据质量: ${quality}" "true"
fi

# 统计有效数据
python3 - "${FEATURES_OUT}" <<'PY'
import json, sys
path = sys.argv[1]
with open(path) as f: d = json.load(f)
valid = sum(1 for s in d.get("stocks",[]) if s["indicators"].get("RSI",0) > 0)
total = len(d.get("stocks",[]))
print(f"有效数据: {valid}/{total}")
PY

log_info "========== ${STAGE} 完成 =========="
update_status "${TIMESTAMP}"
log_info "✅ ${STAGE} 成功"

# Runtime Event
source "${CRON_BASE}/runtime_events/log_event.sh"
quality="$(check_data_quality)"
log_event "feature_engine" "execution_layer" "success" "features written: raw=${raw_count}, quality=${quality}"
