#!/usr/bin/env python3
"""
market_regime.py - Phase-2.1 Market Regime Filter
判断市场整体状态，用于选股和交易的仓位控制
数据来源：portfolio/events.json + market/sector_rotation.json
输出：market/market_regime.json
状态：
  risk_on   可积极开仓
  neutral   正常推荐
  overheat  过热，禁止追高，高RSI降权减半
  risk_off  降低仓位，只出观察不买入
  panic     禁止所有新开仓
"""
import os, sys, json, re
from datetime import datetime, date
from pathlib import Path
from typing import Optional, Dict, Any

HOME            = Path.home()
CRON_BASE       = HOME / "project_ai_trading"
EVENTS_JSON     = CRON_BASE / "portfolio" / "events.json"
SECTOR_JSON     = CRON_BASE / "market" / "sector_rotation.json"
REGIME_JSON     = CRON_BASE / "market" / "market_regime.json"

# =============================================================================
# 辅助函数
# =============================================================================
def load_json(path: Path) -> Optional[dict]:
    try:
        return json.loads(path.read_text())
    except:
        return None

def safe_float(v, default=0.0) -> float:
    try:
        return float(v)
    except:
        return default

# =============================================================================
# 判断市场状态
# =============================================================================
def detect_regime(indices: list, sector_report: dict, cand_data: dict = None) -> dict:
    """综合指数+板块+候选股RSI判断市场状态"""

    # ── 1. 指数分析 ──────────────────────────────────────────────────
    index_map = {idx.get("name", ""): idx for idx in indices}
    def idx_pct(name_substr: str) -> float:
        for name, idx in index_map.items():
            if name_substr in name:
                return idx.get("pct", 0)
        return 0

    sz_pct   = idx_pct("上证指数")
    sz01_pct = idx_pct("深证成指")
    cy_pct   = idx_pct("创业板")
    hs300_pct= idx_pct("沪深300")
    kc50_pct = idx_pct("科创50")

    avg_pct  = sum(filter(None, [sz_pct, sz01_pct, cy_pct, hs300_pct, kc50_pct])) / 5
    max_pct  = max(filter(None, [sz_pct, sz01_pct, cy_pct, kc50_pct]))
    min_pct  = min(filter(None, [sz_pct, sz01_pct, cy_pct, kc50_pct]))

    # ── 2. 板块分析 ──────────────────────────────────────────────────
    hot     = sector_report.get("hot", [])
    warm    = sector_report.get("warm", [])
    cool    = sector_report.get("cool", [])
    cold    = sector_report.get("cold", [])
    total   = len(hot) + len(warm) + len(cool) + len(cold)

    hot_count  = len(hot)
    warm_count = len(warm)

    # 板块集中度（强势板块占比）
    concentration = hot_count / max(total, 1)

    # 热门板块平均涨幅
    hot_avg = sum(s.get("avg_pct", 0) for s in hot) / max(len(hot), 1)

    # ── 3. 候选股 RSI 分析 ────────────────────────────────────────────
    high_rsi_count  = 0
    mid_rsi_count   = 0
    candidates       = []
    if cand_data:
        candidates = cand_data.get("candidates", [])
    for c in candidates:
        rsi = safe_float(c.get("RSI", 0))
        if rsi > 75:
            high_rsi_count += 1
        elif rsi > 55:
            mid_rsi_count += 1

    high_rsi_ratio  = high_rsi_count / max(len(candidates), 1)
    cand_avg_rsi     = sum(safe_float(c.get("RSI", 0)) for c in candidates) / max(len(candidates), 1)

    # ── 4. 综合判断逻辑 ──────────────────────────────────────────────
    signals = []  # 诊断信息

    # 4.1 Panic：任一指数跌幅 > 2%
    if min_pct < -2.0:
        regime = "panic"
        signals.append(f"恐慌：{min_pct:.2f}%指数急跌")
        position_limit = 0.0

    # 4.2 Risk_off：平均涨幅 < 0 且弱势板块多
    elif avg_pct < -0.5 and len(cold) > 2:
        regime = "risk_off"
        signals.append(f"风险偏好下降：平均{avg_pct:.2f}% 弱势板块{len(cold)}个")
        position_limit = 0.3

    # 4.3 Overheat：科创50 > 3% 且 强势板块少（集中炒作）
    elif kc50_pct > 3.0 and hot_count <= 2:
        regime = "overheat"
        signals.append(f"局部过热：科创50{kc50_pct:.2f}% 强势板块少集中炒作")
        position_limit = 0.5

    # 4.4 Overheat：强势板块平均涨幅 > 5% 但 RSI 极高
    elif hot_avg > 5.0 and high_rsi_ratio > 0.6:
        regime = "overheat"
        signals.append(f"过热：强势均{hot_avg:.2f}% 高RSI占比{high_rsi_ratio:.0%}")
        position_limit = 0.5

    # 4.5 Risk_on：主要指数全涨，强势板块 >= 3
    elif (sz_pct > 0 and sz01_pct > 0 and cy_pct > 0 and hot_count >= 3
          and avg_pct > 0.5):
        regime = "risk_on"
        signals.append(f"做多窗口：指数全涨 强势板块{hot_count}个 均{avg_pct:.2f}%")
        position_limit = 1.0

    # 4.6 Risk_on：科创+创业板领涨，强势板块 >= 2
    elif kc50_pct > 1.5 and cy_pct > 1.0 and hot_count >= 2:
        regime = "risk_on"
        signals.append(f"成长做多：科创{kc50_pct:.2f}% 创业{cy_pct:.2f}% 强势{hot_count}个")
        position_limit = 1.0

    # 4.7 Neutral（默认）
    else:
        regime = "neutral"
        signals.append(f"中性市场：均{avg_pct:.2f}% 强势{hot_count}个 高RSI{high_rsi_count}只")
        position_limit = 0.8

    # ── 5. 交易限制 ──────────────────────────────────────────────────
    if regime == "panic":
        allow_new = False
        allow_reinforce = False
        allow_short = False
        reason = "指数急跌，禁止所有新开仓"
    elif regime == "risk_off":
        allow_new = False
        allow_reinforce = False
        allow_short = True
        reason = "风险偏好下降，只做观察不开新仓"
    elif regime == "overheat":
        allow_new = True
        allow_reinforce = True
        allow_short = False
        reason = f"局部过热，禁止追高，高RSI({high_rsi_count}只)降权减半"
    elif regime == "risk_on":
        allow_new = True
        allow_reinforce = True
        allow_short = False
        reason = "市场做多窗口，积极布局强势主线"
    else:  # neutral
        allow_new = True
        allow_reinforce = True
        allow_short = False
        reason = "中性市场，正常推荐"

    # ── 6. 指数详情 ──────────────────────────────────────────────────
    index_details = [
        {
            "name": idx.get("name", ""),
            "code": idx.get("code", ""),
            "price": idx.get("price", 0),
            "pct": idx.get("pct", 0),
            "status": "🔥" if idx.get("pct", 0) > 1 else ("🟢" if idx.get("pct", 0) < -0.5 else "📗")
        }
        for idx in indices
    ]

    result = {
        "schema_version":    "2.1",
        "phase":             "Phase-2.2 AI Stock Cockpit",
        "generated_at":      datetime.now().isoformat(),
        "regime":            regime,
        "position_limit":    position_limit,
        "allow_new":         allow_new,
        "allow_reinforce":   allow_reinforce,
        "allow_short":        allow_short,
        "reason":            reason,
        "signals":           signals,
        "index_details":     index_details,
        "index_summary": {
            "上证":   round(sz_pct, 2),
            "深证":   round(sz01_pct, 2),
            "创业板": round(cy_pct, 2),
            "沪深300":round(hs300_pct, 2),
            "科创50": round(kc50_pct, 2),
            "平均":   round(avg_pct, 2),
            "最高":   round(max_pct, 2),
            "最低":   round(min_pct, 2),
        },
        "sector_summary": {
            "hot":  hot_count,
            "warm": warm_count,
            "cool": len(cool),
            "cold": len(cold),
            "concentration": round(concentration, 2),
            "hot_avg_pct":   round(hot_avg, 2),
        },
        "cand_summary": {
            "count":        len(candidates),
            "high_rsi":     high_rsi_count,
            "mid_rsi":      mid_rsi_count,
            "high_rsi_ratio": round(high_rsi_ratio, 2),
            "avg_rsi":      round(cand_avg_rsi, 1),
        },
    }
    return result

