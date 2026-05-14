#!/usr/bin/env python3
"""
Intraday Quote Snapshot via AkShare
Phase-2.8D Full China Market Baseline Selection

盘中用 AkShare 拉取全市场实时行情
今日涨跌幅(pct_chg)、最新价、最高、最低、成交量、成交额

注意:
- factors pct_chg = 昨日收盘涨幅
- AkShare 涨跌幅 = 今日盘中实时涨幅
- 盘中选股应该用 AkShare 今日涨跌幅

输出: runtime_data/intraday_quote_snapshot.json
"""

import json
import warnings
from pathlib import Path
from datetime import datetime
from typing import Dict, Any

import akshare as ak

BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_FILE = BASE_DIR / "runtime_data/intraday_quote_snapshot.json"


def safe_float(v, default=0.0):
    try:
        return float(str(v).replace('%', '').replace(',', '').strip())
    except:
        return default


def fetch_spot_data() -> Dict[str, Dict[str, Any]]:
    """
    从 AkShare 获取全市场实时行情
    stock_zh_a_spot 包含所有 A 股: 主板 + 创业板 + 科创板 + 北交所
    返回: {normalized_code: {fields}}
    """
    print("[1/3] 从 AkShare 拉取全市场实时行情 (stock_zh_a_spot)...")
    warnings.filterwarnings("ignore")

    df = ak.stock_zh_a_spot()
    print(f"  总计: {len(df)} 只股票")

    results = {}
    for _, row in df.iterrows():
        raw_code = str(row.get("代码", ""))
        if not raw_code:
            continue

        # 标准化代码: 去掉 sz/sh/bj 前缀，转为纯数字
        normalized = raw_code.replace("sz", "").replace("sh", "").replace("bj", "").strip()

        pct = safe_float(row.get("涨跌幅", 0))
        latest = safe_float(row.get("最新价", 0))
        high = safe_float(row.get("最高", 0))
        low = safe_float(row.get("最低", 0))
        open_p = safe_float(row.get("今开", 0))
        prev_close = safe_float(row.get("昨收", 0))
        vol = safe_float(row.get("成交量", 0))
        amount = safe_float(row.get("成交额", 0))
        timestamp = str(row.get("时间戳", ""))

        if latest > 0:  # 只保留有价格的
            results[normalized] = {
                "最新价": latest,
                "涨跌幅": pct,
                "最高价": high,
                "最低价": low,
                "今开": open_p,
                "昨收": prev_close,
                "成交量": vol,
                "成交额": amount,
                "时间戳": timestamp,
                "raw_code": raw_code,
            }

    print(f"  有效行情: {len(results)} 只")
    return results


def build_snapshot():
    """构建盘中实时行情快照"""
    print("=" * 60)
    print("Intraday Quote Snapshot via AkShare")
    print("Phase-2.8D Full China Market")
    print("=" * 60)

    print("[1/3] 拉取 AkShare 全市场实时行情...")
    spot_data = fetch_spot_data()

    print("[2/3] 验证 300677 英科医疗...")
    test = spot_data.get("300677", {})
    if test:
        print(f"  300677 英科医疗:")
        print(f"    最新价: {test.get('最新价')}")
        print(f"    涨跌幅: {test.get('涨跌幅')}%  ← 今日盘中实时涨幅")
        print(f"    最高: {test.get('最高价')}")
        print(f"    最低: {test.get('最低价')}")
        print(f"    时间: {test.get('时间戳')}")
    else:
        print("  ⚠ 300677 未找到")

    print("[3/3] 保存快照...")
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    snapshot = {
        "phase": "Phase-2.8D",
        "generated_at": datetime.now().isoformat(),
        "source": "akshare_stock_zh_a_spot",
        "quote_data_as_of": datetime.now().isoformat(),
        "total_symbols": len(spot_data),
        "quotes": spot_data,
    }
    OUTPUT_FILE.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  已保存: {OUTPUT_FILE}")

    print("=" * 60)
    print("完成")


if __name__ == "__main__":
    build_snapshot()
