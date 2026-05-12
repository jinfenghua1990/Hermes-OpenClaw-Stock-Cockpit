#!/usr/bin/env python3
"""
candidate_engine.py - Phase-2.0 AI Stock Cockpit 选股引擎
盘中 10:30 / 14:30 生成候选股排行
盘后 15:30 生成明日观察池
数据来源：
  1. configs/candidate_stocks.json（候选股池）
  2. mx_data_output/（实时行情 MA5/MA20/RSI/量比）
  3. logs/robot4_strategy.json（四种模式匹配结果）
  4. reports/intraday/intraday_signal_*.json（OpenClaw 盘中信号）
  5. portfolio/events.json（事件引擎输出）
  6. portfolio/unified_positions.json（当前持仓）
输出：
  portfolio/candidate_rankings.json
  portfolio/observation_pool.json
飞书推送：intraday_candidate（盘中）/ observation_pool（盘后）
"""
import os, sys, json, glob, re
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional

# =============================================================================
# 路径配置
# =============================================================================
HOME           = Path.home()
CRON_BASE      = HOME / "project_ai_trading"
MX_OUT_DIR     = HOME / "mx_data_output"
CAND_OUT       = CRON_BASE / "portfolio" / "candidate_rankings.json"
OBS_OUT        = CRON_BASE / "portfolio" / "observation_pool.json"
SECTOR_JSON    = CRON_BASE / "market" / "sector_rotation.json"
REGIME_JSON    = CRON_BASE / "market" / "market_regime.json"
CACHE_DIR      = CRON_BASE / "cron" / ".candidate_cache"
HERMES_GROUP_ID = "oc_174834d2967c4dfbdd692464f85398e0"

CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Phase-2.1 主题板块配置（与 sector_engine.py 保持一致）
THEMES = {
    "AI":      ["AI", "人工智能", "AIGC", "DeepSeek", "大模型", "ChatGPT", "AI眼镜", "AI应用", "AI算力", "AI芯片"],
    "算力":    ["算力", "算力租赁", "数据中心", "光通信", "CPO", "光模块", "铜缆", "液冷", "服务器PCB", "算力概念"],
    "PCB":     ["PCB", "印制电路板", "通信PCB", "服务器PCB", "PCB化学品", "PCB铜箔", "覆铜板", "CCL"],
    "机器人":  ["机器人", "人形机器人", "工业母机", "减速器", "传感器", "机器视觉", "自动化设备"],
    "半导体":  ["半导体", "国产芯片", "光刻机", "先进封装", "存储芯片", "GPU", "HBM", "英伟达概念", "AI芯片"],
    "电力":    ["电力", "虚拟电厂", "智能电网", "绿电", "光伏", "储能", "电网概念", "特高压", "柔性直流"],
    "新能源":  ["新能源", "锂电池", "固态电池", "钠离子电池", "光伏设备", "新能源车", "比亚迪概念", "能源金属"],
    "银行":    ["银行"],
    "证券":    ["证券"],
    "医疗":    ["医药", "医疗器械", "中药", "创新药", "疫苗"],
}

# =============================================================================
# 数据加载工具
# =============================================================================
def load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text())
    except:
        return {}

def load_json_safe(path: Path) -> Any:
    try:
        return json.loads(path.read_text())
    except:
        return None

# =============================================================================
# 1. 读取候选股池
# =============================================================================
def get_candidate_pool() -> List[dict]:
    """返回 configs/candidate_stocks.json 中的股票列表"""
    cfg = CRON_BASE / "configs" / "candidate_stocks.json"
    data = load_json_safe(cfg)
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and "stocks" in data:
        return data["stocks"]
    return []

# =============================================================================
# 2. 读取持仓（已有仓位禁止重复买入）
# =============================================================================
def get_held_symbols() -> set:
    """返回 unified_positions.json 中已持有股票代码集合"""
    pos_file = CRON_BASE / "portfolio" / "unified_positions.json"
    data = load_json_safe(pos_file)
    if not data:
        return set()
    held = set()
    for p in data.get("positions", []):
        sym = p.get("symbol", "")
        if p.get("volume", 0) > 0:
            held.add(sym)
            # 也去掉交易所后缀
            held.add(sym.replace(".SH","").replace(".SZ",""))
    return held

