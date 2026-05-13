#!/usr/bin/env python3
"""
Phase-2.6A Research Intelligence Layer
Ranking Engine — 对候选股重新评分排序，生成 Top Picks
"""
import json, os, sys
from datetime import datetime

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CANDIDATE_FILE = f"{BASE}/portfolio/candidate_rankings.json"
OBS_POOL_FILE = f"{BASE}/portfolio/observation_pool.json"
OUTPUT_DIR = f"{BASE}/reports"
TOP_PICKS_FILE = f"{OUTPUT_DIR}/top_picks.json"
WATCHLIST_FILE = f"{BASE}/paper_trading/watchlist.json"
AI_SUMMARY_FILE = f"{OUTPUT_DIR}/ai_market_summary.md"

os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(f"{BASE}/paper_trading", exist_ok=True)

# ========== 过滤规则 ==========
STOCKS_ST = {'ST', '*ST', 'ST*', 'S'}
FORBIDDEN_WORDS = {'退市', '暂停上市'}
MIN_PRICE = 2.0
MAX_PRICE = 500.0
MIN_VOLUME_RATIO = 0.5
MAX_RSI = 85
MIN_RSI = 20
MAX_OPEN_GAP = 9.7  # 高开超过9.7%过滤
YIZI_LIMIT = 9.7    # 一字板涨跌停过滤


def is_st(name: str) -> bool:
    """判断是否ST股"""
    if not name:
        return False
    for w in STOCKS_ST:
        if w in name:
            return True
    return False


def filter_candidates(candidates: list) -> list:
    """风险过滤"""
    filtered = []
    for c in candidates:
        name = c.get('股票名称', '')
        price = c.get('最新价', 0)
        rsi = c.get('RSI', 50)
        vol_ratio = c.get('量比', 1.0)
        pct = c.get('涨跌幅', 0)
        
        # ST过滤
        if is_st(name):
            continue
        # 退市过滤
        if any(w in name for w in FORBIDDEN_WORDS):
            continue
        # 价格异常
        if price <= 0 or price < MIN_PRICE or price > MAX_PRICE:
            continue
        # RSI超买
        if rsi > MAX_RSI:
            continue
        # RSI超卖但尚可
        if rsi < MIN_RSI:
            continue
        # 流动性过低
        if vol_ratio < MIN_VOLUME_RATIO:
            continue
        # 追高过滤（涨幅过大且RSI高）
        if pct > 8 and rsi > 70:
            continue
        # 高开过高
        if pct > MAX_OPEN_GAP:
            continue
        
        filtered.append(c)
    return filtered


def compute_score(c: dict) -> float:
    """
    综合评分维度（简单加权）
    """
    rsi = c.get('RSI', 50)
    vol_ratio = c.get('量比', 1.0)
    pct = c.get('涨跌幅', 0)
    ma_dist = c.get('MA5距离MA20', 0)
    score_base = c.get('综合评分', 100)
    risk = c.get('风险等级', '中')
    pattern = c.get('模式', '')
    
    # RSI位置分（40~70最优）
    if 30 <= rsi <= 45:
        rsi_score = 25  # 超卖回暖区，最优
    elif 45 < rsi <= 60:
        rsi_score = 20
    elif 60 < rsi <= 70:
        rsi_score = 12
    elif rsi < 30:
        rsi_score = 15  # 严重超卖，可能反弹
    else:
        rsi_score = 5  # 超买区
    
    # 量比分（放量是好信号）
    if 1.0 <= vol_ratio <= 2.5:
        vol_score = 20
    elif 2.5 < vol_ratio <= 4:
        vol_score = 15  # 异常放量
    elif vol_ratio < 1.0:
        vol_score = 5
    else:
        vol_score = 8
    
    # 涨幅分（小幅上涨最好）
    if 0 <= pct <= 5:
        pct_score = 20
    elif -2 <= pct < 0:
        pct_score = 15  # 小幅回调，可能是好买点
    elif 5 < pct <= 8:
        pct_score = 10
    elif pct < -2:
        pct_score = 8
    else:
        pct_score = 3
    
    # 风险等级权重
    risk_weight = {'低': 1.2, '中': 1.0, '高': 0.7}.get(risk, 1.0)
    
    # 模式权重（突破型最强）
    pattern_weight = {
        '突破启动型': 1.3,
        '2波启动型': 1.2,
        '小阳启动型': 1.0,
        '回踩止跌型': 0.9,
        '综合候选': 1.0,
    }.get(pattern, 1.0)
    
    total = (score_base * 0.3 + rsi_score + vol_score + pct_score) * risk_weight * pattern_weight
    return round(total, 2)


