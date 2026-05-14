#!/usr/bin/env python3
"""
Scanner to Candidate Rankings Adapter
Phase-2.8D Full China Market Baseline Selection

读取 original_four_modes_scanner 输出
合并四种模式结果，去重，排序
输出 portfolio/candidate_rankings.json

数据源：
- strategies/outputs/original_four_modes_*.json
- data/stock_pool.json (symbol → name 映射)

正式链路：
features/cache/daily_technical_factors.json (4788只)
→ original_four_modes_scanner.py
→ strategies/outputs/original_four_modes_YYYY-MM-DD.json
→ scanner_to_candidate_rankings_adapter.py  ← 本文件
→ portfolio/candidate_rankings.json
→ candidate_pool_refresh_runtime (刷新/校验/标记)
→ Paper Runtime
→ Governance / Replay / Feishu
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any

# 目录配置
BASE_DIR = Path(__file__).resolve().parent.parent
STRATEGY_OUTPUT_DIR = BASE_DIR / "strategies/outputs"
CANDIDATE_RANKINGS_FILE = BASE_DIR / "portfolio/candidate_rankings.json"
STOCK_POOL_FILE = BASE_DIR / "data/stock_pool.json"

# 模式权重（固定，不自动调整）
MODE_WEIGHTS = {
    "mode_1_revert": 3,       # 回踩止跌型
    "mode_2_breakout": 3,     # 突破启动型
    "mode_3_xiaoyang": 2,     # 小阳启动型
    "mode_4_second_wave": 2,  # 2波启动型
}


def build_symbol_name_map() -> Dict[str, str]:
    """从 stock_pool.json 构建 symbol → stock_name 映射"""
    if not STOCK_POOL_FILE.exists():
        return {}
    try:
        pool = json.loads(STOCK_POOL_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}

    name_map = {}
    for item in pool:
        code = str(item.get("code", "")).zfill(6)
        name = item.get("name", "")
        if code and name:
            name_map[code] = name
    return name_map


def normalize_symbol(symbol: str) -> str:
    """去掉 .SZ .SH 后缀，返回6位纯数字代码"""
    return symbol.replace(".SZ", "").replace(".SH", "").strip()


def find_latest_scanner_output() -> Path:
    """找到最新的 scanner 输出文件"""
    today = datetime.now().strftime("%Y-%m-%d")
    today_file = STRATEGY_OUTPUT_DIR / f"original_four_modes_{today}.json"
    if today_file.exists():
        return today_file
    files = sorted(STRATEGY_OUTPUT_DIR.glob("original_four_modes_*.json"), reverse=True)
    if not files:
        raise FileNotFoundError("未找到 original_four_modes_*.json 文件，请先运行 scanner")
    return files[0]


def load_scanner_output() -> Dict[str, Any]:
    """加载 scanner 输出"""
    scanner_file = find_latest_scanner_output()
    return json.loads(scanner_file.read_text(encoding="utf-8"))


def merge_candidates(scanner_data: Dict[str, Any], name_map: Dict[str, str]) -> List[Dict[str, Any]]:
    """合并四种模式，去重，计算综合评分，加入股票名称"""
    candidates: Dict[str, Dict[str, Any]] = {}

    mode_keys = {
        "mode_1_revert": "回踩止跌型",
        "mode_2_breakout": "突破启动型",
        "mode_3_xiaoyang": "小阳启动型",
        "mode_4_second_wave": "2波启动型",
    }

    for mode_key, mode_name in mode_keys.items():
        mode_items = scanner_data.get(mode_key, [])
        weight = MODE_WEIGHTS.get(mode_key, 1)

        for item in mode_items:
            symbol = item.get("symbol", "")
            if not symbol:
                continue

            bare = normalize_symbol(symbol)
            stock_name = name_map.get(bare, bare)  # 查不到则用代码本身

            if symbol not in candidates:
                candidates[symbol] = {
                    "symbol": symbol,
                    "stock_code": bare,
                    "stock_name": stock_name,
                    "close": item.get("close", 0),
                    "ma20": item.get("ma20", 0),
                    "pct_chg": item.get("pct_chg", 0),
                    "rsi14": item.get("rsi14", 0),
                    "volume_ratio": item.get("volume_ratio", 0),
                    "matched_modes": [],
                    "mode_count": 0,
                    "runtime_candidate_score": 0,
                    "source": "original_four_modes_scanner",
                }

            if mode_name not in candidates[symbol]["matched_modes"]:
                candidates[symbol]["matched_modes"].append(mode_name)
                candidates[symbol]["mode_count"] += 1
                candidates[symbol]["runtime_candidate_score"] += weight

    # 严格筛选：只保留3模式以上的股票
    # 2模式不推荐买，不进入正式候选池
    result = [c for c in candidates.values() if c["mode_count"] >= 3]
    result.sort(key=lambda x: (x["runtime_candidate_score"], x["mode_count"]), reverse=True)

    return result


def build_candidate_rankings(candidates: List[Dict[str, Any]], scanner_data: Dict[str, Any]) -> Dict[str, Any]:
    """构建完整的 candidate_rankings.json"""
    now = datetime.now()
    stats = scanner_data.get("statistics", {})

    return {
        "phase": "Phase-2.8D",
        "generated_at": now.isoformat(),
        "updated_at": now.isoformat(),
        "source": "scanner_to_candidate_rankings_adapter",
        "source_file": str(find_latest_scanner_output()),
        "schema_version": "1.0",
        "report_type": "candidate_rankings",
        "market_regime": scanner_data.get("date", "unknown"),
        "total_universe": stats.get("total_symbols", 0),
        "scanner_stats": {
            "mode_1_revert": stats.get("mode_1_count", 0),
            "mode_2_breakout": stats.get("mode_2_count", 0),
            "mode_3_xiaoyang": stats.get("mode_3_count", 0),
            "mode_4_second_wave": stats.get("mode_4_count", 0),
            "any_mode_count": stats.get("any_mode_count", 0),
        },
        "candidate_count": len(candidates),
        "candidates": candidates,
        "governance": {
            "SOUL_MODE": "OBSERVE_ONLY",
            "PAPER_ONLY": True,
            "auto_trade": False,
            "auto_learning": False,
            "baseline_mutation": False,
        },
    }


def main():
    print("=" * 60)
    print("Scanner to Candidate Rankings Adapter")
    print("Phase-2.8D Full China Market Baseline Selection")
    print("=" * 60)

    # 构建股票名称映射
    name_map = build_symbol_name_map()
    print(f"[名称] 从 stock_pool.json 加载 {len(name_map)} 只股票名称映射")

    print("[加载] original_four_modes scanner 输出...")
    scanner_data = load_scanner_output()
    stats = scanner_data.get("statistics", {})
    print(f"[数据] 全市场股票: {stats.get('total_symbols', 0)}")
    print(f"[数据] 模式1 回踩止跌型: {stats.get('mode_1_count', 0)}")
    print(f"[数据] 模式2 突破启动型: {stats.get('mode_2_count', 0)}")
    print(f"[数据] 模式3 小阳启动型: {stats.get('mode_3_count', 0)}")
    print(f"[数据] 模式4 2波启动型: {stats.get('mode_4_count', 0)}")
    print(f"[数据] 符合任一模式: {stats.get('any_mode_count', 0)}")

    print("[合并] 四种模式去重...")
    candidates = merge_candidates(scanner_data, name_map)
    print(f"[合并] 3模式共振候选股: {len(candidates)}")

    print("[构建] candidate_rankings.json...")
    rankings = build_candidate_rankings(candidates, scanner_data)

    CANDIDATE_RANKINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    CANDIDATE_RANKINGS_FILE.write_text(json.dumps(rankings, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[输出] {CANDIDATE_RANKINGS_FILE}")
    print(f"[候选] 共 {len(candidates)} 只")

    if candidates:
        print("\n[TOP 10 候选股]")
        print(f"{'排名':<4} {'代码':<12} {'名称':<10} {'模式数':<6} {'评分':<6} {'匹配模式'}")
        print("-" * 70)
        for i, c in enumerate(candidates[:10], 1):
            modes = ",".join(c["matched_modes"])
            print(f"{i:<4} {c['symbol']:<12} {c['stock_name']:<10} {c['mode_count']:<6} {c['runtime_candidate_score']:<6} {modes}")

    print("=" * 60)
    print("完成")


if __name__ == "__main__":
    main()
