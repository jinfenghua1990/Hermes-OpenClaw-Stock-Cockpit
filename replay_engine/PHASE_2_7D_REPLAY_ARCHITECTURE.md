# Phase-2.7D Replay Architecture

当前 replay snapshot 已进入治理运行态，不再只是普通执行快照。

---

## 当前主 Snapshot

路径：

```text
replay_engine/snapshots/YYYY-MM-DD.json
```

定位：

```text
Daily Replay Summary Snapshot
```

允许包含：

- snapshot_date
- generated_at
- phase
- soul_mode
- account_mode
- risk_validation_summary
- market_structure_summary
- source_trace_summary
- execution_summary
- phase_2_7d_extension
- version_registry
- strategy_registry_ref
- execution_reconciliation
- baseline_drift_detected
- decisions summary

---

## 禁止继续无限塞入主 Snapshot

以下内容后续不要直接塞进主 snapshot：

- 全量 agent raw reasoning
- 长文本 AI 推理
- 大量 runtime event 明细
- 大量 execution audit 明细
- shadow strategy 全量参数
- 多日历史明细
- 高频行情原始数据

原因：

```text
主 snapshot 必须保持轻量、可读、可 replay。
```

---

## 推荐分层目录

后续如 snapshot 继续膨胀，应拆分为：

```text
replay_engine/snapshots/runtime/YYYY-MM-DD.json
replay_engine/snapshots/governance/YYYY-MM-DD.json
replay_engine/snapshots/execution/YYYY-MM-DD.json
replay_engine/snapshots/agent_trace/YYYY-MM-DD.json
replay_engine/snapshots/strategy/YYYY-MM-DD.json
```

---

## 分层职责

### runtime

保存：

- runtime event summary
- runtime health summary
- active modules

### governance

保存：

- governance_guard
- baseline_drift
- source_trace_summary
- version_registry

### execution

保存：

- execution_summary
- reconciliation result
- missing_source_trace_count

### agent_trace

保存：

- robot_1~5 votes
- conflict result
- arbitration result
- trace graph

### strategy

保存：

- baseline version
- shadow strategy registry snapshot
- strategy experiment references

---

## 当前原则

```text
主 snapshot = summary + references
分层 snapshot = detail
```

---

## 验收规则

主 snapshot 必须始终包含：

- phase = Phase-2.7D
- source_trace_summary
- phase_2_7d_extension
- version_registry
- strategy_registry_ref
- execution_reconciliation
- baseline_drift_detected

但主 snapshot 不应承担所有明细日志存储。