# =============================================================================
# 3. 读取四种模式匹配结果
# =============================================================================
def get_pattern_results() -> Dict[str, dict]:
    """返回 robot4_strategy.json 中的模式匹配结果，按股票代码索引"""
    f = CRON_BASE / "logs" / "robot4_strategy.json"
    data = load_json_safe(f)
    if not data:
        return {}
    result = {}
    for s in data.get("matched_stocks", []):
        code = s.get("stock_code", "")
        result[code] = s
    return result

# =============================================================================
# 4. 读取盘中信号
# =============================================================================
def get_intraday_signals() -> Dict[str, dict]:
    """读取 reports/intraday/intraday_signal_*.json 中的候选股指标"""
    signals = {}
    for fp in sorted(glob.glob(str(CRON_BASE / "reports/intraday/intraday_signal_*.json"))):
        data = load_json_safe(Path(fp))
        if not data:
            continue
        for s in data.get("candidate_stocks", []):
            code = s.get("stock_code", "")
            if code:
                signals[code] = s
    return signals

# =============================================================================
# 5. 读取事件引擎输出
# =============================================================================
def get_events() -> Dict[str, Any]:
    """读取 portfolio/events.json"""
    return load_json_safe(CRON_BASE / "portfolio" / "events.json") or {}

# =============================================================================
# 6. 从 mx_data_output 读取单股实时指标
# =============================================================================
def get_stock_indicators(symbol: str) -> Optional[dict]:
    """从 mx_data_output 目录读取股票的 MA5/MA20/RSI/量比/最新价"""
    # 构造可能的文件名
    name_map = {
        "301282": "金禄电子", "300476": "胜宏科技",
        "002130": "沃尔核材", "603629": "利通电子", "002463": "沪电股份",
    }
    name = name_map.get(symbol, symbol)

    # 匹配 MA5/MA20/RSI/量比文件
    p1 = "mx_data_" + "*" + "_" + symbol + "_" + "*MA5*" + "_raw.json"
    p2 = "mx_data_" + "*" + "_" + name + "_" + symbol + "_" + "*MA5*" + "_raw.json"
    patterns = [p1, p2]
    data = None
    for pat in patterns:
        files = glob.glob(str(MX_OUT_DIR / pat))
        for fp in files:
            raw = load_json_safe(fp)
            if not raw:
                continue
            # 双重 data 嵌套
            try:
                table = raw["data"]["data"]["searchDataResultDTO"]["dataTableDTOList"]
                for row in table:
                    cols = {c["colCN"]: c["col"] for c in row.get("data", [])}
                    data = {
                        "最新价":    cols.get("最新价"),
                        "涨跌幅":    cols.get("涨跌幅"),
                        "MA5":       cols.get("MA5"),
                        "MA20":      cols.get("MA20"),
                        "RSI":       cols.get("RSI"),
                        "量比":      cols.get("量比"),
                        "时间":      cols.get("更新时间") or cols.get("时间"),
                    }
                    return data
            except (KeyError, TypeError):
                pass

    # 读取最新价文件
    pp1 = "mx_data_" + "*" + "_" + symbol + "_" + "*最新价*" + "_raw.json"
    pp2 = "mx_data_" + "*" + "_" + name + "_" + symbol + "_" + "*最新价*" + "_raw.json"
    price_files = glob.glob(str(MX_OUT_DIR / pp1)) + glob.glob(str(MX_OUT_DIR / pp2))
    for fp in price_files:
        raw = load_json_safe(fp)
        if not raw:
            continue
        try:
            table = raw["data"]["data"]["searchDataResultDTO"]["dataTableDTOList"]
            for row in table:
                cols = {c["colCN"]: c["col"] for c in row.get("data", [])}
                return {
                    "最新价": cols.get("最新价"),
                    "涨跌幅": cols.get("涨跌幅"),
                    "MA5":    None, "MA20": None,
                    "RSI":    None, "量比": None,
                    "时间":   cols.get("更新时间"),
                }
        except (KeyError, TypeError):
            pass

    return None

# =============================================================================
# 7. 读取指数快照
# =============================================================================
def get_index_snapshot() -> List[dict]:
    """从 events.json 读取指数快照"""
    ev = get_events()
    return ev.get("indices_snapshot", [])

