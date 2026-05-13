# Phase-2.4B-Stable 稳定运行期配置指南

## 概述
**Phase-2.4B-Stable** 是一个为期14-30天的稳定运行期，目标是通过持续运行验证系统的稳定性和可靠性，为后续的SOUL_INSIGHT_MODE做准备。

## 核心目标
- ✅ 连续稳定运行14-30天
- ✅ 验证所有核心组件正常工作
- ✅ 积累足够的历史数据
- ✅ 不进行任何自动化学习或调整

## 每日检查项

### 1. K线更新是否成功
- 检查目录: `data/kline_daily/`
- 检查日志: `data/update_logs/kline_update_YYYYMMDD.json`
- 要求: 每天必须有成功的K线更新记录

### 2. 技术因子缓存是否生成
- 检查目录: `features/cache/`
- 要求: `valid_count >= 4000`
- 验证: 检查`*_factors.json`文件的valid字段

### 3. 四模式扫描是否完成
- 检查目录: `candidate_pool/`
- 检查文件: `candidates_YYYY-MM-DD.json`
- 要求: 每天生成候选列表

### 4. 日报是否生成
- 检查目录: `reports/history/`
- 检查文件: `YYYY-MM-DD.md`
- 要求: 每天必须有日报文件

### 5. 情绪快照是否生成
- 检查目录: `emotion_engine/snapshots/`
- 检查文件: `emotion_YYYY-MM-DD.json`
- 要求: 每天生成情绪快照

### 6. 情绪历史分析是否更新
- 检查目录: `emotion_engine/analyzer/`
- 检查文件: `emotion_history_analysis.json`
- 要求: 定期更新分析结果

### 7. Replay缓存是否正常
- 检查目录: `replay_engine/cache/`
- 要求: 有24小时内的缓存文件

### 8. GitHub push 是否成功
- 检查: `git status`是否有未推送提交
- 要求: 所有变更及时推送

## 关键监控指标

| 指标 | 标准 | 类型 | 重要性 |
|------|------|------|--------|
| daily_pipeline_success | true | boolean | 🔴 关键 |
| factor_valid_count | ≥4000 | integer | 🔴 关键 |
| mode_candidate_count | ≥1 | integer | 🟡 重要 |
| emotion_score | -100~100 | float | 🟡 重要 |
| market_phase | stable/volatile/... | string | 🟢 参考 |
| risk_level | low/medium/high | string | 🟡 重要 |

## 异常告警规则

触发警告的条件：
1. `factor_valid_count < 4000`
2. 日报未生成
3. 情绪快照缺失
4. 任何检查项返回error状态

警告输出：
- 控制台输出警告信息
- 健康报告中标记warnings字段
- 每日汇总时高亮显示

## 禁止事项 ⚠️

**绝对禁止**以下操作：
1. ❌ **自动学习** - 禁止AI自主学习和经验积累
2. ❌ **baseline修改** - 禁止修改基线策略配置
3. ❌ **权重调整** - 禁止调整策略权重
4. ❌ **自动交易** - 禁止触发任何交易
5. ❌ **AI自治** - 禁止AI自主决策和行动

## 运行周期

### 第一阶段：启动验证 (第1-3天)
- 验证所有检查项正常工作
- 建立健康报告基线
- 确认关键指标达标

### 第二阶段：稳定运行 (第4-14天)
- 连续10天以上无重大警告
- 所有关键指标持续达标
- 系统运行稳定可靠

### 第三阶段：延长验证 (第15-30天)
- 可选延长运行时间
- 进一步验证系统稳定性
- 为下一阶段积累数据

## 阶段结束评估

当满足以下条件时，可以结束Phase-2.4B：
1. ✅ 连续稳定运行14天以上
2. ✅ 所有关键指标达标
3. ✅ 无严重警告
4. ✅ 系统监控稳定

**评估方向**：
- 🔄 **SOUL_INSIGHT_MODE** - ✅ 推荐方向
- 🔄 **AUTO_LEARNING_MODE** - ❌ 不推荐

## 自动化脚本

### 每日健康检查
```bash
cd /Users/gino/project_ai_trading
python3 system_health/daily_health_check.py
```

### 禁止事项验证
```bash
python3 system_health/verify_prohibitions.py
```

### 报告汇总
```bash
python3 system_health/summarize_health_reports.py
```

## 目录结构

```
system_health/
├── daily_health_check.py      # 每日健康检查主脚本
├── verify_prohibitions.py     # 禁止事项验证脚本
├── summarize_health_reports.py # 报告汇总脚本
├── phase_2_4b_config.json     # 配置定义
├── history/                   # 历史报告
│   ├── YYYY-MM-DD.json        # 每日健康报告
│   └── index.json            # 报告索引
├── violations/               # 违规记录
│   └── violations_*.json     # 违规报告
└── stability_report_*.json   # 稳定性报告
```

## 飞书通知集成

健康检查完成后，可通过飞书发送通知：
- 成功：简单状态通知
- 警告：详细警告信息
- 违规：紧急违规告警

## 故障排查

### 常见问题
1. **因子缓存不足**：检查数据源连接，验证数据质量
2. **日报未生成**：检查报告引擎日志，验证模板文件
3. **情绪快照缺失**：检查情绪引擎配置，验证数据输入
4. **Git推送失败**：检查网络连接，验证权限设置

### 恢复步骤
1. 检查日志文件定位问题
2. 手动运行相关组件测试
3. 修复配置或数据问题
4. 重新运行健康检查

## 退出标准

当以下任一情况发生时，可以提前退出Phase-2.4B：
1. 🔴 连续3天出现关键错误
2. 🔴 系统核心组件无法修复
3. 🔴 数据源长期不可用
4. 🟡 用户主动终止稳定运行期

退出后需：
1. 记录退出原因
2. 分析问题根本原因
3. 制定修复计划
4. 重新启动稳定运行期

---

**Phase-2.4B-Stable** 是系统走向成熟的必经阶段，通过严格的稳定运行验证，为后续的智能洞察模式打下坚实基础。