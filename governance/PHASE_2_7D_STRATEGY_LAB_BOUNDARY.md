# Phase-2.7D Strategy Lab Boundary

## 目标

允许策略实验与 Shadow Strategy 演化，但禁止污染四种选股模式原版 baseline。

---

## Baseline 定位

当前 baseline：

```text
四种选股模式（原版 baseline_v1）
```

定位：

```text
Governance Anchor
```

用途：

- replay 对照
- governance 对照
- 风险比较
- 回测基准
- 长期稳定对照组

---

## 绝对禁止

禁止：

- 自动覆盖 baseline
- 自动调参直接写入 baseline
- Agent runtime 动态修改 baseline
- Shadow Strategy 参数进入 baseline runtime
- 实验策略直接替换生产策略

---

## 允许事项

允许：

- shadow strategy
- sandbox strategy
- experimental strategy
- 多 Agent 讨论策略实验
- 自动生成实验结论
- 自动记录实验表现
- 长周期模拟观察

---

## 推荐目录

后续策略实验统一进入：

```text
strategy_lab/
  experimental/
  shadow/
  sandbox/
  reports/
```

禁止直接写入：

```text
strategy_library/baseline/
```

除非人工批准 baseline 升级。

---

## Strategy Registry

所有 shadow strategy 必须注册到：

```text
governance/registry/strategy_registry.json
```

每个实验策略必须包含：

- strategy_id
- strategy_name
- created_at
- source_agent
- mode
- status
- baseline_mutation_allowed = false

---

## Baseline 升级条件

只有满足以下条件，才允许从实验策略升级为新 baseline：

1. 长周期模拟稳定
2. Replay 完整
3. Governance 正常
4. Source Trace 完整
5. 无 baseline drift
6. 风险收益长期优于 baseline_v1
7. 人工最终批准

升级路径：

```text
baseline_v1 -> baseline_v2
```

但必须保留：

```text
baseline_v1
```

用于历史 replay 对照。

---

## Baseline Drift Monitor

检测脚本：

```text
governance/baseline_drift_monitor.py
```

如果检测到：

```text
baseline_drift_detected = true
```

则：

```text
status = CRITICAL
```

并必须冻结：

- auto execution
- shadow promotion
- strategy mutation

---

## 当前原则

```text
允许策略实验性进化
禁止主 baseline 被自动污染
```

```text
Shadow Strategy = 可实验
Baseline = 可对照、可回放、可回退
```
