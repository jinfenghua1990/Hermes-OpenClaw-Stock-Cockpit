#!/usr/bin/env python3
"""
sector_engine.py - Phase-2.1 Sector Rotation Engine
盘中 09:35 / 10:30 / 13:30 / 14:30 执行
数据来源：
  1. mx_data_output/mx_search_今日A股市场热点板块_*.json（新闻）
  2. mx_data_output/mx_xuangu_*.json（板块成分股）
  3. portfolio/candidate_rankings.json（候选股板块联动）
输出：
  market/sector_rotation.json
  market/sector_rotation.json → candidate_engine 读取并联动评分
飞书推送：sector_rotation
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
SECTOR_OUT     = CRON_BASE / "market" / "sector_rotation.json"
CACHE_DIR      = CRON_BASE / "cron" / ".sector_cache"
CAND_RANKINGS  = CRON_BASE / "portfolio" / "candidate_rankings.json"
HERMES_GROUP_ID = "oc_174834d2967c4dfbdd692464f85398e0"

SECTOR_OUT.parent.mkdir(parents=True, exist_ok=True)
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# =============================================================================
# 主题板块配置（申万/概念 一级分类）
# =============================================================================
THEMES = {
    "AI":        ["AI", "人工智能", "AIGC", "DeepSeek", "大模型", "ChatGPT", "AI眼镜", "AI应用", "AI算力", "AI芯片"],
    "算力":      ["算力", "算力租赁", "数据中心", "光通信", "CPO", "光模块", "铜缆", "液冷", "服务器PCB", "算力概念"],
    "PCB":       ["PCB", "印制电路板", "通信PCB", "服务器PCB", "PCB化学品", "PCB铜箔", "覆铜板", "CCL"],
    "机器人":    ["机器人", "人形机器人", "工业母机", "减速器", "传感器", "机器视觉", "自动化设备"],
    "半导体":    ["半导体", "国产芯片", "光刻机", "先进封装", "存储芯片", "GPU", "HBM", "英伟达概念", "AI芯片"],
    "电力":      ["电力", "虚拟电厂", "智能电网", "绿电", "光伏", "储能", "电网概念", "特高压", "柔性直流"],
    "新能源":    ["新能源", "锂电池", "固态电池", "钠离子电池", "光伏设备", "新能源车", "比亚迪概念", "能源金属"],
    "银行":      ["银行"],
    "证券":      ["证券"],
    "医疗":      ["医药", "医疗器械", "中药", "创新药", "疫苗"],
}

# 热门主题（来自新闻分析）
HOT_THEMES_OVERRIDE = {
    "光纤":      ["光纤概念", "光通信", "光棒"],
    "工业母机":  ["工业母机", "数控机床"],
    "光通信":    ["光通信", "CPO", "光模块"],
}

# =============================================================================
# 工具函数
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

def parse_float(v) -> Optional[float]:
    try:
        return float(v)
    except:
        return None

def classify_concept(concept_str: str) -> List[str]:
    """根据概念字符串返回匹配的主题列表"""
    matched = []
    for theme, keywords in THEMES.items():
        for kw in keywords:
            if kw in concept_str:
                matched.append(theme)
                break
    return matched

# =============================================================================
# 1. 从新闻读取热点板块（mx_search）
# =============================================================================
def parse_sector_news() -> Dict[str, Any]:
    """解析 mx_search_今日A股市场热点板块 输出，提取板块涨跌和关键词"""
    files = list(MX_OUT_DIR.glob("mx_search_今日A股市场热点板块*.json"))
    if not files:
        return {}
    # 读最新文件
    latest = max(files, key=lambda f: f.stat().st_mtime)
    raw = load_json_safe(latest)
    if not raw:
        return {}

    try:
        news_items = (raw.get("data", {})
                      .get("data", {})
                      .get("llmSearchResponse", {})
                      .get("data", []))
    except (KeyError, TypeError):
        return {}

    sectors = {}  # name -> {pct, keywords, count}

    for item in news_items:
        content = item.get("content", "") or ""
        title   = item.get("title", "") or ""
        combined = title + " " + content

        # 提取涨跌幅
        pct = 0.0
        for m in re.findall(r"([\+|\-]?\d+\.?\d*)%", combined):
            v = parse_float(m)
            if v and abs(v) > 0.1:
                pct = v
                break

        # 识别板块关键词
        detected = []
        for theme, keywords in THEMES.items():
            for kw in keywords:
                if kw in combined:
                    detected.append(theme)
                    break

        # 额外识别
        for theme, keywords in HOT_THEMES_OVERRIDE.items():
            for kw in keywords:
                if kw in combined:
                    if theme not in detected:
                        detected.append(theme)
                    break

        # 提取个股
        stock_mentions = re.findall(r"([\u4e00-\u9fa5]{2,6})\s*[\uff08\（]?(\d{6})[\uff09\）]?", combined)
        for name, code in stock_mentions:
            for t in detected:
                if t not in sectors:
                    sectors[t] = {"pct": pct, "stocks": [], "keywords": [], "news_count": 0}
                if {"name": name, "code": code} not in sectors[t]["stocks"]:
                    sectors[t]["stocks"].append({"name": name, "code": code})

        for t in detected:
            if t not in sectors:
                sectors[t] = {"pct": pct, "stocks": [], "keywords": [], "news_count": 0}
            sectors[t]["news_count"] += 1
            sectors[t]["pct"] = max(sectors[t]["pct"], pct)  # 取最强涨幅

    return sectors

# =============================================================================
# 2. 从 xuangu 板块数据读取成分股
# =============================================================================
def parse_xuangu_sectors() -> Dict[str, dict]:
    """读取 mx_xuangu_*.json 板块数据，提取成分股涨跌"""
    sectors = {}
    for fp in MX_OUT_DIR.glob("mx_xuangu_*_raw.json"):
        fname = fp.stem  # e.g. mx_xuangu_PCB板块涨幅大于1%的股票_raw
        # 提取板块名
        m = re.search(r"mx_xuangu_([^_]+)板块", fp.name)
        if not m:
            continue
        board_name = m.group(1)
        raw = load_json_safe(fp)
        if not raw:
            continue

        # 判断是否热门主题
        theme = None
        for t, keywords in THEMES.items():
            if any(kw in board_name for kw in keywords):
                theme = t
                break

        try:
            all_res = (raw.get("data", {})
                       .get("data", {})
                       .get("allResults", {})
                       .get("result", {})
                       .get("dataList", []))
        except (KeyError, TypeError):
            all_res = []

        stocks = []
        for row in all_res[:20]:  # 每板块最多20只
            code = str(row.get("SECURITY_CODE", ""))
            name = row.get("SECURITY_SHORT_NAME", "")
            pct  = parse_float(str(row.get("CHG", "0")))
            price = parse_float(str(row.get("NEWEST_PRICE", "0")))
            concepts_raw = row.get("STYLE_CONCEPT", {"pureText": ""})
            if isinstance(concepts_raw, dict):
                concepts = concepts_raw.get("pureText", "") or ""
            else:
                concepts = str(concepts_raw)

            if not code:
                continue

            stocks.append({
                "code": code, "name": name,
                "pct": pct or 0, "price": price or 0,
                "concepts": concepts,
                "themes": classify_concept(concepts),
            })

        if stocks:
            avg_pct = sum(s["pct"] for s in stocks) / len(stocks) if stocks else 0
            sectors[board_name] = {
                "theme": theme,
                "board_name": board_name,
                "stock_count": len(stocks),
                "avg_pct": round(avg_pct, 2),
                "top_stocks": sorted(stocks, key=lambda x: -x["pct"])[:5],
                "all_stocks": stocks,
            }

    return sectors

# =============================================================================
# 3. 从 events.json 读取指数快照
# =============================================================================
def get_index_snapshot() -> List[dict]:
    ev = load_json_safe(CRON_BASE / "portfolio" / "events.json") or {}
    return ev.get("indices_snapshot", [])

# =============================================================================
# 4. 综合评分：板块强度
# =============================================================================
def score_sector(board_name: str, data: dict, news_sectors: dict) -> dict:
    """对板块评分，返回强度指标"""
    avg_pct   = data.get("avg_pct", 0)
    count     = data.get("stock_count", 0)
    theme     = data.get("theme", "")
    news_pct  = news_sectors.get(theme, {}).get("pct", 0) if theme else 0

    # 综合涨幅
    sector_pct = max(avg_pct, news_pct)

    # 强度等级
    if sector_pct >= 3:
        level = "hot"
    elif sector_pct >= 1:
        level = "warm"
    elif sector_pct >= 0:
        level = "neutral"
    elif sector_pct >= -1:
        level = "cool"
    else:
        level = "cold"

    # 仓位调整（相对基准）
    position_multiplier = 1.0
    if theme in ["AI", "算力", "PCB", "机器人", "半导体"]:
        if sector_pct >= 3:
            position_multiplier = 1.3   # 热门主题可加仓
        elif sector_pct >= 1:
            position_multiplier = 1.1
        elif sector_pct < -1:
            position_multiplier = 0.7   # 冷门主题降仓位
    elif theme in ["新能源", "电力"]:
        if sector_pct < -2:
            position_multiplier = 0.5

    return {
        "board_name":   board_name,
        "theme":       theme,
        "avg_pct":     round(sector_pct, 2),
        "stock_count": count,
        "level":       level,
        "position_multiplier": round(position_multiplier, 2),
        "source":      "xuangu+news",
    }

# =============================================================================
# 5. 生成板块轮动报告
# =============================================================================
def generate_sector_rotation() -> dict:
    news_s  = parse_sector_news()
    xuangu  = parse_xuangu_sectors()
    indices = get_index_snapshot()

    # 合并评分
    all_sectors = {}
    for board, data in xuangu.items():
        scored = score_sector(board, data, news_s)
        theme  = scored["theme"]
        if theme:
            all_sectors[theme] = scored

    # 从新闻补充主题（没有 xuangu 数据的）
    for theme, ndata in news_s.items():
        if theme not in all_sectors:
            all_sectors[theme] = {
                "board_name":  theme,
                "theme":       theme,
                "avg_pct":     ndata.get("pct", 0),
                "stock_count": 0,
                "level":       "warm" if ndata.get("pct", 0) > 0 else "neutral",
                "position_multiplier": 1.0,
                "source":      "news",
                "top_stocks":  ndata.get("stocks", [])[:3],
            }

    # 按 avg_pct 排序
    sorted_sectors = sorted(all_sectors.values(),
                            key=lambda x: -x["avg_pct"])

    # 分类：hot / warm / neutral / cool / cold
    hot     = [s for s in sorted_sectors if s["level"] == "hot"]
    warm    = [s for s in sorted_sectors if s["level"] == "warm"]
    neutral = [s for s in sorted_sectors if s["level"] == "neutral"]
    cool    = [s for s in sorted_sectors if s["level"] == "cool"]
    cold    = [s for s in sorted_sectors if s["level"] == "cold"]

    # 龙头股（各板块最强）
    leaders = []
    for s in sorted_sectors[:8]:
        top = s.get("top_stocks", [])
        if top:
            leaders.append({
                "theme":    s["theme"],
                "pct":      s["avg_pct"],
                "level":    s["level"],
                "top_stock": top[0],
            })

    report = {
        "schema_version": "2.1",
        "phase":         "Phase-2.2 AI Stock Cockpit",
        "generated_at":  datetime.now().isoformat(),
        "indices_snapshot": indices,
        "all_sectors":   all_sectors,
        "hot":     hot,
        "warm":    warm,
        "neutral": neutral,
        "cool":    cool,
        "cold":    cold,
        "leaders": leaders,
        "total_sectors": len(sorted_sectors),
    }
    return report

# =============================================================================
# 6. 联动 candidate_rankings.json：板块加分
# =============================================================================
def apply_sector_rotation_to_candidates(report: dict) -> dict:
    """读取 candidate_rankings.json，对每只候选股应用板块联动评分"""
    cand_file = CAND_RANKINGS
    if not cand_file.exists():
        return report

    cand_data = load_json_safe(cand_file)
    if not cand_data:
        return report

    # 建立强势板块集合
    hot_themes  = {s["theme"] for s in report["hot"]}
    warm_themes = {s["theme"] for s in report["warm"]}
    cool_themes = {s["theme"] for s in report["cool"]}
    cold_themes = {s["theme"] for s in report["cold"]}

    # sector_multiplier per theme
    sm = {s["theme"]: s["position_multiplier"] for s in report["all_sectors"].values()}

    adjusted_candidates = []
    for c in cand_data.get("candidates", []):
        sym  = c.get("股票代码", "")
        name = c.get("股票名称", "")
        score_delta = 0
        pos_mult    = 1.0
        sector_note = ""

        # 从 xuangu 板块数据匹配
        xuangu_sectors = {}
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
                code = str(row.get("SECURITY_CODE", ""))
                if code != sym:
                    continue
                concepts_raw = row.get("STYLE_CONCEPT", {})
                if isinstance(concepts_raw, dict):
                    concepts = concepts_raw.get("pureText", "") or ""
                else:
                    concepts = str(concepts_raw)

                themes = classify_concept(concepts)
                for t in themes:
                    if t not in xuangu_sectors:
                        pct = parse_float(str(row.get("CHG", "0"))) or 0
                        xuangu_sectors[t] = {"pct": pct, "concepts": concepts}

        # 应用板块联动
        matched_themes = list(xuangu_sectors.keys())
        for t in matched_themes:
            mult = sm.get(t, 1.0)
            if t in hot_themes:
                score_delta += 15
                sector_note += f"🔥{t}强势+15 "
            elif t in warm_themes:
                score_delta += 8
                sector_note += f"📗{t}温和+8 "
            elif t in cool_themes:
                score_delta -= 5
                sector_note += f"⚠️{t}偏冷-5 "
            elif t in cold_themes:
                score_delta -= 10
                sector_note += f"❄️{t}弱势-10 "
            pos_mult *= mult

        new_score = round(c.get("综合评分", 0) + score_delta, 1)
        new_shares = round(c.get("建议股数", 0) * pos_mult / 100) * 100
        new_shares = max(100, new_shares)

        new_allowed = c.get("允许模拟买入", False)
        if pos_mult < 0.6:
            new_allowed = False  # 冷门板块降权后禁止

        adjusted = dict(c)
        adjusted["综合评分"]           = new_score
        adjusted["建议股数"]           = new_shares
        adjusted["建议仓位pct"]        = round(c.get("建议仓位pct", 0) * pos_mult, 3)
        adjusted["允许模拟买入"]        = new_allowed
        adjusted["板块联动说明"]        = sector_note.strip() or "板块中性"
        adjusted["position_multiplier"] = round(pos_mult, 2)

        adjusted_candidates.append(adjusted)

    # 重排序
    adjusted_candidates.sort(key=lambda x: -x["综合评分"])

    # 更新输出
    updated_cand_data = dict(cand_data)
    updated_cand_data["candidates"] = adjusted_candidates
    updated_cand_data["sector_report_time"] = report["generated_at"]

    cand_file.write_text(json.dumps(updated_cand_data, ensure_ascii=False, indent=2))

    report["candidates_updated"] = True
    report["updated_candidates_count"] = len(adjusted_candidates)
    return report

# =============================================================================
# 7. 飞书推送
# =============================================================================
def feishu(msg: str, alert_type: str = "sector_rotation"):
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

def feishu_sector_rotation(report: dict):
    indices = report.get("indices_snapshot", [])
    hot     = report.get("hot", [])
    warm    = report.get("warm", [])
    cool    = report.get("cool", [])
    leaders = report.get("leaders", [])

    # 指数行
    idx_lines = []
    for idx in indices[:4]:
        pct = idx.get("pct", 0)
        icon = "🔴" if pct > 0 else "🟢"
        idx_lines.append(f"{icon}{idx.get('name','')} {pct:+.2f}%")

    lines = [
        f"🔥 【板块轮动】{datetime.now().strftime('%H:%M')}",
        " | ".join(idx_lines),
        "",
    ]

    # 热门板块
    if hot:
        lines.append("🔥 强势板块")
        for s in hot[:4]:
            leaders_str = ""
            for ts in s.get("top_stocks", [])[:2]:
                leaders_str += f"{ts.get('name','?')} "
            lines.append(
                f"  🔥 {s['board_name']}({s['theme']}) {s['avg_pct']:+.2f}%"
                + (f" | 龙头:{leaders_str.strip()}" if leaders_str else "")
            )
        lines.append("")

    # 温和板块
    if warm:
        lines.append("📗 活跃板块")
        for s in warm[:4]:
            lines.append(f"  📗 {s['board_name']}({s['theme']}) {s['avg_pct']:+.2f}%")
        lines.append("")

    # 偏冷板块
    if cool:
        lines.append("⚠️ 偏冷板块")
        for s in cool[:3]:
            lines.append(f"  ⚠️ {s['board_name']} {s['avg_pct']:+.2f}%")
        lines.append("")

    lines.append(f"Phase-2.1 Sector Rotation Engine")
    feishu("\n".join(lines), "sector_rotation")

# =============================================================================
# 8. 入口
# =============================================================================
if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "rotate"

    print(f"[Sector] Phase-2.1 Sector Rotation Engine 开始...")

    if mode in ("rotate", "full"):
        report = generate_sector_rotation()
        SECTOR_OUT.parent.mkdir(parents=True, exist_ok=True)
        SECTOR_OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2))
        print(f"[Sector] 输出: {SECTOR_OUT}")
        print(f"[Sector] 共 {report['total_sectors']} 个板块 | "
              f"🔥{len(report['hot'])} 📗{len(report['warm'])} "
              f"⚠️{len(report['cool'])} ❄️{len(report['cold'])}")

        # 联动候选股
        if mode == "full":
            report = apply_sector_rotation_to_candidates(report)
            print(f"[Sector] 候选股板块联动完成: {report['updated_candidates_count']} 只")

        feishu_sector_rotation(report)

    elif mode == "adjust":
        # 仅联动候选股（读取现有 sector_rotation.json）
        report = load_json_safe(SECTOR_OUT) or {}
        if not report:
            report = generate_sector_rotation()
            SECTOR_OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2))
        report = apply_sector_rotation_to_candidates(report)
        print(f"[Sector] 候选股联动完成: {report['updated_candidates_count']} 只")

    else:
        print(f"用法: python3 sector_engine.py [rotate|adjust|full]")
        print(f"  rotate: 生成板块轮动报告（不联动候选股）")
        print(f"  adjust: 仅联动候选股评分")
        print(f"  full:   生成报告 + 联动候选股")