# =============================================================================
# 8. 候选股评分
# =============================================================================
def score_candidate(code: str, name: str, indicators: dict,
                    pattern: dict, held: set, events: dict) -> dict:
    """对候选股打分，返回包含完整分析的字典"""
    price      = indicators.get("最新价") or 0
    pct_chg    = indicators.get("涨跌幅") or 0
    ma5        = indicators.get("MA5")
    ma20       = indicators.get("MA20")
    rsi        = indicators.get("RSI")
    vol_ratio  = indicators.get("量比") or 1.0

    # 基础分
    score = 50

    # RSI 适中偏低 → 加分（超卖反弹潜力）
    if rsi and 30 <= rsi <= 55:
        score += 20
    elif rsi and rsi < 30:
        score += 15   # 严重超卖
    elif rsi and rsi > 70:
        score -= 10   # 超买警告

    # 放量 → 加分
    if vol_ratio and vol_ratio >= 2.0:
        score += 15
    elif vol_ratio and vol_ratio >= 1.5:
        score += 8

    # MA5 金叉 MA20 → 加分
    if ma5 and ma20 and ma5 > ma20:
        score += 10

    # 股价远离 MA20（突破）→ 加分
    if price and ma20 and ma20 > 0:
        dist_pct = (price - ma20) / ma20 * 100
        if dist_pct > 5:
            score += 10
        elif dist_pct < -5:
            score -= 5

    # 今日涨幅适中 → 加分
    if 0 <= pct_chg <= 5:
        score += 8
    elif pct_chg < 0 and pct_chg > -3:
        score += 5   # 小幅回调可接受

    # 模式匹配 → 加分
    if pattern.get("matched"):
        ptype = pattern.get("pattern")
        if ptype == "回踩止跌型":
            score += 15
        elif ptype == "突破启动型":
            score += 15
        elif ptype == "小阳启动型":
            score += 12
        elif ptype == "二波启动型":
            score += 18

    # 已有持仓 → 大幅扣分（不允许追高重复买入）
    if code in held or name in held:
        score -= 40

    # 事件引擎有重要事件 → 加分
    ev_list = events.get("events", [])
    relevant = [e for e in ev_list if code in str(e)]
    if relevant:
        score += 5 * len(relevant)

    # 价格超出交易区间 → 禁止
    price_level = "normal"
    if price > 300:
        price_level = "prohibited_high"
        score -= 100
    elif price >= 200:
        price_level = "high"
    elif price >= 100:
        price_level = "mid"
    else:
        price_level = "low"

    # 风险等级
    if rsi and rsi < 30:
        risk = "低"
    elif rsi and rsi > 75:
        risk = "高"
    elif abs(pct_chg) > 7:
        risk = "高"
    else:
        risk = "中"

    # AI 推荐理由
    reasons = []
    if rsi and rsi < 40:
        reasons.append(f"RSI={rsi:.1f} 超卖")
    if vol_ratio and vol_ratio >= 1.5:
        reasons.append(f"量比={vol_ratio:.2f} 放量")
    if ma5 and ma20 and ma5 > ma20:
        reasons.append("MA5 金叉 MA20")
    if pattern.get("matched"):
        reasons.append(f"匹配模式：{pattern.get('pattern')}")
    if price and ma20 and ma20 > 0:
        dist = (price - ma20) / ma20 * 100
        if dist > 5:
            reasons.append(f"股价突破 MA20 +{dist:.1f}%")
    if relevant:
        reasons.append(f"事件共振：{len(relevant)}条")

    ai_reason = "；".join(reasons) if reasons else "综合指标良好"

    # 建议仓位（价格分层）
    max_pct_map = {"prohibited_high": 0, "high": 0.30, "mid": 0.50, "low": 0.70}
    max_pct = max_pct_map.get(price_level, 0)
    # A股按100股取整
    suggest_shares = 0
    if max_pct > 0 and price > 0:
        raw_shares = int(max_pct * 1000000 / price / 100) * 100
        suggest_shares = max(100, raw_shares) if raw_shares > 0 else 0

    # 是否允许模拟盘买入
    can_buy = (
        score >= 60
        and price_level != "prohibited_high"
        and price > 0
        and code not in held
        and name not in held
    )

    return {
        "股票代码":   code,
        "股票名称":   name,
        "模式":      pattern.get("pattern") or "综合候选",
        "入选原因":  ai_reason,
        "最新价":    round(price, 2) if price else None,
        "涨跌幅":    round(pct_chg, 2) if pct_chg else 0,
        "MA5":       round(ma5, 2) if ma5 else None,
        "MA20":      round(ma20, 2) if ma20 else None,
        "RSI":       round(rsi, 2) if rsi else None,
        "量比":      round(vol_ratio, 2) if vol_ratio else None,
        "风险等级":  risk,
        "AI理由":    ai_reason,
        "综合评分":   round(score, 1),
        "建议股数":  suggest_shares,
        "建议仓位pct": max_pct,
        "允许模拟买入": can_buy,
        "价格区间":   price_level,
        "已有持仓":   code in held or name in held,
    }

