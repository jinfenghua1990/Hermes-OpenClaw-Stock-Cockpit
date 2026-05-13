#!/bin/bash
# Phase-2.4B-Stable 每日健康检查脚本
# 每天收盘后16:30执行

cd /Users/gino/project_ai_trading

echo "=================================================="
echo "Phase-2.4B-Stable 每日健康检查"
echo "开始时间: $(date)"
echo "=================================================="

# 执行健康检查
python3 system_health/daily_health_check.py

echo ""
echo "=================================================="
echo "健康检查完成"
echo "完成时间: $(date)"
echo "=================================================="

# 更新历史索引
python3 system_health/summarize_health_reports.py

echo ""
echo "=================================================="
echo "历史索引已更新"
echo "=================================================="

# 检查是否需要发送警告
CHECK_FILE="system_health/history/$(date +%Y-%m-%d).json"
if [ -f "$CHECK_FILE" ]; then
    WARNINGS=$(grep -c '"warnings"' "$CHECK_FILE" || echo "0")
    if [ "$WARNINGS" -gt 0 ]; then
        echo "⚠️  发现警告，请检查详细报告"
    fi
fi

echo ""
echo "Phase-2.4B-Stable 稳定运行期"
echo "禁止: 自动学习、baseline修改、权重调整、自动交易、AI自治"