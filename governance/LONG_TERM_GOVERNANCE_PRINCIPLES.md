# AI Research Governance Platform — 长期治理原则
> 版本：v1.0 | 日期：2026-05-13 | 状态：PERMANENT（永久保留）

---

## 一、系统当前定位

**当前系统定位：AI Research Governance Cockpit Platform**

不是普通 AI 炒股机器人。

**当前核心模块：**
- Governance（治理快照）
- Replay（回放审计）
- Snapshot（状态快照）
- Risk Validation（风险价格验证）
- Market Structure（市场结构引擎）
- Paper Execution（模拟盘执行桥）
- Execution Audit（执行审计）
- Multi-Agent Observe Simulation（多智能体观察仿真）

---

## 二、当前运行模式（必须长期保留）

系统必须保持：
- `SOUL_MODE = OBSERVE_ONLY`
- `account_mode = PAPER_ONLY`

**当前仅允许：** 东方财富模拟盘

**禁止：**
- 实盘
- 真实资金
- 真实券商 API
- 杠杆
- 融资融券

---

## 三、当前允许放开的能力

允许：
1. robot_1~5 多 Agent 协作
2. 自动研究
3. 自动模拟盘执行
4. 自动复核
5. 多观点冲突
6. 多层 Trace
7. 自动 Replay
8. 自动 Audit
9. Shadow Strategy 实验
10. 自动实验性策略进化（仅限实验区）

---

## 四、当前绝对不能关闭的治理底线（必须永久保留）

以下属于**系统治理底线**，禁止关闭：

1. `PAPER_ONLY`（仅模拟盘）
2. `Risk Validation`（风险价格验证）
3. `Replay Snapshot`（Replay 回放）
4. `Governance Snapshot`（治理快照）
5. `Baseline Freeze`（Baseline 冻结）
6. `Execution Audit`（执行审计）
7. `Runtime Health Check`
8. `Snapshot Consistency`
9. `Replay Consistency Check`

---

## 五、关于 Baseline 的长期原则（非常重要）

### 四种选股模式（原版 baseline）

属于：**系统治理锚点（Governance Anchor）**

**作用：**
- Replay 对照
- Governance 对照
- 风险比较
- 回测基准
- 长期稳定对照组

**禁止：**
- AI 自动覆盖 baseline
- Agent 自动修改 baseline
- 自动调参直接写入 baseline
- Runtime 动态污染 baseline

---

## 六、允许的策略进化方式（正式规则）

### Shadow Strategy Evolution（影子策略实验）

**允许实验区域：**
- `strategy_lab/`
- `experimental/`
- `shadow/`
- `sandbox/`

**实验策略允许：**
- 自动学习
- 自动调参
- 多 Agent 讨论
- 自动 evolution
- 自动评分
- 长周期模拟

**但：** 禁止直接覆盖 baseline。

---

## 七、Baseline 升级规则（正式）

只有满足**所有**以下条件，才允许 baseline 升级：

1. 实验策略连续长期稳定
2. Replay 完整
3. Governance 正常
4. 无 snapshot corruption
5. 无 replay corruption
6. 风险收益长期优于 baseline
7. **人工最终批准**

**升级路径：**
```
baseline_v1 → baseline_v2
```

---

## 八、关于 robot_6~10

robot_6~10：**reserved only**，属于其他项目。

**禁止：**
- 默认纳入股票系统
- 擅自定义职责
- 自动激活

---

## 九、当前系统长期路线

| Phase | 阶段 | 核心 |
|-------|------|------|
| Phase-2 | Governance Stabilization | Replay, Risk Validation, Market Structure, Paper Execution |
| Phase-3 | Multi-Agent Research Team | 多智能体研究团队 |
| Phase-4 | Strategy Lab | Shadow Strategy Evolution |
| Phase-5 | Limited Autonomous Execution | 强治理下的有限自主执行 |

---

## 十、当前核心原则

**允许：**
- "高自由度模拟"
- +
- "强治理审计"

**系统后续可以：**
- 多 Agent
- 自动研究
- 自动执行（模拟盘）
- 自动协作
- 自动实验

**但必须始终：**
- 可 Replay
- 可 Trace
- 可 Rollback
- 可 Audit
- 可 Snapshot
- 可 Governance

---

## 十一、当前最终目标

**不是：** "AI 立刻赚钱"

**而是：** 建立可治理、可审计、可回放、可长期演化的 **AI Research Governance Platform**。

---

## 十二、治理快照标记

```json
{
  "governance_version": "v1.0",
  "governance_date": "2026-05-13",
  "soul_mode": "OBSERVE_ONLY",
  "account_mode": "PAPER_ONLY",
  "baseline_frozen": true,
  "governance_anchors": [
    "PAPER_ONLY",
    "Risk_Validation",
    "Replay_Snapshot",
    "Governance_Snapshot",
    "Baseline_Freeze",
    "Execution_Audit",
    "Runtime_Health_Check",
    "Snapshot_Consistency",
    "Replay_Consistency"
  ],
  "robot_6_10_status": "RESERVED_ONLY",
  "status": "PERMANENT"
}
```
