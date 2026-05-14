# Runtime Freshness Principle

## 核心原则

所有 Runtime 分析必须实时刷新，不允许全天使用盘前静态缓存。

---

## 禁止行为

禁止：

```text
早上生成一次 Top Picks 后全天不更新
结构分析使用过期 K 线
风险价格使用旧 current_price
持仓盈亏使用旧价格
paper decision 使用旧 support / pressure
```

---

## 强制要求

### 1. Position Runtime

必须实时刷新：

- current_price
- pnl
- stop_loss 状态
- take_profit 状态
- position risk

### 2. Structure Runtime

必须实时刷新：

- intraday kline
- support
- pressure
- structure_type
- structure_confidence

如果结构无法识别：

```text
structure = unknown
```

则必须触发：

```text
runtime_data_stale_or_missing = true
```

禁止直接给买入建议。

### 3. Risk Runtime

必须实时刷新：

- current_price
- stop_loss
- entry_zone
- pressure
- data_as_of

如果 data_as_of 不一致：

```text
paper_skip
reason = stale_runtime_data
```

### 4. Top Picks Runtime

盘中必须动态更新：

- 新增强势票
- 移除失效票
- 标记结构异常票
- 标记 stale data

### 5. Paper Runtime

所有 paper decision 必须基于最新 runtime snapshot。

如果数据过期：

```text
paper_skip
reason = stale_runtime_snapshot
```

---

## Runtime Freshness SLA

盘中 Runtime：

```text
每 15 分钟刷新一次
```

任何关键数据超过：

```text
20 分钟
```

未刷新，则标记：

```text
STALE
```

---

## 结论

Runtime 的职责不是“问用户是否刷新”，而是：

```text
主动刷新
主动重算
主动拦截旧数据
主动推送异常
```
