#!/bin/bash
# ============================================================
# Phase-1.6 cron #3: robot-4 模式匹配
# 调度时间: 15:28（仅收盘流程）
# 前置: feature_engine.sh（收盘版）
# 后置: robot5_risk.sh
# ============================================================
set -e

CRON_BASE="/Users/gino/project_ai_trading"
source "${CRON_BASE}/cron/scripts/cron_utils.sh"

STAGE="robot4_pattern_match"
TIMESTAMP=$(date '+%Y-%m-%dT%H:%M:%S')
LOG="${CRON_BASE}/cron/logs/robot4_$(date '+%Y%m%d_%H%M').log"

log_info "========== ${STAGE} 开始 =========="
exec > >(tee -a "${LOG}")
exec 2>&1

FEATURES="${CRON_BASE}/features/daily_features.json"
OUTPUT="${CRON_BASE}/logs/robot4_strategy.json"

# 检查输入
if [ ! -f "${FEATURES}" ]; then
    abort_pipeline "${STAGE}" "daily_features.json 不存在，请先运行 feature_engine.sh"
fi

# 运行模式匹配
log_info "正在运行 robot-4 模式匹配..."
python3 - "${FEATURES}" "${OUTPUT}" <<'PYEOF'
import json, sys
from datetime import datetime

features_path, output_path = sys.argv[1], sys.argv[2]

with open(features_path) as f:
    d = json.load(f)

def match_pattern(code, name, ind):
    rsi = ind.get("RSI", 0)
    ma5 = ind.get("MA5", 0)
    ma20 = ind.get("MA20", 0)
    ma20_trend = ind.get("MA20趋势", "unknown")
    vol_ratio = ind.get("量比", 0)
    lower_shadow = ind.get("下影线长度", 0)
    daily_change = ind.get("日涨幅", 0)
    prev_change = ind.get("昨日涨幅", 0)
    prev_limit_up = ind.get("昨日涨停", False)
    ma20_dist = ind.get("股价距MA20距离", 0)
    open_price = ind.get("开盘价", 0)
    close = ind.get("最新价", 0)
    ma5_above_ma20 = ind.get("MA5大于MA20", False)
    
    scores, reasons, risk_notes = {}, {}, {}
    
    # 模式1: 回踩止跌型
    s1 = 0; r1 = []; rn1 = []
    if rsi < 40: s1 += 3; r1.append(f"RSI={rsi:.1f}<40")
    if lower_shadow > 2: s1 += 2; r1.append(f"下影={lower_shadow}%>2%")
    if daily_change < -2: s1 += 2; r1.append(f"日跌幅={daily_change}%<-2%")
    if ma20_trend == "down": s1 -= 3; rn1.append("MA20↓")
    if s1 >= 3: scores["回踩止跌型"]=s1; reasons["回踩止跌型"]=r1; risk_notes["回踩止跌型"]=rn1
    
    # 模式2: 突破启动型
    s2 = 0; r2 = []; rn2 = []
    if ma5_above_ma20: s2 += 2; r2.append(f"MA5>{ma20:.1f}")
    else: s2 -= 2; rn2.append("MA5<MA20")
    if 40 <= rsi <= 70: s2 += 2; r2.append(f"RSI={rsi:.1f}(40~70)")
    elif rsi > 70: s2 -= 2; rn2.append(f"RSI={rsi:.1f}>70过热")
    if vol_ratio > 1.2: s2 += 1; r2.append(f"量比={vol_ratio:.2f}>1.2")
    if abs(ma20_dist) < 15: s2 += 1; r2.append(f"距MA20={ma20_dist:.1f}%<15%")
    else: s2 -= 1; rn2.append(f"距MA20={ma20_dist:.1f}%>15%")
    if prev_change < 6: s2 += 1; r2.append(f"昨涨={prev_change}%<6%")
    else: s2 -= 1; rn2.append(f"昨涨={prev_change}%≥6%")
    if s2 >= 4: scores["突破启动型"]=s2; reasons["突破启动型"]=r2; risk_notes["突破启动型"]=rn2
    
    # 模式3: 小阳启动型
    s3 = 0; r3 = []; rn3 = []
    if 1 <= daily_change <= 5: s3 += 3; r3.append(f"日涨幅={daily_change}%(1~5%)")
    if lower_shadow > 0.5: s3 += 2; r3.append(f"下影={lower_shadow}%>0.5%")
    if 30 <= rsi <= 55: s3 += 2; r3.append(f"RSI={rsi:.1f}(30~55)")
    elif rsi < 30: s3 += 1; r3.append(f"RSI={rsi:.1f}<30弱")
    if ma5_above_ma20: s3 += 1; r3.append("MA5>MA20")
    if s3 >= 5: scores["小阳启动型"]=s3; reasons["小阳启动型"]=r3; risk_notes["小阳启动型"]=rn3
    
    # 模式4: 2波启动型
    s4 = 0; r4 = []; rn4 = []
    if prev_limit_up: s4 += 3; r4.append("昨涨停")
    else: s4 -= 2; rn4.append("昨未涨停")
    if ma20_trend == "up": s4 += 2; r4.append("MA20↑")
    elif ma20_trend == "flat": s4 += 1; r4.append("MA20平")
    else: s4 -= 1; rn4.append(f"MA20{ma20_trend}")
    if 40 <= rsi <= 70: s4 += 2; r4.append(f"RSI={rsi:.1f}(40~70)")
    if open_price > close > 0: s4 += 1; r4.append("高开")
    if s4 >= 5: scores["2波启动型"]=s4; reasons["2波启动型"]=r4; risk_notes["2波启动型"]=rn4
    
    if not scores: return False, None, 0, [], []
    best = max(scores, key=scores.get)
    return True, best, scores[best], reasons[best], risk_notes.get(best,[])

