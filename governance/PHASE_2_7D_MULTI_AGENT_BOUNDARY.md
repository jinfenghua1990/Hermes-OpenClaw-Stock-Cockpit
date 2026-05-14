# Phase-2.7D Multi-Agent Boundary

## 目标

Phase-2.7D 允许多 Agent 参与模拟盘研究与治理观察，但必须保留治理边界。

---

## 当前可用 Agent

当前股票系统仅允许使用：

```text
robot_1 ~ robot_5
```

---

## robot_1~5 建议职责

### robot_1

```text
baseline_pattern_engine
```

负责：

- 四种选股模式 baseline 识别
- 模式标签
- baseline 对照

### robot_2

```text
market_structure_review
```

负责：

- swing low / swing high
- support / pressure
- structure_type
- structure_confidence

### robot_3

```text
sentiment_theme_review
```

负责：

- 市场情绪
- 题材方向
- 板块热度观察

### robot_4

```text
risk_validation_review
```

负责：

- risk price validation
- stop_loss / pressure / support 合理性
- invalid_price_structure 检测

### robot_5

```text
execution_replay_audit
```

负责：

- paper execution audit
- replay consistency
- source trace completeness
- governance guard review

---

## robot_6~10

状态：

```text
RESERVED_ONLY
```

禁止：

- 默认纳入股票系统
- 擅自定义职责
- 自动激活
- 进入 daily pipeline
- 进入 source trace
- 进入 execution decision

原因：

```text
robot_6~10 属于其他项目预留资源，不属于当前股票系统。
```

---

## 多 Agent 允许事项

允许：

- 多观点
- 多复核
- 冲突输出
- agent vote
- arbitration
- source trace
- replay audit
- paper-only execution suggestion

---

## 多 Agent 禁止事项

禁止：

- 绕过 Risk Validation
- 绕过 Governance Guard
- 绕过 PAPER_ONLY
- 自动覆盖 baseline
- 自动启用 robot_6~10
- 自动调参写入 baseline
- 直接实盘执行

---

## 冲突裁决

所有 Agent 冲突必须进入：

```text
governance/arbitration/agent_arbitrator.py
```

输出：

- final_decision
- decision_source
- agent_votes
- conflict_detected
- conflict_level
- arbitration_reason

---

## Source Trace 要求

所有 Agent 输出必须包含：

- source_agent
- source_module
- data_source
- data_as_of
- trace_id

否则：

```text
source_trace_health = WARNING / CRITICAL
```

---

## 当前原则

```text
多 Agent 可以放开观察，治理底线不能放开。
```

```text
robot_1~5 = 当前股票系统 Agent
robot_6~10 = RESERVED_ONLY
```
