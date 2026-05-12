import json
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)


def load_technical_factors():
    """加载技术因子缓存"""
    cache_path = BASE_DIR.parent / "features" / "cache" / "daily_technical_factors.json"
    if not cache_path.exists():
        raise FileNotFoundError(f"技术因子文件不存在: {cache_path}")
    with open(cache_path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_strategy_results():
    """加载策略扫描结果"""
    today = datetime.now().strftime("%Y-%m-%d")
    strategy_path = BASE_DIR.parent / "strategies" / "outputs" / f"original_four_modes_{today}.json"
    if not strategy_path.exists():
        # 尝试查找最新文件
        outputs_dir = BASE_DIR.parent / "strategies" / "outputs"
        pattern = f"original_four_modes_*.json"
        files = sorted(outputs_dir.glob(pattern))
        if not files:
            raise FileNotFoundError(f"策略结果文件不存在: {strategy_path}")
        strategy_path = files[-1]  # 最新文件
    with open(strategy_path, "r", encoding="utf-8") as f:
        return json.load(f)


def build_market_summary():
    today = datetime.now().strftime("%Y-%m-%d")
    
    # 加载数据
    try:
        factors_data = load_technical_factors()
        strategy_data = load_strategy_results()
    except FileNotFoundError as e:
        print(f"[ERROR] 数据文件缺失: {e}")
        # 返回占位数据，但保持结构完整
        summary = {
            "date": today,
            "northbound": "数据文件缺失，无法生成北向资金分析",
            "main_sector": "数据文件缺失，无法生成板块强度分析",
            "institution": "数据文件缺失，无法生成机构净买分析",
            "emotion": "数据文件缺失，无法生成情绪分析",
            "tomorrow_focus": "数据文件缺失，无法生成明日关注点",
            "strategy_summary": {
                "mode_1_count": 0,
                "mode_2_count": 0,
                "mode_3_count": 0,
                "mode_4_count": 0,
                "any_mode_count": 0,
                "total_symbols": 0,
                "hot_mode": "数据缺失",
                "risk_note": "数据文件缺失，无法生成风险提示"
            }
        }
        output_path = DATA_DIR / "market_summary.json"
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        print(f"[WARN] market_summary generated with placeholder: {output_path}")
        return
    
    # 提取策略统计
    stats = strategy_data.get("statistics", {})
    mode_1 = stats.get("mode_1_count", 0)
    mode_2 = stats.get("mode_2_count", 0)
    mode_3 = stats.get("mode_3_count", 0)
    mode_4 = stats.get("mode_4_count", 0)
    any_mode = stats.get("any_mode_count", 0)
    total_symbols = stats.get("total_symbols", 0)
    
    # 确定热门模式
    mode_counts = {
        "回踩止跌型": mode_1,
        "突破启动型": mode_2,
        "小阳启动型": mode_3,
        "2波启动型": mode_4
    }
    hot_mode = max(mode_counts, key=mode_counts.get)
    hot_count = mode_counts[hot_mode]
    
    # 风险提示
    risk_note = ""
    if mode_2 == 0:
        risk_note = "突破启动型数量为0，说明市场追涨环境较弱，资金观望情绪浓厚。"
    elif mode_2 < 10:
        risk_note = f"突破启动型仅{mode_2}只，市场追涨动力不足。"
    elif mode_1 > 200:
        risk_note = f"回踩止跌型{mode_1}只，市场处于调整阶段，注意风险。"
    else:
        risk_note = "四模式分布正常，市场情绪稳定。"
    
    # 构建策略摘要
    strategy_summary = {
        "mode_1_count": mode_1,
        "mode_2_count": mode_2,
        "mode_3_count": mode_3,
        "mode_4_count": mode_4,
        "any_mode_count": any_mode,
        "total_symbols": total_symbols,
        "hot_mode": f"{hot_mode} ({hot_count})",
        "risk_note": risk_note,
        "mode_names": {
            "mode_1": "回踩止跌型",
            "mode_2": "突破启动型",
            "mode_3": "小阳启动型",
            "mode_4": "2波启动型"
        }
    }
    
    # 北向资金分析（基于技术因子）
    northbound_analysis = "技术因子分析："
    if mode_3 > 300:
        northbound_analysis += " 小阳启动型占比较高，市场情绪偏暖。"
    else:
        northbound_analysis += " 小阳启动型数量一般，市场情绪中性。"
    
    # 板块强度分析（简化）
    main_sector = "基于四模式分布："
    if mode_1 > 150:
        main_sector += " 回踩止跌型占优，市场处于调整期。"
    elif mode_3 > 250:
        main_sector += " 小阳启动型占优，市场温和上涨。"
    else:
        main_sector += " 四模式分布均衡，市场震荡整理。"
    
    # 机构净买分析
    institution_analysis = "模式扫描结果："
    if mode_4 > 100:
        institution_analysis += " 2波启动型较多，机构可能开始布局。"
    else:
        institution_analysis += " 2波启动型偏少，机构观望。"
    
    # 情绪分析
    emotion_analysis = "市场情绪："
    if mode_2 > 50:
        emotion_analysis += " 突破启动型较多，市场情绪积极。"
    elif mode_2 == 0:
        emotion_analysis += " 无突破启动型，市场情绪谨慎。"
    else:
        emotion_analysis += " 市场情绪中性偏弱。"
    
    # 明日关注点
    tomorrow_focus = "关注："
    if mode_1 > 100:
        tomorrow_focus += " 回踩止跌型股票，寻找反弹机会。"
    if mode_3 > 200:
        tomorrow_focus += " 小阳启动型股票，温和上涨趋势。"
    if mode_4 > 100:
        tomorrow_focus += " 2波启动型股票，二次上涨机会。"
    if not (mode_1 > 100 or mode_3 > 200 or mode_4 > 100):
        tomorrow_focus += " 市场无明显热点，建议观望。"
    
    summary = {
        "date": today,
        "northbound": northbound_analysis,
        "main_sector": main_sector,
        "institution": institution_analysis,
        "emotion": emotion_analysis,
        "tomorrow_focus": tomorrow_focus,
        "strategy_summary": strategy_summary
    }
    
    output_path = DATA_DIR / "market_summary.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    
    print(f"[OK] market_summary generated: {output_path}")
    print(f"[INFO] 四模式统计: 回踩止跌型={mode_1}, 突破启动型={mode_2}, 小阳启动型={mode_3}, 2波启动型={mode_4}")
    print(f"[INFO] 候选总数: {any_mode}/{total_symbols}")
    print(f"[INFO] 热门模式: {hot_mode} ({hot_count})")
    print(f"[INFO] 风险提示: {risk_note}")


if __name__ == "__main__":
    build_market_summary()