def get_action(price: float, rsi: float, pct: float, pattern: str) -> str:
    """给出操作建议"""
    if rsi < 35:
        return "低吸机会 🔔"
    elif rsi > 75:
        return "观察 ⚠️"
    elif pct > 7:
        return "观察 ⚠️"
    elif pattern in ('突破启动型', '2波启动型'):
        return "关注 ✅"
    else:
        return "观察"


def build_top_picks(candidates: list, top_n: int = 8) -> list:
    """构建Top Picks"""
    picks = []
    for c in candidates:
        price = c.get('最新价', 0)
        rsi = c.get('RSI', 50)
        pct = c.get('涨跌幅', 0)
        pattern = c.get('模式', '')
        
        score = compute_score(c)
        
        # 预期逻辑
        if rsi < 35:
            logic = f"RSI={rsi:.0f} 超卖，反弹概率大"
        elif rsi > 70:
            logic = f"RSI={rsi:.0f} 偏高，注意追高风险"
        else:
            logic = f"RSI={rsi:.0f} 处于合理区间"
        
        # 观察位（支撑/压力）
        ma5 = c.get('MA5', price)
        ma20 = c.get('MA20', price)
        observe_price = round(ma20 * 0.99, 2) if price > ma20 else round(ma5 * 0.99, 2)
        pressure_price = round(ma20 * 1.05, 2)
        
        # 风险点
        risks = []
        if rsi > 70:
            risks.append(f"RSI偏高({rsi:.0f})")
        if pct > 7:
            risks.append(f"涨幅较大({pct:.1f}%)")
        if vol_ratio := c.get('量比', 1.0) > 4:
            risks.append("量比异常")
        if not risks:
            risks.append("无明显风险")
        
        action = get_action(price, rsi, pct, pattern)
        
        picks.append({
            "股票代码": c.get('股票代码', ''),
            "股票名称": c.get('股票名称', ''),
            "所属模式": pattern,
            "入选原因": c.get('入选原因', c.get('AI理由', '')),
            "风险点": risks,
            "预期逻辑": logic,
            "AI评分": score,
            "建议观察位": {
                "支撑位": observe_price,
                "压力位": pressure_price
            },
            "操作建议": action,
            "价格": price,
            "涨跌幅": pct,
            "RSI": rsi,
            "量比": c.get('量比', 1.0),
            "MA20距离": c.get('MA5距离MA20', 0),
        })
    
    # 按AI评分排序
    picks.sort(key=lambda x: x['AI评分'], reverse=True)
    return picks[:top_n]


def build_ai_summary(picks: list, market_summary: dict, emotion: dict) -> str:
    """生成AI市场总结"""
    if not picks:
        return "今日无精选个股，建议观望。"
    
    top_pattern = picks[0].get('所属模式', '未知')
    top_name = picks[0].get('股票名称', '')
    emotion_score = 40
    emotion_level = "中性"
    
    if emotion:
        em = emotion.get('emotion_analysis', {})
        emotion_score = em.get('score', 40)
        emotion_level = em.get('level', '中性')
    
    regime = "复苏阶段"
    
    # 生成AI总结
    summary = f"""## AI 市场总结

**今日判断**：市场进入 **{regime}**。

- 情绪评分：**{emotion_score}/100**（{emotion_level}）
- 最强模式：**{top_pattern}**（{len([p for p in picks if p.get('所属模式')==top_pattern])}只）
- 首选标的：**{top_name}**（AI评分 {picks[0].get('AI评分', 0)}）
- 操作建议：{picks[0].get('操作建议', '观察')}

**核心逻辑**：
{chr(10).join([f"- {p['股票名称']}：{p['预期逻辑']}" for p in picks[:3]])}

**风险提示**：
突破启动型数量偏少（0只），说明市场追涨环境仍弱，不宜重仓追入。

**次日策略**：
- 优先关注回踩止跌型（低吸机会）
- 关注量比适中（1~2.5x）的标的
- 控制仓位， PAPER_ONLY 模式
"""
    return summary


