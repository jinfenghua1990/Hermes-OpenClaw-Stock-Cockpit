#!/usr/bin/env python3
"""
Replay Engine v1 - 历史市场状态回放
根据 reports/history/index.json 和历史日报，回放某一天市场状态
"""

import json
import os
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional

BASE_DIR = Path(__file__).resolve().parent.parent
HISTORY_INDEX = BASE_DIR / "reports" / "history" / "index.json"
CACHE_DIR = BASE_DIR / "replay_engine" / "cache"
LATEST_CACHE = CACHE_DIR / "latest_replay.json"


def load_history_index() -> Dict[str, Any]:
    """加载历史日报索引"""
    if not HISTORY_INDEX.exists():
        print(f"错误：历史索引文件不存在 {HISTORY_INDEX}")
        sys.exit(1)
    
    try:
        with open(HISTORY_INDEX, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"错误：无法加载索引文件 {e}")
        sys.exit(1)


def find_report_by_date(date_str: str, index_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """根据日期查找日报信息"""
    for report in index_data.get("reports", []):
        if report["date"] == date_str:
            return report
    return None


def get_latest_report(index_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """获取最新日报"""
    reports = index_data.get("reports", [])
    if not reports:
        return None
    
    # 索引中的报告已按日期倒序排列
    return reports[0]


def format_report_output(report: Dict[str, Any]) -> Dict[str, Any]:
    """格式化报告输出"""
    pattern_counts = report.get("pattern_counts", {})
    
    return {
        "date": report["date"],
        "market_phase": report["market_phase"],
        "risk_level": report["risk_level"],
        "strongest_mode": report["strongest_mode"],
        "mode1_count": pattern_counts.get("mode1_count", 0),
        "mode2_count": pattern_counts.get("mode2_count", 0),
        "mode3_count": pattern_counts.get("mode3_count", 0),
        "mode4_count": pattern_counts.get("mode4_count", 0),
        "total_candidates": pattern_counts.get("total_candidates", 0),
        "report_path": report["path"],
        "file_size": report["file_size"],
        "last_modified": report["last_modified"]
    }


def save_to_cache(replay_data: Dict[str, Any]):
    """保存到缓存文件"""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    
    cache_data = {
        "replay_version": "1.0",
        "generated_at": datetime.now().isoformat(),
        "data": replay_data
    }
    
    try:
        with open(LATEST_CACHE, 'w', encoding='utf-8') as f:
            json.dump(cache_data, f, ensure_ascii=False, indent=2)
        print(f"缓存已保存：{LATEST_CACHE}")
    except Exception as e:
        print(f"警告：无法保存缓存 {e}")


def print_human_readable(replay_data: Dict[str, Any]):
    """打印人类可读的输出"""
    print("\n" + "="*60)
    print("历史市场状态回放")
    print("="*60)
    
    print(f"📅 日期：{replay_data['date']}")
    print(f"📊 市场阶段：{replay_data['market_phase']}")
    print(f"⚠️  风险等级：{replay_data['risk_level']}")
    print(f"🚀 最强模式：{replay_data['strongest_mode']}")
    
    print("\n📈 四模式统计：")
    print(f"  • 回踩止跌型：{replay_data['mode1_count']} 只")
    print(f"  • 突破启动型：{replay_data['mode2_count']} 只")
    print(f"  • 小阳启动型：{replay_data['mode3_count']} 只")
    print(f"  • 2波启动型：{replay_data['mode4_count']} 只")
    print(f"  • 候选总数：{replay_data['total_candidates']} 只")
    
    print(f"\n📁 报告路径：{replay_data['report_path']}")
    print(f"📄 文件大小：{replay_data['file_size']} 字节")
    print(f"🕒 最后修改：{replay_data['last_modified']}")
    print("="*60)


def print_json_output(replay_data: Dict[str, Any]):
    """打印JSON格式输出"""
    print(json.dumps(replay_data, ensure_ascii=False, indent=2))


def main():
    """主函数"""
    # 解析命令行参数
    if len(sys.argv) != 2:
        print("用法：")
        print("  python replay_engine/replay_market_day.py <日期>")
        print("  python replay_engine/replay_market_day.py latest")
        print("\n示例：")
        print("  python replay_engine/replay_market_day.py 2026-05-12")
        print("  python replay_engine/replay_market_day.py latest")
        sys.exit(1)
    
    target_date = sys.argv[1]
    
    # 加载历史索引
    print(f"加载历史索引...")
    index_data = load_history_index()
    
    # 查找目标报告
    if target_date.lower() == "latest":
        print("查找最新日报...")
        report = get_latest_report(index_data)
        if not report:
            print("错误：没有找到任何历史日报")
            sys.exit(1)
        print(f"找到最新日报：{report['date']}")
    else:
        print(f"查找日期：{target_date}")
        report = find_report_by_date(target_date, index_data)
        if not report:
            print(f"错误：没有找到 {target_date} 的日报")
            print(f"可用日期范围：{index_data['metadata']['date_range']['earliest']} 到 {index_data['metadata']['date_range']['latest']}")
            sys.exit(1)
    
    # 格式化输出
    replay_data = format_report_output(report)
    
    # 保存到缓存
    save_to_cache(replay_data)
    
    # 输出结果
    print_human_readable(replay_data)
    print("\nJSON格式输出：")
    print_json_output(replay_data)


if __name__ == "__main__":
    main()