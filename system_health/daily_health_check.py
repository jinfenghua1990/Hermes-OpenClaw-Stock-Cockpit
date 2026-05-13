#!/usr/bin/env python3
"""
Phase-2.4B-Stable 每日健康检查脚本
"""

import os
import json
import datetime
import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
SYSTEM_HEALTH_DIR = BASE_DIR / "system_health"
HISTORY_DIR = SYSTEM_HEALTH_DIR / "history"
CURRENT_DATE = datetime.datetime.now().strftime("%Y-%m-%d")

def check_kline_update():
    """检查K线更新是否成功"""
def check_kline_update():
    """检查K线数据是否更新"""
    try:
        kline_dir = BASE_DIR / "data" / "kline_daily"
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        
        if not kline_dir.exists():
            return {"status": "error", "message": "K线数据目录不存在"}
        
        # 检查是否有今天的K线文件
        today_files = list(kline_dir.glob(f"*_{today}.csv"))
        if today_files:
            return {"status": "success", "message": f"找到{len(today_files)}个今日K线文件", "updated_stocks": len(today_files)}
        else:
            return {"status": "warning", "message": "未找到今日K线更新记录"}
    except Exception as e:
        return {"status": "error", "message": f"检查K线更新时出错: {str(e)}"}

def check_factor_cache():
    """检查技术因子缓存是否生成"""
    try:
        factor_cache_dir = BASE_DIR / "features" / "cache"
        
        if not factor_cache_dir.exists():
            return {"status": "error", "message": "因子缓存目录不存在"}
        
        cache_files = list(factor_cache_dir.glob("*_factors.json"))
        total_valid_count = 0
        
        for cache_file in cache_files:
            try:
                with open(cache_file, 'r') as f:
                    data = json.load(f)
                    
                    # 优先读取顶层的valid字段
                    if "valid" in data and isinstance(data["valid"], (int, float)):
                        total_valid_count += int(data["valid"])
                    # 如果没有valid字段，但有factors字段，计算factors数量
                    elif "factors" in data and isinstance(data["factors"], dict):
                        total_valid_count += len(data["factors"])
                    else:
                        # 如果都没有，尝试计算总记录数
                        total_valid_count += len(data)
                        
            except Exception as e:
                print(f"警告: 读取缓存文件 {cache_file.name} 时出错: {str(e)}")
                continue
        
        return {
            "status": "success" if total_valid_count >= 4000 else "warning",
            "message": f"有效因子缓存数量: {total_valid_count}",
            "valid_count": total_valid_count,
            "threshold": 4000
        }
    except Exception as e:
        return {"status": "error", "message": f"检查因子缓存时出错: {str(e)}"}

def check_mode_scan():
    """检查四模式扫描是否完成"""
    try:
        strategies_dir = BASE_DIR / "strategies" / "outputs"
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        
        if not strategies_dir.exists():
            return {"status": "error", "message": "策略输出目录不存在"}
        
        today_file = strategies_dir / f"original_four_modes_{today}.json"
        
        if today_file.exists():
            with open(today_file, 'r') as f:
                data = json.load(f)
                # 计算所有模式的总数
                total_count = 0
                for mode in ["mode_1_revert", "mode_2_breakout", "mode_3_xiaoyang", "mode_4_second_wave"]:
                    if mode in data:
                        total_count += len(data[mode])
                
                return {
                    "status": "success",
                    "message": f"四模式扫描完成，找到{total_count}个候选",
                    "candidate_count": total_count
                }
        else:
            return {"status": "warning", "message": "今日四模式扫描未完成"}
    except Exception as e:
        return {"status": "error", "message": f"检查模式扫描时出错: {str(e)}"}

def check_daily_report():
    """检查日报是否生成"""
    try:
        reports_dir = BASE_DIR / "reports" / "history"
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        
        if not reports_dir.exists():
            return {"status": "error", "message": "报告目录不存在"}
        
        today_report = reports_dir / f"{today}.md"
        
        if today_report.exists():
            report_size = today_report.stat().st_size
            return {
                "status": "success",
                "message": f"日报已生成 ({report_size}字节)",
                "file_size": report_size
            }
        else:
            return {"status": "warning", "message": "今日日报未生成"}
    except Exception as e:
        return {"status": "error", "message": f"检查日报时出错: {str(e)}"}

