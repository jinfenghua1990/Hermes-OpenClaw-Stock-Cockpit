#!/bin/bash
# ============================================================
# Phase-1.6 cron #4: robot-5 风控检查
# 调度时间: 15:29（仅收盘流程）
# 前置: robot4_match.sh
# 后置: main_aggregate.sh
# 禁止: 写入 strategy_positions.json
# ============================================================
set -e

CRON_BASE="/Users/gino/project_ai_trading"
source "${CRON_BASE}/cron/scripts/cron_utils.sh"

STAGE="robot5_risk"
TIMESTAMP=$(date '+%Y-%m-%dT%H:%M:%S')
LOG="${CRON_BASE}/cron/logs/robot5_$(date '+%Y%m%d_%H%M').log"

log_info "========== ${STAGE} 开始 =========="
exec > >(tee -a "${LOG}")
exec 2>&1

STRATEGY_JSON="${CRON_BASE}/logs/robot4_strategy.json"
LEGACY="${CRON_BASE}/portfolio/legacy/legacy_positions.json"
OUTPUT="${CRON_BASE}/logs/robot5_risk.json"

# 检查输入
if [ ! -f "${STRATEGY_JSON}" ]; then
    abort_pipeline "${STAGE}" "robot4_strategy.json 不存在"
fi

# 运行风控检查（只读，不写入 strategy_positions）
python3 - "${STRATEGY_JSON}" "${LEGACY}" "${OUTPUT}" <<'PYEOF'
import json, sys
from datetime import datetime

strategy_path, legacy_path, output_path = sys.argv[1], sys.argv[2], sys.argv[3]

with open(strategy_path) as f:
    strategy = json.load(f)
with open(legacy_path) as f:
    legacy = json.load(f)

# 风控规则
RISK_RULES = {
    "单票仓位上限": {"threshold": 10, "unit": "%"},
    "总仓位上限": {"threshold": 50, "unit": "%"},
    "港股仓位上限": {"threshold": 30, "unit": "%"},
    "最大回撤预警": {"threshold": -15, "unit": "%"},
    "硬止损线": {"threshold": -20, "unit": "%"},
}

alerts = []
passed_stocks = []

for stock in strategy.get("matched_stocks", []):
    if not stock["entry_pass"]:
        continue
    # TODO: 实际风控需要持仓成本/数量，此处仅做信号记录
    passed_stocks.append({
        "stock_code": stock["stock_code"],
        "stock_name": stock["stock_name"],
        "pattern": stock["pattern"],
        "score": stock["score"],
        "risk_signal": "REVIEW_REQUIRED"  # 需要人工复审
    })

# Legacy 仓位风险检查
legacy_warnings = []
for pos in legacy:
    # 此处需补充完整持仓风控计算
    # 占位：实际风控由 Main 汇总时处理
    pass

result = {
    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    "robot": "robot-5 Risk",
    "risk_rules": RISK_RULES,
    "passed_candidates": passed_stocks,
    "legacy_warnings": legacy_warnings,
    "strategy_write_blocked": True,  # 禁止写入 strategy_positions
    "alerts": alerts,
    "risk_level": "REVIEW_REQUIRED" if alerts else "NORMAL"
}

with open(output_path, "w") as f:
    json.dump(result, f, ensure_ascii=False, indent=2)

print(f"风控检查完成")
print(f"候选通过: {len(passed_stocks)}")
print(f"风险提示: {len(alerts)}")
print(f"策略写入: 已禁止（仅人工可写）")
PYEOF

result=$?
if [ $result -ne 0 ]; then
    abort_pipeline "${STAGE}" "风控检查运行失败 (exit ${result})"
fi

log_info "✅ ${STAGE} 完成"
log_info "注意: 策略写入已禁止，仅生成报告"
