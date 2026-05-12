#!/usr/bin/env python3
"""
日报历史索引生成器
扫描 reports/history/*.md，自动生成索引文件 index.json
用于日报历史沉淀、Replay、情绪历史分析、龙头周期分析、AI经验沉淀
"""

import json
import os
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any

BASE_DIR = Path(__file__).resolve().parent
HISTORY_DIR = BASE_DIR / "history"
INDEX_FILE = HISTORY_DIR / "index.json"


def extract_report_info(file_path: Path) -> Dict[str, Any]:
    """
    从日报文件中提取关键信息
    """
    try:
        content = file_path.read_text(encoding='utf-8')
        
        # 提取日期（从文件名）
        date_str = file_path.stem
        
        # 提取市场阶段
        market_phase = "unknown"
        if "上涨" in content or "强势" in content:
            market_phase = "bullish"
        elif "下跌" in content or "弱势" in content:
            market_phase = "bearish"
        elif "震荡" in content or "盘整" in content:
            market_phase = "consolidation"
        elif "复苏" in content or "回暖" in content:
            market_phase = "recovery"
        elif "调整" in content:
            market_phase = "adjustment"
        
        # 提取风险等级
        risk_level = "medium"
        if "高风险" in content or "警惕" in content:
            risk_level = "high"
        elif "低风险" in content or "安全" in content:
            risk_level = "low"
        
        # 提取模式数量
        pattern_counts = {
            "mode1_count": 0,
            "mode2_count": 0,
            "mode3_count": 0,
            "mode4_count": 0,
            "total_candidates": 0
        }
        
        # 使用正则表达式直接从文本中提取数字
        # 模式1: 回踩止跌型
        mode1_matches = re.findall(r'回踩止跌型.*?(\d+)', content)
        if mode1_matches:
            # 取最后一个匹配（避免匹配到其他位置的数字）
            pattern_counts["mode1_count"] = int(mode1_matches[-1])
        
        # 模式2: 突破启动型
        mode2_matches = re.findall(r'突破启动型.*?(\d+)', content)
        if mode2_matches:
            pattern_counts["mode2_count"] = int(mode2_matches[-1])
        
        # 模式3: 小阳启动型 - 需要特别处理
        # 先尝试匹配列表项格式
        mode3_matches = re.findall(r'小阳启动型[：:]\s*(\d+)', content)
        if not mode3_matches:
            # 尝试匹配带**的格式
            mode3_matches = re.findall(r'小阳启动型[：:]\s*\*\*(\d+)\*\*', content)
        if not mode3_matches:
            # 尝试匹配所有数字，取最后一个（避免匹配到括号内的数字）
            all_mode3_matches = re.findall(r'小阳启动型.*?(\d+)', content)
            if all_mode3_matches:
                # 取最后一个匹配，通常是数量
                mode3_matches = [all_mode3_matches[-1]]
        if mode3_matches:
            pattern_counts["mode3_count"] = int(mode3_matches[0])
        
        # 模式4: 2波启动型
        mode4_matches = re.findall(r'2波启动型.*?(\d+)', content)
        if mode4_matches:
            pattern_counts["mode4_count"] = int(mode4_matches[-1])
        
        # 总候选数
        total_matches = re.findall(r'共有 \*\*(\d+)\*\* 只', content)
        if total_matches:
            pattern_counts["total_candidates"] = int(total_matches[0])
        
        # 确定最强模式
        strongest_mode = "unknown"
        if pattern_counts["mode1_count"] > 0 or pattern_counts["mode2_count"] > 0 or pattern_counts["mode3_count"] > 0 or pattern_counts["mode4_count"] > 0:
            # 找到数量最大的模式
            mode_counts = [
                ("mode1_retracement", pattern_counts["mode1_count"]),
                ("mode2_breakout", pattern_counts["mode2_count"]),
                ("mode3_small_bullish", pattern_counts["mode3_count"]),
                ("mode4_second_wave", pattern_counts["mode4_count"])
            ]
            strongest_mode = max(mode_counts, key=lambda x: x[1])[0]
        
        return {
            "date": date_str,
            "path": str(file_path.relative_to(BASE_DIR.parent)),
            "market_phase": market_phase,
            "risk_level": risk_level,
            "strongest_mode": strongest_mode,
            "pattern_counts": pattern_counts,
            "file_size": file_path.stat().st_size,
            "last_modified": datetime.fromtimestamp(file_path.stat().st_mtime).isoformat()
        }
    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        return None