# =============================================================================
# 9. 盘中候选股排行
# =============================================================================
def generate_candidate_rankings() -> dict:
    pool       = get_candidate_pool()
    held       = get_held_symbols()
    patterns   = get_pattern_results()
    signals    = get_intraday_signals()
    events     = get_events()
    indices    = get_index_snapshot()

    candidates = []
    name_map   = {s["code"]: s.get("name", s["code"]) for s in pool}

    for stock in pool:
        code = stock.get("code", "")
        name = stock.get("name", code)

        # 优先从 signals 读取指标
        sig = signals.get(code, {})
        ind = {}

        if sig:
            ind_raw = sig.get("indicators", {})
            ind = {
                "最新价": ind_raw.get("最新价"),
                "涨跌幅": ind_raw.get("日涨幅") or ind_raw.get("涨跌幅"),
                "MA5":    ind_raw.get("MA5"),
                "MA20":   ind_raw.get("MA20"),
                "RSI":    ind_raw.get("RSI"),
                "量比":   ind_raw.get("量比"),
            }

        # 尝试从 mx_data_output 补充
        mx = get_stock_indicators(code)
        if mx:
            for k in ["最新价", "涨跌幅", "MA5", "MA20", "RSI", "量比"]:
                if ind.get(k) is None and mx.get(k) is not None:
                    ind[k] = mx[k]

        pat = patterns.get(code, {})
        scored = score_candidate(code, name, ind, pat, held, events)
        candidates.append(scored)

    # ── Phase-2.1 板块轮动 + 市场状态 联动 ────────────────────────────────
    sector_report = load_json_safe(SECTOR_JSON) or {}
    regime_report = load_json_safe(REGIME_JSON) or {}
    regime        = regime_report.get("regime", "neutral")
    regime_limit  = regime_report.get("position_limit", 1.0)
    # 资金数据用于建议股数 cap
    unified_pos   = load_json_safe(CRON_BASE / "portfolio" / "unified_positions.json") or {}
    capital       = unified_pos.get("capital", {})
    total_assets  = capital.get("total_assets", 1_000_000)
    avail_cash    = capital.get("avail_balance", total_assets * 0.1)

    hot_themes  = {s["theme"] for s in sector_report.get("hot", [])}
    warm_themes = {s["theme"] for s in sector_report.get("warm", [])}
    cool_themes = {s["theme"] for s in sector_report.get("cool", [])}
    cold_themes = {s["theme"] for s in sector_report.get("cold", [])}
    sm = {s["theme"]: s["position_multiplier"]
          for s in sector_report.get("all_sectors", {}).values()}

    def _match_themes(code: str) -> set:
        matched = set()
        for fp in MX_OUT_DIR.glob("mx_xuangu_*_raw.json"):
            raw = load_json_safe(fp)
            if not raw:
                continue
            try:
                rows = (raw.get("data", {})
                        .get("data", {})
                        .get("allResults", {})
                        .get("result", {})
                        .get("dataList", []))
            except (KeyError, TypeError):
                continue
            for row in rows:
                if str(row.get("SECURITY_CODE", "")) != code:
                    continue
                cr = row.get("STYLE_CONCEPT", {})
                concepts = (cr.get("pureText", "") or
                            cr.get("matchText", "") or
                            str(cr)) if isinstance(cr, dict) else str(cr)
                for theme, keywords in THEMES.items():
                    if any(kw in concepts for kw in keywords):
                        matched.add(theme)
        return matched

    # 对每只候选股应用联动
    for c in candidates:
        sym    = c["股票代码"]
        themes = _match_themes(sym)
        delta  = 0
        pos_mult = 1.0
        notes = []

        for t in themes:
            mult = sm.get(t, 1.0)
            if t in hot_themes:
                delta += 15
                pos_mult *= mult
                notes.append(f"🔥{t}+15分")
            elif t in warm_themes:
                delta += 8
                pos_mult *= mult
                notes.append(f"📗{t}+8分")
            elif t in cool_themes:
                delta -= 5
                pos_mult *= 0.7
                notes.append(f"⚠️{t}-5分")
            elif t in cold_themes:
                delta -= 10
                pos_mult *= 0.3
                notes.append(f"❄️{t}-10分")

        # 市场状态额外调整
        rsi_val = c.get("RSI") or 0
        if regime == "overheat":
            if rsi_val > 75:
                delta -= 15
                notes.append(f"过热高RSI-15")
                pos_mult *= 0.5
            elif rsi_val > 65:
                delta -= 8
                notes.append(f"过热RSI偏高-8")
                pos_mult *= 0.8
        elif regime == "risk_off":
            delta -= 20
            notes.append("risk_off-20分")
            pos_mult *= 0.3
        elif regime == "panic":
            delta -= 50
            notes.append("panic-50分")
            pos_mult = 0

        new_score   = round(c["综合评分"] + delta, 1)
        # 建议股数：先用 pos_mult 调整，再按可用资金 cap
        raw_shares = round(c["建议股数"] * pos_mult / 100) * 100
        raw_shares = max(100, raw_shares)
        # 资金上限检查：单股不超过可用资金60%，不超过总资产20%
        price = c.get("最新价") or 1
        cap_by_cash  = int(avail_cash * 0.60 / price / 100) * 100
        cap_by_asset = int(total_assets * 0.20 / price / 100) * 100
        new_shares   = min(raw_shares, cap_by_cash, cap_by_asset)
        new_shares   = max(100, new_shares)
        new_allowed = (c["允许模拟买入"]
                       and new_score >= 60
                       and pos_mult > 0.3
                       and regime not in ("panic", "risk_off"))

        c["综合评分"]          = new_score
        c["建议股数"]          = new_shares
        c["建议仓位pct"]       = round(c["建议仓位pct"] * pos_mult, 3)
        c["允许模拟买入"]       = new_allowed
        c["板块/市场联动说明"]  = " | ".join(notes) if notes else "中性"
        c["position_multiplier"]= round(pos_mult, 2)
        c["market_regime"]      = regime

    # panic / risk_off 时全部禁止买入
    if regime in ("panic", "risk_off"):
        for c in candidates:
            c["允许模拟买入"] = False

    # ── 过滤今日已交易股票（防重复买入）─────────────────────────────
    trade_log  = load_json_safe(CRON_BASE / "portfolio" / "trade_log.json") or {}
    today      = datetime.now().date().isoformat()
    bought_syms = {
        t["symbol"] for t in trade_log.get("trades", [])
        if t.get("trade_date") == today and t.get("action") == "buy"
    }
    # 按评分排序，取 Top 10（后续取 Top 5 输出）
    candidates.sort(key=lambda x: -x["综合评分"])
    # 过滤：已有持仓的股票降分，新信号才允许再次入选
    filtered = []
    for c in candidates:
        sym = c["股票代码"]
        if sym in bought_syms:
            # 已买过但今日还未买够3次，降分后保留（给加仓机会）
            c["综合评分"] = max(0, c["综合评分"] - 30)
        filtered.append(c)
    filtered.sort(key=lambda x: -x["综合评分"])
    top5 = [c for c in filtered if c["综合评分"] >= 60][:5]

    report = {
        "schema_version": "2.1",
        "phase": "Phase-2.2 AI Stock Cockpit",
        "report_type": "intraday_candidate",
        "generated_at": datetime.now().isoformat(),
        "market_regime": regime,
        "position_limit": regime_limit,
        "sector_hot_count": len(hot_themes),
        "trade_prohibited": regime in ("panic", "risk_off"),
        "indices_snapshot": indices,
        "candidates": top5,
        "all_candidates_count": len(candidates),
        "held_symbols": list(held),
    }
    return report

