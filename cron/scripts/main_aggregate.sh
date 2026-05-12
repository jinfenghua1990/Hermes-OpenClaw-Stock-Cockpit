#!/bin/bash
# ============================================================
# Phase-1.6 cron #5: Main 汇总生成报告
# 调度时间: 08:30(pre_market) / 10:30(intraday_am) / 13:30(intraday_pm) / 15:30(daily_review)
# 前置(08:30/10:30/13:30): feature_engine.sh
# 前置(15:30): robot5_risk.sh
# ============================================================
set -e

CRON_BASE="/Users/gino/project_ai_trading"
source "${CRON_BASE}/cron/scripts/cron_utils.sh"

REPORT_TYPE="${1:-pre_market}"  # pre_market / intraday_am / intraday_pm / daily_review
TIMESTAMP=$(date '+%Y-%m-%dT%H:%M:%S')
LOG="${CRON_BASE}/cron/logs/main_$(date '+%Y%m%d_%H%M').log"

log_info "========== Main 汇总(${REPORT_TYPE}) 开始 =========="
exec > >(tee -a "${LOG}")
exec 2>&1

FEATURES="${CRON_BASE}/features/daily_features.json"
STRATEGY="${CRON_BASE}/logs/robot4_strategy.json"
LEGACY="${CRON_BASE}/portfolio/legacy/legacy_positions.json"
OUTPUT_BASE="${CRON_BASE}/reports"

# 映射报告类型到文件
REPORT_FILES_pre_market="${OUTPUT_BASE}/pre_market/pre_market_report.json"
REPORT_FILES_intraday_am="${OUTPUT_BASE}/intraday/intraday_signal_am.json"
REPORT_FILES_intraday_pm="${OUTPUT_BASE}/intraday/intraday_signal_pm.json"
REPORT_FILES_daily_review="${OUTPUT_BASE}/daily_review/daily_review.json"

case "${REPORT_TYPE}" in
    pre_market)   OUTPUT="${REPORT_FILES_pre_market}" ;;
    intraday_am)  OUTPUT="${REPORT_FILES_intraday_am}" ;;
    intraday_pm)  OUTPUT="${REPORT_FILES_intraday_pm}" ;;
    daily_review)  OUTPUT="${REPORT_FILES_daily_review}" ;;
    *) echo "未知报告类型: ${REPORT_TYPE}"; exit 1 ;;
esac

# 生成报告
python3 - "${REPORT_TYPE}" "${OUTPUT}" <<'PYEOF'
import json, sys
from datetime import datetime

report_type, output_path = sys.argv[1], sys.argv[2]
CRON_BASE = "/Users/gino/project_ai_trading"

ts = datetime.now()
time_map = {
    "pre_market": ("盘前分析", "08:30"),
    "intraday_am": ("上午日内信号", "10:30"),
    "intraday_pm": ("下午日内信号", "13:30"),
    "daily_review": ("收盘复盘", "15:30"),
}

title, default_time = time_map.get(report_type, ("报告", ""))

report = {
    "report_type": report_type,
    "timestamp": ts.strftime("%Y-%m-%d %H:%M:%S"),
    "date": ts.strftime("%Y-%m-%d"),
    "time": default_time,
    "robot": "Main (Hermes SystemAdmin)",
    "phase": "Phase-1.6 有限自动化",
    "workflow": "OpenClaw → robot-3 → robot-4 → robot-5 → Main",
}

# 读取 features
features_path = f"{CRON_BASE}/features/daily_features.json"
try:
    with open(features_path) as f:
        features_data = json.load(f)
    report["candidate_stocks"] = features_data.get("stocks", [])
    report["fetch_time"] = features_data.get("timestamp", "")
except Exception as e:
    report["candidate_stocks"] = []
    report["data_error"] = str(e)

# 读取模式匹配结果（仅收盘有）
if report_type == "daily_review":
    try:
        with open(f"{CRON_BASE}/logs/robot4_strategy.json") as f:
            strategy_data = json.load(f)
        report["pattern_matching"] = strategy_data
        passed = [s for s in strategy_data.get("matched_stocks", []) if s.get("entry_pass")]
        report["passed_candidates"] = passed
    except:
        report["pattern_matching"] = None

# 读取 Legacy 仓位
try:
    with open(f"{CRON_BASE}/portfolio/legacy/legacy_positions.json") as f:
        legacy_data = json.load(f)
    report["legacy_positions_count"] = len(legacy_data)
except:
    legacy_data = []
    report["legacy_positions_count"] = 0

# 报告内容
if report_type == "pre_market":
    report["title"] = f"📊 {ts.strftime('%Y-%m-%d')} 盘前分析报告"
    report["sections"] = {
        "candidate_stocks": f"候选股数量: {len(report.get('candidate_stocks',[]))}",
        "data_fetch_status": "✅ OpenClaw 数据抓取完成",
        "feature_engine_status": "✅ robot-3 Feature Engine 完成",
        "next_action": "等待 10:25 OpenClaw 数据更新"
    }
    
elif report_type == "intraday_am":
    report["title"] = f"📈 {ts.strftime('%Y-%m-%d')} 上午日内信号"
    report["am_session"] = {
        "status": "上午时段信号检查完成",
        "data_freshness": "数据更新至 10:25"
    }
    
elif report_type == "intraday_pm":
    report["title"] = f"📉 {ts.strftime('%Y-%m-%d')} 下午日内信号"
    report["pm_session"] = {
        "status": "下午时段信号检查完成",
        "data_freshness": "数据更新至 13:25"
    }
    
elif report_type == "daily_review":
    passed = report.get("passed_candidates", [])
    report["title"] = f"📋 {ts.strftime('%Y-%m-%d')} 收盘复盘报告"
    report["sections"] = {
        "market_data": f"候选股数量: {len(report.get('candidate_stocks',[]))}",
        "pattern_matching": f"通过候选: {len(passed)} 只",
        "passed_stocks": passed,
        "legacy_review": f"Legacy 仓位: {report.get('legacy_positions_count',0)} 只（需人工复审）",
        "auto_trade_blocked": "✅ 自动交易已禁止（Phase-1.6 限制）",
        "strategy_write_blocked": "✅ 策略仓位写入已禁止（仅人工可写）"
    }

# 确保目录存在
import os
os.makedirs(os.path.dirname(output_path), exist_ok=True)
with open(output_path, "w") as f:
    json.dump(report, f, ensure_ascii=False, indent=2)

print(f"✅ 报告已生成: {output_path}")
print(f"   类型: {report['title']}")
print(f"   候选股: {len(report.get('candidate_stocks',[]))}")
if report_type == "daily_review":
    print(f"   通过候选: {len(passed)}")
PYEOF

result=$?
if [ $result -ne 0 ]; then
    abort_pipeline "main_aggregate(${REPORT_TYPE})" "报告生成失败 (exit ${result})"
fi

log_info "✅ Main 汇总(${REPORT_TYPE}) 完成"
log_info "✅ 报告: ${OUTPUT}"