def scan_history_reports() -> List[Dict[str, Any]]:
    """
    扫描历史日报文件
    """
    reports = []
    
    if not HISTORY_DIR.exists():
        print(f"History directory not found: {HISTORY_DIR}")
        return reports
    
    # 按日期排序读取所有 .md 文件
    md_files = sorted(HISTORY_DIR.glob("*.md"), key=lambda x: x.stem)
    
    print(f"Found {len(md_files)} historical report files")
    
    for file_path in md_files:
        if file_path.stem == "index":  # 跳过索引文件
            continue
            
        report_info = extract_report_info(file_path)
        if report_info:
            reports.append(report_info)
            counts = report_info["pattern_counts"]
            print(f"  - {file_path.stem}: {report_info['market_phase']} ({report_info['risk_level']} risk) "
                  f"模式: M1={counts['mode1_count']}, M2={counts['mode2_count']}, M3={counts['mode3_count']}, M4={counts['mode4_count']}")
    
    return reports


def build_index(reports: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    构建索引结构
    """
    # 按日期排序
    reports.sort(key=lambda x: x["date"], reverse=True)
    
    # 计算统计信息
    total_reports = len(reports)
    market_phase_counts = {}
    risk_level_counts = {}
    mode_counts = {
        "mode1_total": 0,
        "mode2_total": 0,
        "mode3_total": 0,
        "mode4_total": 0
    }
    
    for report in reports:
        # 市场阶段统计
        phase = report["market_phase"]
        market_phase_counts[phase] = market_phase_counts.get(phase, 0) + 1
        
        # 风险等级统计
        risk = report["risk_level"]
        risk_level_counts[risk] = risk_level_counts.get(risk, 0) + 1
        
        # 模式统计
        counts = report["pattern_counts"]
        mode_counts["mode1_total"] += counts["mode1_count"]
        mode_counts["mode2_total"] += counts["mode2_count"]
        mode_counts["mode3_total"] += counts["mode3_count"]
        mode_counts["mode4_total"] += counts["mode4_count"]
    
    # 找出最频繁的市场阶段
    most_common_phase = max(market_phase_counts.items(), key=lambda x: x[1])[0] if market_phase_counts else "unknown"
    
    # 找出最频繁的风险等级
    most_common_risk = max(risk_level_counts.items(), key=lambda x: x[1])[0] if risk_level_counts else "medium"
    
    # 找出最强模式（累计数量最多）
    mode_totals = [
        ("mode1_retracement", mode_counts["mode1_total"]),
        ("mode2_breakout", mode_counts["mode2_total"]),
        ("mode3_small_bullish", mode_counts["mode3_total"]),
        ("mode4_second_wave", mode_counts["mode4_total"])
    ]
    most_common_mode = max(mode_totals, key=lambda x: x[1])[0] if any(x[1] > 0 for x in mode_totals) else "unknown"
    
    return {
        "metadata": {
            "index_version": "1.0",
            "created_at": datetime.now().isoformat(),
            "total_reports": total_reports,
            "date_range": {
                "earliest": reports[-1]["date"] if reports else None,
                "latest": reports[0]["date"] if reports else None
            },
            "statistics": {
                "market_phases": market_phase_counts,
                "risk_levels": risk_level_counts,
                "most_common_phase": most_common_phase,
                "most_common_risk": most_common_risk,
                "most_common_mode": most_common_mode,
                "total_pattern_counts": mode_counts
            }
        },
        "reports": reports
    }


def main():
    """主函数"""
    print("==================================================")
    print("日报历史索引生成器")
    print("==================================================")
    
    # 确保目录存在
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    
    # 扫描历史日报
    reports = scan_history_reports()
    
    if not reports:
        print("No historical reports found")
        # 创建空的索引文件
        empty_index = {
            "metadata": {
                "index_version": "1.0",
                "created_at": datetime.now().isoformat(),
                "total_reports": 0,
                "date_range": {
                    "earliest": None,
                    "latest": None
                },
                "statistics": {
                    "market_phases": {},
                    "risk_levels": {},
                    "most_common_phase": "unknown",
                    "most_common_risk": "medium",
                    "most_common_mode": "unknown",
                    "total_pattern_counts": {
                        "mode1_total": 0,
                        "mode2_total": 0,
                        "mode3_total": 0,
                        "mode4_total": 0
                    }
                }
            },
            "reports": []
        }
        
        with open(INDEX_FILE, 'w', encoding='utf-8') as f:
            json.dump(empty_index, f, ensure_ascii=False, indent=2)
        
        print(f"Created empty index file: {INDEX_FILE}")
        return
    
    # 构建索引
    index = build_index(reports)
    
    # 保存索引文件
    with open(INDEX_FILE, 'w', encoding='utf-8') as f:
        json.dump(index, f, ensure_ascii=False, indent=2)
    
    print(f"\nIndex saved to: {INDEX_FILE}")
    print(f"Total reports indexed: {len(reports)}")
    print(f"Date range: {index['metadata']['date_range']['earliest']} to {index['metadata']['date_range']['latest']}")
    print(f"Most common market phase: {index['metadata']['statistics']['most_common_phase']}")
    print(f"Most common risk level: {index['metadata']['statistics']['most_common_risk']}")
    print(f"Most common pattern: {index['metadata']['statistics']['most_common_mode']}")
    print("==================================================")


if __name__ == "__main__":
    main()