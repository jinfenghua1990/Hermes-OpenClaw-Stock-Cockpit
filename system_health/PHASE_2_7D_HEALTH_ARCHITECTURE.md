# Phase-2.7D Health Architecture

当前健康检查分为三层，禁止混用。

---

## 1. daily_health_check.py

定位：

```text
基础系统健康检查
```

覆盖：

- 数据文件存在性
- runtime 基础状态
- replay snapshot 基础持久化
- market structure health
- risk validation health

---

## 2. generate_phase_2_7d_status.py

定位：

```text
Phase-2.7D Governance Runtime Status
```

覆盖：

- governance_guard
- governance_scalability
- source_trace
- baseline_drift
- execution_reconciliation

输出：

```text
system_health/phase_2_7d_status.json
```

供：

- Cockpit
- MAIN
- Replay
- Tail

读取。

---

## 3. phase_2_7d_acceptance_check.py

定位：

```text
Phase-2.7D Acceptance Gate
```

覆盖：

- Replay Snapshot schema
- decision source_trace
- governance guard
- 2.7D status completeness
- cockpit entry

输出：

```text
system_health/phase_2_7d_acceptance_result.json
```

---

## 4. run_phase_2_7d_tail.py

定位：

```text
Daily Pipeline Finalizer
```

每日 pipeline 最后运行：

```bash
python governance/run_phase_2_7d_tail.py
```

执行顺序：

1. governance_guard.py
2. generate_replay_snapshot.py
3. generate_phase_2_7d_status.py
4. phase_2_7d_acceptance_check.py

---

## 禁止事项

禁止把所有检查都塞回 daily_health_check.py。

原因：

```text
daily_health_check = 基础健康
phase_2_7d_status = 治理运行态
acceptance_check = 验收门
```

三者职责不同。

---

## 当前原则

```text
基础健康 != 治理状态 != 验收门
```

后续新增治理检查，优先进入：

```text
system_health/generate_phase_2_7d_status.py
```

后续新增验收标准，优先进入：

```text
system_health/phase_2_7d_acceptance_check.py
```