def check_emotion_snapshot():
    """检查情绪快照是否生成"""
    try:
        emotion_dir = BASE_DIR / "emotion_engine"
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        
        if not emotion_dir.exists():
            return {"status": "error", "message": "情绪引擎目录不存在"}
        
        # 检查快照缓存文件
        snapshot_file = emotion_dir / "cache" / "market_emotion_snapshot.json"
        
        if snapshot_file.exists():
            with open(snapshot_file, 'r') as f:
                data = json.load(f)
                emotion_score = data.get("emotion_score", 0)
                return {
                    "status": "success",
                    "message": f"情绪快照已生成 (分数: {emotion_score})",
                    "emotion_score": emotion_score
                }
        
        return {"status": "warning", "message": "今日情绪快照未生成"}
    except Exception as e:
        return {"status": "error", "message": f"检查情绪快照时出错: {str(e)}"}

def check_emotion_history():
    """检查情绪历史分析是否更新"""
    try:
        emotion_dir = BASE_DIR / "emotion_engine"
        history_analysis = emotion_dir / "analyzer" / "emotion_history_analysis.json"
        
        if history_analysis.exists():
            with open(history_analysis, 'r') as f:
                data = json.load(f)
                last_update = data.get("last_updated", "")
                return {
                    "status": "success",
                    "message": f"情绪历史分析已更新 ({last_update})",
                    "last_updated": last_update
                }
        else:
            return {"status": "warning", "message": "情绪历史分析文件不存在"}
    except Exception as e:
        return {"status": "error", "message": f"检查情绪历史分析时出错: {str(e)}"}

def check_replay_cache():
    """检查Replay缓存是否正常"""
    try:
        replay_dir = BASE_DIR / "replay_engine" / "cache"
        
        if not replay_dir.exists():
            return {"status": "warning", "message": "Replay缓存目录不存在"}
        
        cache_files = list(replay_dir.glob("*.json"))
        
        if cache_files:
            latest_file = max(cache_files, key=lambda x: x.stat().st_mtime)
            file_time = datetime.datetime.fromtimestamp(latest_file.stat().st_mtime)
            age_hours = (datetime.datetime.now() - file_time).total_seconds() / 3600
            
            if age_hours < 24:
                return {
                    "status": "success",
                    "message": f"Replay缓存正常 (最新: {file_time.strftime('%Y-%m-%d %H:%M')})",
                    "latest_file": latest_file.name,
                    "age_hours": age_hours
                }
            else:
                return {"status": "warning", "message": f"Replay缓存已过期 ({age_hours:.1f}小时)"}
        else:
            return {"status": "warning", "message": "无Replay缓存文件"}
    except Exception as e:
        return {"status": "error", "message": f"检查Replay缓存时出错: {str(e)}"}