# =============================================================================
# 10. 明日观察池（盘后）
# =============================================================================
def generate_observation_pool() -> dict:
    pool     = get_candidate_pool()
    held     = get_held_symbols()
    patterns = get_pattern_results()
    signals = get_intraday_signals()
    indices = get_index_snapshot()

    # 按四种模式分类
    categories = {
        "回踩止跌型": [],
        "突破启动型": [],
        "小阳启动型": [],
        "二波启动型": [],
    }

    for stock in pool:
        code = stock.get("code", "")
        name = stock.get("name", code)
        pat  = patterns.get(code, {})

        if not pat.get("matched"):
            continue

        ptype = pat.get("pattern")
        if ptype not in categories:
            continue

        sig = signals.get(code, {})
        ind = {}
        if sig:
            ind_raw = sig.get("indicators", {})
            ind = {
                "最新价": ind_raw.get("最新价"),
                "涨跌幅": ind_raw.get("日涨幅") or ind_raw.get("涨跌幅"),
                "MA5":    ind_raw.get("MA5"),
                "MA20":   ind_raw.get("MA20"),
                "RSI":    ind_raw.get("RSI"),
                "量比":   ind_raw.get("量比"),
            }

        mx = get_stock_indicators(code)
        if mx:
            for k in ["最新价", "涨跌幅", "MA5", "MA20", "RSI", "量比"]:
                if ind.get(k) is None and mx.get(k) is not None:
                    ind[k] = mx[k]

        price     = ind.get("最新价") or 0
        rsi       = ind.get("RSI")
        vol_ratio = ind.get("量比") or 1.0
        pct_chg   = ind.get("涨跌幅") or 0

        entry_ok = True
        # 禁止条件
        if price > 300 or price <= 0:
            entry_ok = False
        if code in held or name in held:
            entry_ok = False

        item = {
            "股票代码": code,
            "股票名称": name,
            "模式":    ptype,
            "最新价":  round(price, 2) if price else None,
            "涨跌幅":  round(pct_chg, 2) if pct_chg else 0,
            "RSI":     round(rsi, 2) if rsi else None,
            "量比":    round(vol_ratio, 2) if vol_ratio else None,
            "今日是否可买": entry_ok,
            "观察理由": "；".join(pat.get("pattern_reasons", [])) or ptype,
        }
        categories[ptype].append(item)

    # 每类最多3个，按评分排序
    for ptype in categories:
        categories[ptype].sort(key=lambda x: -(x.get("RSI") or 0))
        categories[ptype] = categories[ptype][:3]

    report = {
        "schema_version": "2.0",
        "phase": "Phase-2.2 AI Stock Cockpit",
        "report_type": "observation_pool",
        "generated_at": datetime.now().isoformat(),
        "date": date.today().isoformat(),
        "indices_snapshot": indices,
        "categories": categories,
        "total_count": sum(len(v) for v in categories.values()),
        "held_symbols": list(held),
    }
    return report