# =============================================================================
# 飞书推送
# =============================================================================
HERMES_GROUP_ID = "oc_174834d2967c4dfbdd692464f85398e0"

def feishu(msg: str, alert_type: str = "market_regime"):
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

def feishu_regime(report: dict):
    regime   = report["regime"]
    idx_sum  = report.get("index_summary", {})
    sec_sum  = report.get("sector_summary", {})
    signals  = report.get("signals", [])

    icon = {"risk_on":"🟢","neutral":"📗","overheat":"🔥","risk_off":"⚠️","panic":"🔴"}.get(regime,"❓")
    regime_text = {"risk_on":"可积极开仓","neutral":"正常推荐","overheat":"过热禁追高","risk_off":"降仓观察","panic":"禁止新开仓"}.get(regime,regime)

    idx_lines = " | ".join([
        f"{idx['status']}{idx['name'][:4]}{idx['pct']:+.2f}%"
        for idx in report.get("index_details", [])
    ])

    limit_pct = int(report.get("position_limit", 1.0) * 100)

    lines = [
        f"{icon} 【市场状态】{datetime.now().strftime('%H:%M')}",
        f"状态：{regime_text}（仓位上限 {limit_pct}%）",
        idx_lines,
    ]

    if signals:
        lines.append(f"诊断：{signals[0]}")

    lines += [
        f"强势🔥{sec_sum.get('hot',0)}个 | 温和📗{sec_sum.get('warm',0)}个 | 偏冷⚠️{-sec_sum.get('cool',0)}% | 弱势❄️{len(report.get('cold',[]))}个",
        f"候选高RSI({report['cand_summary'].get('high_rsi',0)}只) | 均RSI {report['cand_summary'].get('avg_rsi',0):.0f}",
        "Phase-2.1 Market Regime Filter",
    ]

    feishu("\n".join(lines), f"market_regime_{regime}")

# =============================================================================
# 入口
# =============================================================================
if __name__ == "__main__":
    print(f"[Regime] Phase-2.1 Market Regime Filter 开始...")

    # 读取指数快照
    events = load_json(EVENTS_JSON) or {}
    indices = events.get("indices_snapshot", [])

    # 读取板块报告
    sector = load_json(SECTOR_JSON) or {}

    # 读取候选股（用于RSI分析）
    cand_path = CRON_BASE / "portfolio" / "candidate_rankings.json"
    cand_data = load_json(cand_path)

    # 判断状态
    report = detect_regime(indices, sector, cand_data)

    # 写入
    REGIME_JSON.parent.mkdir(parents=True, exist_ok=True)
    REGIME_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"[Regime] 输出: {REGIME_JSON}")
    print(f"[Regime] 状态: {report['regime']} | 仓位上限: {int(report['position_limit']*100)}% | 新开仓: {report['allow_new']}")
    print(f"[Regime] 诊断: {report['signals']}")

    # 飞书
    feishu_regime(report)

    # 模式标志
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    if mode == "--check":
        print(f"[Regime] 状态={report['regime']} allow_new={report['allow_new']} position_limit={report['position_limit']}")