def main():
    print("=== Ranking Engine Phase-2.6A ===")
    
    # 1. 加载候选股
    candidates = []
    if os.path.exists(CANDIDATE_FILE):
        with open(CANDIDATE_FILE) as f:
            d = json.load(f)
            candidates = d.get('candidates', [])
    
    print(f"加载候选股: {len(candidates)} 只")
    
    # 2. 加载观察池
    obs_pool = []
    if os.path.exists(OBS_POOL_FILE):
        with open(OBS_POOL_FILE) as f:
            d = json.load(f)
            cats = d.get('categories', {})
            for cat_stocks in cats.values():
                obs_pool.extend(cat_stocks)
    
    print(f"加载观察池: {len(obs_pool)} 只")
    
    # 3. 合并去重
    all_stocks = {c.get('股票代码'): c for c in candidates}
    for c in obs_pool:
        code = c.get('股票代码')
        if code and code not in all_stocks:
            all_stocks[code] = c
    
    all_list = list(all_stocks.values())
    print(f"合并后: {len(all_list)} 只")
    
    # 4. 风险过滤
    filtered = filter_candidates(all_list)
    print(f"过滤后: {len(filtered)} 只")
    
    # 5. 构建Top Picks
    top_picks = build_top_picks(filtered, top_n=8)
    print(f"Top Picks: {len(top_picks)} 只")
    
    # 7. 加载市场情绪
    emotion = {}
    emp_file = f"{BASE}/emotion_engine/cache/market_emotion_snapshot.json"
    if os.path.exists(emp_file):
        with open(emp_file) as f:
            emotion = json.load(f)
    result = {
        "schema_version": "2.6A",
        "phase": "Phase-2.6A Research Intelligence",
        "generated_at": datetime.now().isoformat(),
        "total_candidates": len(all_list),
        "filtered_candidates": len(filtered),
        "top_picks": top_picks,
        "filter_summary": {
            "st_filtered": len([c for c in all_list if is_st(c.get('股票名称', ''))]),
            "rsi_overbought_filtered": len([c for c in all_list if c.get('RSI', 50) > MAX_RSI]),
            "volume_too_low_filtered": len([c for c in all_list if c.get('量比', 1.0) < MIN_VOLUME_RATIO]),
            "price_abnormal_filtered": len([c for c in all_list if (p := c.get('最新价', 0)) <= 0 or p < MIN_PRICE or p > MAX_PRICE]),
        }
    }
    
    with open(TOP_PICKS_FILE, 'w') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"写入: {TOP_PICKS_FILE}")
    
    # 10. 写入 paper_trading watchlist
    watchlist = {
        "schema_version": "1.0",
        "phase": "Phase-2.6A",
        "generated_at": datetime.now().isoformat(),
        "watchlist": [{"code": p['股票代码'], "name": p['股票名称'], "pattern": p['所属模式'], "action": p['操作建议'], "score": p['AI评分']} for p in top_picks],
        "trade_prohibited": True,  # PAPER_ONLY
        "note": "观察列表，不自动交易"
    }
    with open(WATCHLIST_FILE, 'w') as f:
        json.dump(watchlist, f, ensure_ascii=False, indent=2)
    print(f"写入: {WATCHLIST_FILE}")
    
    # 11. 写入 AI Summary（无标题，仅内容）
    phase_map = {
        'recovery_phase': '复苏阶段', 'breakout_phase': '突破阶段',
        'defensive_phase': '防御阶段', 'trend_phase': '趋势阶段',
        'consolidation_phase': '震荡阶段',
    }
    em_analysis = emotion.get('emotion_analysis', {})
    regime_cn = phase_map.get(em_analysis.get('market_phase', 'unknown'), em_analysis.get('market_phase', 'unknown'))
    emotion_level = em_analysis.get('level', '中性')
    top_pattern = top_picks[0].get('所属模式', '未知') if top_picks else '未知'
    top_name = top_picks[0].get('股票名称', '') if top_picks else ''
    emotion_score = em_analysis.get('score', 40)

    summary_content = f"""**今日判断**：市场进入 **{regime_cn}**。

- 情绪评分：**{emotion_score}/100**（{emotion_level}）
- 最强模式：**{top_pattern}**（{len([p for p in top_picks if p.get('所属模式')==top_pattern])}只）
- 首选标的：**{top_name}**（AI评分 {top_picks[0].get('AI评分', 0) if top_picks else 0}）
- 操作建议：{top_picks[0].get('操作建议', '观察') if top_picks else '观察'}

**核心逻辑**：
{chr(10).join([f"- {p['股票名称']}：{p['预期逻辑']}" for p in top_picks[:3]])}

**风险提示**：
突破启动型数量偏少（0只），说明市场追涨环境仍弱，不宜重仓追入。

**次日策略**：
- 优先关注回踩止跌型（低吸机会）
- 关注量比适中（1~2.5x）的标的
- 控制仓位， PAPER_ONLY 模式"""

    with open(AI_SUMMARY_FILE, 'w') as f:
        f.write(summary_content)
    print(f"写入: {AI_SUMMARY_FILE}")
    
    print("\n=== Top Picks ===")
    for i, p in enumerate(top_picks, 1):
        print(f"{i}. {p['股票名称']} ({p['股票代码']}) | {p['所属模式']} | AI评分:{p['AI评分']} | {p['操作建议']}")
    
    return result


if __name__ == '__main__':
    main()