# =============================================================================
# 11. 飞书推送
# =============================================================================
def feishu(msg: str, alert_type: str = "intraday_candidate"):
    import subprocess
    try:
        subprocess.run(
            ["lark-cli", "im", "+messages-send",
             "--chat-id", HERMES_GROUP_ID, "--text", msg],
            capture_output=True, timeout=30
        )
        print(f"[FEISHU] 已发送: {alert_type}")
    except Exception as e:
        print(f"[FEISHU] 发送失败: {e}")

def feishu_candidates(report: dict):
    indices = report.get("indices_snapshot", [])
    top5    = report.get("candidates", [])

    # 指数行
    idx_lines = []
    for idx in indices[:4]:
        pct = idx.get("pct", 0)
        icon = "🔴" if pct > 0 else "🟢"
        idx_lines.append(f"{icon}{idx.get('name','')} {pct:+.2f}%")

    lines = [
        f"📈 【盘中候选】{datetime.now().strftime('%H:%M')}",
        " | ".join(idx_lines),
        "",
    ]

    if not top5:
        lines += ["（暂无候选信号）", "", "Phase-2.0 AI Stock Cockpit"]
        feishu("\n".join(lines), "intraday_candidate")
        return

    for i, c in enumerate(top5, 1):
        price = c.get("最新价", "-")
        pct   = c.get("涨跌幅", 0)
        icon  = "🔴" if pct > 0 else "🟢"
        rsi   = c.get("RSI", "-")
        vr    = c.get("量比", "-")
        pat   = c.get("模式", "-")
        score = c.get("综合评分", 0)
        reason= c.get("AI理由", "-")
        can   = "✅可买" if c.get("允许模拟买入") else "⛔禁止"
        shares= c.get("建议股数", 0)
        held  = "📌已持仓" if c.get("已有持仓") else ""

        lines += [
            f"📗 #{i} {c.get('股票名称','')}({c.get('股票代码','')})",
            f"   模式:{pat} | 评分:{score} | {icon} {pct:+.2f}% |价:{price}",
            f"   RSI:{rsi} | 量比:{vr} | {held}",
            f"   {reason}",
            f"   建议:{shares}股 {can}",
            "",
        ]

    lines.append("Phase-2.0 AI Stock Cockpit")
    feishu("\n".join(lines), "intraday_candidate")

