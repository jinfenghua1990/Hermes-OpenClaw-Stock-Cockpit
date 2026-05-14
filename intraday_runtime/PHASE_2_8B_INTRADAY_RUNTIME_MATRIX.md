# Phase-2.8B Intraday Runtime Matrix

## 当前目标

构建：

```text
15分钟级 AI Intraday Runtime
```

覆盖：

- Position Runtime
- Market Runtime
- Governance Runtime
- Replay Runtime
- Execution Runtime
- Source Trace Runtime
- AI Arbitration Runtime

仅允许：

```text
PAPER_ONLY
OBSERVE_ONLY
```

---

# Runtime Frequency

## 固定频率

```text
09:30
09:45
10:00
10:15
10:30
10:45
11:00
11:15
13:00
13:15
13:30
13:45
14:00
14:15
14:30
14:45
```

统一：

```text
15分钟 Runtime
```

---

# Runtime Report Matrix

## 1. Position Runtime

### 输出

- 持仓列表
- 仓位占比
- 成本价
- 浮盈浮亏
- 止损状态
- 止盈状态
- 仓位集中度
- position_risk_level

### 风险事件

- stop_loss_triggered
- take_profit_watch
- abnormal_drawdown
- concentration_warning

---

## 2. Intraday Structure Runtime

### 输出

- structure_type
- structure_confidence
- support
- pressure
- intraday_structure_risk

### 结构变化事件

- breakout -> invalid
- pullback -> breakout
- trend_extension -> consolidation

---

## 3. Market Emotion Runtime

### 输出

- emotion_level
- market_risk_level
- sector_rotation
- hot_theme
- cold_theme

### 情绪事件

- emotion_strengthening
- emotion_weakening
- panic_risk
- sector_collapse

---

## 4. Sector Runtime

### 输出

- sector_strength_rank
- capital_flow
- sector_heat
- sector_breakdown

### 板块事件

- hot_sector_switch
- capital_outflow
- rotation_detected

---

## 5. Top Picks Runtime

### 输出

- top_pick_added
- top_pick_removed
- top_pick_invalidated
- ranking_changed

---

## 6. Execution Runtime

### 输出

- paper_buy
- paper_sell
- paper_skip
- manual_pending
- execution_status

### 执行事件

- execution_blocked
- risk_rejected
- governance_rejected

---

## 7. Governance Runtime

### 输出

- governance_status
- governance_bypass_detected
- baseline_frozen
- replay_runtime_status
- acceptance_status

### Governance 事件

- replay_fail
- acceptance_warning
- source_trace_warning
- baseline_drift_detected

---

## 8. Source Trace Runtime

### 输出

- source_agent
- source_module
- data_source
- data_as_of
- trace_id

### Trace 事件

- trace_missing
- source_conflict
- stale_data_detected

---

## 9. Replay Runtime

### 输出

- intraday_snapshot_uuid
- replay_status
- replay_consistency

### Snapshot Frequency

每15分钟：

```text
09:45 snapshot
10:30 snapshot
13:15 snapshot
14:45 snapshot
```

---

## 10. AI Arbitration Runtime

### 输出

- agent_votes
- conflict_detected
- arbitration_result
- final_decision

### Agent 冲突事件

- bullish_vs_risk_conflict
- execution_conflict
- governance_override

---

# Runtime Push Layer

## 飞书仅负责：

- 风险提醒
- 结构变化
- 持仓警报
- Runtime异常
- Governance异常

## 深度 Runtime 内容：

统一进入：

```text
runtime_reports/
```

---

# Runtime Priority

```text
Position Runtime
>
Risk Runtime
>
Governance Runtime
>
Top Picks Runtime
```

---

# 当前原则

```text
盘中 Runtime 以持仓为核心
不是以候选票为核心
```

```text
飞书负责提醒
Runtime Reports负责深度分析
Cockpit负责实时总控
```