results = {
    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    "robot": "robot-4 Strategy",
    "data_source": "features/daily_features.json",
    "baseline": "four-patterns-v1.0",
    "matched_stocks": []
}

for s in d.get("stocks", []):
    code, name = s["stock_code"], s["stock_name"]
    ind = s["indicators"]
    matched, pattern, score, pat_reasons, risk_notes = match_pattern(code, name, ind)
    entry = {
        "stock_code": code, "stock_name": name,
        "matched": matched, "pattern": pattern, "score": score,
        "pattern_reasons": pat_reasons, "risk_notes": risk_notes,
        "entry_pass": matched and score >= 5,
        "indicators_summary": {
            "RSI": ind.get("RSI"), "MA5": ind.get("MA5"), "MA20": ind.get("MA20"),
            "日涨幅": ind.get("日涨幅"), "下影线": ind.get("下影线长度"),
            "量比": ind.get("量比"), "MA20距": ind.get("股价距MA20距离"),
            "MA5大于MA20": ind.get("MA5大于MA20"), "昨涨停": ind.get("昨日涨停")
        }
    }
    results["matched_stocks"].append(entry)
    status = "✅ PASS" if entry["entry_pass"] else "❌ FAIL"
    print(f"  {status} {name}({code}): {pattern or '无'} (得分:{score})")

with open(output_path, "w") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

passed = [x for x in results["matched_stocks"] if x["entry_pass"]]
print(f"\n通过候选: {len(passed)}/{len(results['matched_stocks'])}")
for x in passed:
    print(f"  ✅ {x['stock_name']} → {x['pattern']} (得分:{x['score']})")
PYEOF

result=$?
if [ $result -ne 0 ]; then
    abort_pipeline "${STAGE}" "模式匹配运行失败 (exit ${result})"
fi

log_info "✅ ${STAGE} 完成"
log_info "注意: 策略写入已禁止，仅生成报告"

# Runtime Event
source "${CRON_BASE}/runtime_events/log_event.sh"
log_event "robot4_match_sh" "execution_layer" "success" "strategy matched: result written"