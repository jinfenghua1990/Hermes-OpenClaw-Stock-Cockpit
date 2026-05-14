# Phase-2.7D Runbook — Governance Scalability + Source Trace

## 目标

Phase-2.7D 用于收口：

- Source Trace Governance
- Replay 2.7D Snapshot
- Governance Scalability
- Baseline Drift Monitor
- Execution Reconciliation
- Cockpit 2.7D Runtime

---

## 当前硬锁

必须保持：

```text
SOUL_MODE = OBSERVE_ONLY
account_mode = PAPER_ONLY
Baseline Frozen = true
robot_6~10 = RESERVED_ONLY
```

禁止：

- 实盘
- 真实资金
- 自动覆盖 baseline
- 删除 replay
- 关闭 governance
- 启用 robot_6~10

---

## MAIN 每日收口命令

在每日 pipeline 完成后执行：

```bash
cd /Users/gino/project_ai_trading
python governance/run_phase_2_7d_tail.py
```

该命令会自动执行：

1. `replay_engine/generate_replay_snapshot.py`
2. `system_health/generate_phase_2_7d_status.py`

并输出：

```text
system_health/phase_2_7d_tail_result.json
system_health/phase_2_7d_status.json
replay_engine/snapshots/YYYY-MM-DD.json
```

---

## 本地验收命令

```bash
cd /Users/gino/project_ai_trading
python governance/run_phase_2_7d_tail.py
cd frontend
npm run build
```

---

## 验收标准

### 1. Replay Snapshot

`replay_engine/snapshots/YYYY-MM-DD.json` 必须包含：

- phase = Phase-2.7D
- source_trace_summary
- phase_2_7d_extension
- version_registry
- strategy_registry_ref
- execution_reconciliation
- baseline_drift_detected

### 2. Source Trace

每条 decision 必须包含：

- source_agent
- source_module
- data_source
- data_as_of
- trace_id
- source_trace

### 3. Health Status

`system_health/phase_2_7d_status.json` 必须包含：

- governance_scalability
- source_trace
- baseline_drift
- execution_reconciliation

### 4. Cockpit

`frontend/main.jsx` 必须入口到：

```jsx
App2_7D
```

---

## 异常处理

### Source Trace WARNING

说明部分数据缺少：

- source_agent
- data_source
- trace_id

需要检查对应模块是否写入 source_trace。

### Source Trace CRITICAL

说明缺少：

- data_as_of

必须修复后再进入执行链路。

### Baseline Drift CRITICAL

说明 shadow / sandbox / experimental 参数进入主 baseline runtime。

立即冻结：

- auto execution
- shadow promotion
- strategy mutation

### Execution Reconciliation WARNING/FAIL

说明：

- replay execution
- paper_execution_log
- auto_execution_audit

存在不一致。

必须先对账，再继续模拟盘观察。

---

## 当前原则

高自由度模拟可以放开，但治理底线不能放开：

- PAPER_ONLY
- Risk Validation
- Replay
- Source Trace
- Governance Snapshot
- Baseline Freeze
- Execution Audit
