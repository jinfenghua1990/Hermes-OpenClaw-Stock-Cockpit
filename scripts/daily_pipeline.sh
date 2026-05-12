#!/bin/bash

echo "=================================================="
echo "[START] Hermes Daily Pipeline"
echo "=================================================="

# 设置工作目录
cd "$(dirname "$0")/.." || exit 1

# 创建日志目录
mkdir -p logs

# 记录开始时间
START_TIME=$(date '+%Y-%m-%d %H:%M:%S')
echo "[TIME] Pipeline started at: $START_TIME"

# 1. 构建技术因子缓存
echo "[1/4] Build Technical Factor Cache"
python features/build_technical_factor_cache.py
if [ $? -ne 0 ]; then
    echo "[ERROR] Technical Factor Cache failed"
    exit 1
fi

# 2. 运行原版四种模式扫描器
echo "[2/4] Run Original Four Modes Scanner"
python strategies/original_four_modes_scanner.py
if [ $? -ne 0 ]; then
    echo "[ERROR] Four Modes Scanner failed"
    exit 1
fi

# 3. 构建市场摘要
echo "[3/4] Build Market Summary"
python report_engine/generators/build_market_summary.py
if [ $? -ne 0 ]; then
    echo "[ERROR] Market Summary failed"
    exit 1
fi

# 4. 生成日报
echo "[4/4] Generate Daily Report"
python report_engine/generators/generate_daily_report.py
if [ $? -ne 0 ]; then
    echo "[ERROR] Daily Report failed"
    exit 1
fi

# 5. 归档历史日报
echo "[5/5] Archive Historical Reports"
mkdir -p reports/history
cp report_engine/outputs/*.md reports/history/
echo "[ARCHIVE] Daily reports archived to reports/history/"

# 6. 更新日报索引
echo "[6/6] Update Report Index"
python reports/build_report_index.py
if [ $? -ne 0 ]; then
    echo "[WARNING] Report index update failed"
fi

# 记录结束时间
END_TIME=$(date '+%Y-%m-%d %H:%M:%S')
echo "[TIME] Pipeline finished at: $END_TIME"

echo "=================================================="
echo "[DONE] Hermes Daily Pipeline Finished"
echo "=================================================="

# 输出文件列表
echo "[FILES] Generated files:"
echo "  - features/cache/daily_technical_factors.json"
echo "  - strategies/outputs/original_four_modes_$(date '+%Y-%m-%d').json"
echo "  - report_engine/data/market_summary.json"
echo "  - report_engine/outputs/$(date '+%Y-%m-%d').md"
echo "  - reports/history/$(date '+%Y-%m-%d').md"
echo "  - reports/history/index.json"