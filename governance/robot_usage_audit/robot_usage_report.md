# Robot Usage Audit Report
*Generated: 2026-05-14 18:48:14*

## 汇总

| Robot | 角色 | 最近运行 | 7D会话 | 7D消息 | OpenClaw调用 | 输出文件 | 错误数 | 被调用来源 | 等级 | 建议 |
|-------|------|----------|--------|--------|-------------|---------|--------|-----------|------|------|
| **robot-1** | SysAdmin — 系统维护机器人 | 2026-05-14T18:03 | 55 | 2,865 | 141 | 92 (7.9MB) | 159 | 无 | **A** | ✅ 保留 - 核心 |
| **robot-2** | Exec-Bridge — OpenClaw 执行桥接机器人 | 2026-05-14T18:03 | 18 | 949 | 109 | 38 (3.5MB) | 189 | 无 | **B** | ⚠️ 保留观察 |
| **robot-3** | Research — 综合研究分析机器人 | 2026-05-14T18:14 | 81 | 3,122 | 200 | 30 (2.4MB) | 159 | 无 | **A** | ✅ 保留 - 核心 |
| **robot-4** | Sandbox — 宏观研究机器人 | 2026-05-14T18:03 | 28 | 1,262 | 91 | 28 (2.1MB) | 192 | 无 | **B** | ⚠️ 保留观察 |
| **robot-5** | Risk — 风险控制 / 持仓管理机器人 | 2026-05-14T18:03 | 8 | 283 | 27 | 21 (1.6MB) | 173 | 无 | **C** | ❓ 评估整合 |
| **robot-6** | 📊 市场分析专家 | 2026-05-14T18:03 | 70 | 4,108 | 405 | 48 (3.6MB) | 163 | 无 | **A** | ✅ 保留 - 核心 |
| **robot-7** | 四种选股模式专家 | 2026-05-14T18:03 | 38 | 2,374 | 2 | 6 (0.0MB) | 146 | 无 | **B** | ⚠️ 保留观察 |
| **robot-8** | 选股机器人 | 2026-05-14T18:03 | 36 | 1,490 | 6 | 6 (0.0MB) | 224 | 无 | **B** | ⚠️ 保留观察 |

## 等级说明

| 等级 | 标准 | 行动 |
|------|------|------|
| **A** | 高活跃(≥30会话/7d) + 有大量OpenClaw调用 + 被核心系统依赖 | ✅ 保留，核心成员 |
| **B** | 中等活跃(10-30会话) 或 有稳定输出 | ⚠️ 保留观察，持续监控 |
| **C** | 低活跃(<10会话) 或 功能可替代 | ❓ 评估是否合并到其他Robot |
| **D** | 14天未运行 或 无输出文件 或 无日志 | 🚫 建议归档 |

## OpenClaw 调用排名（7天）

| 排名 | Robot | 调用次数 |
|------|-------|---------|
| 1 | robot-6 | 405 |
| 2 | robot-3 | 200 |
| 3 | robot-1 | 141 |
| 4 | robot-2 | 109 |
| 5 | robot-4 | 91 |
| 6 | robot-5 | 27 |
| 7 | robot-8 | 6 |
| 8 | robot-7 | 2 |

## 依赖链分析

```
核心调用链 (Phase-1.6 日 pipeline):

  Scheduler → OpenClaw
  Scheduler → robot-3 FeatureEngine
  Scheduler → robot-4 PatternMatch
  Scheduler → robot-5 RiskAudit
  Scheduler → Main Aggregate
  OpenClaw → robot-3 FeatureEngine
  robot-3 FeatureEngine → robot-4 PatternMatch
  robot-3 FeatureEngine → Main Aggregate
  robot-4 PatternMatch → robot-5 RiskAudit
  robot-5 RiskAudit → Main Aggregate

被高频依赖的Robot:
  robot-3 FeatureEngine: 被 Scheduler, OpenClaw 调用
  robot-4 PatternMatch: 被 Scheduler, robot-3 FeatureEngine 调用
  Main Aggregate: 被 Scheduler, robot-3 FeatureEngine, robot-5 RiskAudit 调用
  robot-5 RiskAudit: 被 Scheduler, robot-4 PatternMatch 调用
  OpenClaw: 被 Scheduler 调用
```

## 关键发现

1. **robot-6** OpenClaw调用量最高(405次/7d)，是主力执行Robot
2. **robot-7** OpenClaw调用极少(2次)，角色定位不清，建议评估
3. **robot-8** OpenClaw调用极少(6次)，但有38个会话，可能主要是研究用途
4. **robot-5** 活跃度最低(8会话)，建议确认是否可合并
5. 所有Robot最近运行时间均在24小时内，无真正闲置

## 建议行动

| Robot | 当前状态 | 建议 |
|-------|---------|------|
| robot-1 | A级(高贡献) | 继续当前模式，保持高活跃 |
| robot-2 | B级(中贡献) | 明确分工，减少重复调用 |
| robot-3 | A级(高贡献) | 继续当前模式，保持高活跃 |
| robot-4 | B级(中贡献) | 明确分工，减少重复调用 |
| robot-5 | C级(低贡献) | 评估是否可以合并到robot-3或robot-6 |
| robot-6 | A级(高贡献) | 继续当前模式，保持高活跃 |
| robot-7 | B级(中贡献) | 明确分工，减少重复调用 |
| robot-8 | B级(中贡献) | 明确分工，减少重复调用 |