def feishu_observation_pool(report: dict):
    cats = report.get("categories", {})
    indices = report.get("indices_snapshot", [])

    idx_lines = []
    for idx in indices[:4]:
        pct = idx.get("pct", 0)
        icon = "🔴" if pct > 0 else "🟢"
        idx_lines.append(f"{icon}{idx.get('name','')} {pct:+.2f}%")

    lines = [
        f"🌙 【明日观察池】{report.get('date', date.today().isoformat())}",
        " | ".join(idx_lines),
        "",
    ]

    total = 0
    for ptype in ["回踩止跌型", "突破启动型", "小阳启动型", "二波启动型"]:
        items = cats.get(ptype, [])
        if not items:
            continue
        total += len(items)
        lines.append(f"【{ptype}】")
        for item in items:
            ok = "✅" if item.get("今日是否可买") else "⛔"
            lines.append(
                f"  {ok} {item.get('股票名称','')}({item.get('股票代码','')})"
                f" | RSI:{item.get('RSI','-')} | 量比:{item.get('量比','-')}"
                f" | {item.get('观察理由','')}"
            )
        lines.append("")

    lines.append(f"共 {total} 只进入观察池")
    lines.append("Phase-2.0 AI Stock Cockpit")
    feishu("\n".join(lines), "observation_pool")

# =============================================================================
# 12. 入口
# =============================================================================
if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "candidates"

    if mode == "candidates":
        print("[Candidate] 生成盘中候选股排行...")
        report = generate_candidate_rankings()
        CAND_OUT.parent.mkdir(parents=True, exist_ok=True)
        CAND_OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2))
        print(f"[Candidate] 输出: {CAND_OUT} ({len(report.get('candidates',[]))} 只)")
        feishu_candidates(report)

    elif mode == "observation":
        print("[Candidate] 生成明日观察池...")
        report = generate_observation_pool()
        OBS_OUT.parent.mkdir(parents=True, exist_ok=True)
        OBS_OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2))
        print(f"[Candidate] 输出: {OBS_OUT} (共 {report.get('total_count',0)} 只)")
        feishu_observation_pool(report)

    elif mode == "full":
        print("[Candidate] 生成完整 Phase-2.0 报告...")
        r1 = generate_candidate_rankings()
        CAND_OUT.parent.mkdir(parents=True, exist_ok=True)
        CAND_OUT.write_text(json.dumps(r1, ensure_ascii=False, indent=2))
        print(f"[Candidate] candidates: {CAND_OUT} ({len(r1.get('candidates',[]))} 只)")
        feishu_candidates(r1)

        r2 = generate_observation_pool()
        OBS_OUT.parent.mkdir(parents=True, exist_ok=True)
        OBS_OUT.write_text(json.dumps(r2, ensure_ascii=False, indent=2))
        print(f"[Candidate] observation: {OBS_OUT} (共 {r2.get('total_count',0)} 只)")
        feishu_observation_pool(r2)

    else:
        print(f"用法: python3 candidate_engine.py [candidates|observation|full]")