def check_git_push():
    """检查GitHub push是否成功"""
    try:
        # 获取最近一次提交信息
        result = subprocess.run(
            ["git", "log", "-1", "--oneline"],
            cwd=BASE_DIR,
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            last_commit = result.stdout.strip()
            
            # 检查是否有未推送的提交
            result = subprocess.run(
                ["git", "status", "--porcelain", "-b"],
                cwd=BASE_DIR,
                capture_output=True,
                text=True
            )
            
            if "ahead" in result.stdout:
                return {
                    "status": "warning",
                    "message": f"有未推送的提交: {last_commit}",
                    "last_commit": last_commit
                }
            else:
                return {
                    "status": "success",
                    "message": f"最新提交已推送: {last_commit}",
                    "last_commit": last_commit
                }
        else:
            return {"status": "error", "message": "无法获取git提交信息"}
    except Exception as e:
        return {"status": "error", "message": f"检查git推送时出错: {str(e)}"}

def check_system_monitor():
    """检查系统监控状态"""
    try:
        monitor_dir = BASE_DIR / "system_monitor"
        monitor_file = monitor_dir / "system_status.json"
        
        if monitor_file.exists():
            with open(monitor_file, 'r') as f:
                data = json.load(f)
                last_update = data.get("timestamp", "")
                
                # 检查是否在30分钟内更新过
                if last_update:
                    try:
                        update_time = datetime.datetime.fromisoformat(last_update.replace('Z', '+00:00'))
                        age_minutes = (datetime.datetime.now(datetime.timezone.utc) - update_time).total_seconds() / 60
                        
                        if age_minutes < 30:
                            return {
                                "status": "success",
                                "message": f"系统监控正常 (最近更新: {age_minutes:.1f}分钟前)",
                                "age_minutes": age_minutes
                            }
                        else:
                            return {
                                "status": "warning",
                                "message": f"系统监控更新滞后 ({age_minutes:.1f}分钟前)",
                                "age_minutes": age_minutes
                            }
                    except:
                        return {"status": "success", "message": "系统监控文件存在"}
        
        return {"status": "warning", "message": "系统监控文件不存在"}
    except Exception as e:
        return {"status": "error", "message": f"检查系统监控时出错: {str(e)}"}

def generate_health_report():
    """生成健康报告"""
    checks = {
        "kline_update": check_kline_update(),
        "factor_cache": check_factor_cache(),
        "mode_scan": check_mode_scan(),
        "daily_report": check_daily_report(),
        "emotion_snapshot": check_emotion_snapshot(),
        "emotion_history": check_emotion_history(),
        "replay_cache": check_replay_cache(),
        "git_push": check_git_push(),
        "system_monitor": check_system_monitor()
    }
    
    # 计算总体状态
    status_counts = {"success": 0, "warning": 0, "error": 0}
    for check in checks.values():
        status_counts[check["status"]] += 1
    
    overall_status = "success"
    if status_counts["error"] > 0:
        overall_status = "error"
    elif status_counts["warning"] > 0:
        overall_status = "warning"
    
    # 关键指标
    factor_valid_count = checks["factor_cache"].get("valid_count", 0)
    candidate_count = checks["mode_scan"].get("candidate_count", 0)
    emotion_score = checks["emotion_snapshot"].get("emotion_score", 0)
    
    # 检查是否需要警告
    warnings = []
    if factor_valid_count < 4000:
        warnings.append(f"因子缓存数量不足: {factor_valid_count} < 4000")
    if checks["daily_report"]["status"] == "warning":
        warnings.append("日报未生成")
    if checks["emotion_snapshot"]["status"] == "warning":
        warnings.append("情绪快照缺失")
    
    health_report = {
        "timestamp": datetime.datetime.now().isoformat(),
        "date": CURRENT_DATE,
        "phase": "Phase-2.4B-Stable",
        "overall_status": overall_status,
        "status_counts": status_counts,
        "critical_metrics": {
            "daily_pipeline_success": overall_status == "success",
            "factor_valid_count": factor_valid_count,
            "mode_candidate_count": candidate_count,
            "emotion_score": emotion_score,
            "market_phase": "stable",  # 需要从系统监控获取
            "risk_level": "low" if overall_status == "success" else "medium"
        },
        "checks": checks,
        "warnings": warnings,
        "notes": "Phase-2.4B-Stable 稳定运行期，禁止自动学习、baseline修改、权重调整、自动交易、AI自治"
    }
    
    return health_report

def save_health_report(report):
    """保存健康报告"""
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    
    output_file = HISTORY_DIR / f"{CURRENT_DATE}.json"
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    
    return output_file

def main():
    print(f"正在执行 Phase-2.4B-Stable 每日健康检查 ({CURRENT_DATE})")
    print("=" * 60)
    
    # ==================================================
    # 自动刷新 runtime_usage_summary.json
    # ==================================================
    builder_path = BASE_DIR / "governance" / "runtime_usage_builder.py"
    if builder_path.exists():
        try:
            result = subprocess.run(
                [sys.executable, str(builder_path)],
                cwd=BASE_DIR,
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode == 0:
                print("[Runtime Builder] " + result.stdout.strip())
            else:
                print(f"[Runtime Builder] ⚠️ 警告: {result.stderr.strip()}")
        except Exception as e:
            print(f"[Runtime Builder] ⚠️ 异常: {e}")
    else:
        print("[Runtime Builder] ⚠️ 文件不存在，跳过")
    print()
    
    # 生成健康报告
    report = generate_health_report()
    
    # 保存报告
    output_file = save_health_report(report)
    
    # 打印摘要
    print(f"总体状态: {report['overall_status'].upper()}")
    print(f"成功: {report['status_counts']['success']} | 警告: {report['status_counts']['warning']} | 错误: {report['status_counts']['error']}")
    print()
    
    print("关键指标:")
    print(f"  因子缓存数量: {report['critical_metrics']['factor_valid_count']}")
    print(f"  模式候选数量: {report['critical_metrics']['mode_candidate_count']}")
    print(f"  情绪分数: {report['critical_metrics']['emotion_score']}")
    print()
    
    if report['warnings']:
        print("⚠️  警告:")
        for warning in report['warnings']:
            print(f"  - {warning}")
        print()
    
    # 详细检查结果
    print("详细检查结果:")
    for check_name, result in report['checks'].items():
        status_emoji = "✅" if result['status'] == 'success' else "⚠️ " if result['status'] == 'warning' else "❌"
        print(f"  {status_emoji} {check_name}: {result['message']}")
    
    print()
    print(f"健康报告已保存到: {output_file}")
    
    return report

if __name__ == "__main__":
    main()