# Baseline Freeze 架构说明

## 核心原则
- `baseline_v1/` = 永久冻结，任何人不得修改
- `experimental/` = AI实验区，可以自由探索，但禁止污染 baseline
- Runtime 只读取 `baseline_v1/strategies/` 下的策略

## 目录结构
```
Hermes/
├── baseline_v1/          ← 永久冻结（只读）
│   ├── SOUL.md           ← 冻结声明
│   ├── strategies/       ← 四种原版策略（MODE 1-4）
│   ├── configs/          ← 冻结配置
│   └── docs/             ← 冻结文档
├── experimental/         ← AI实验区（可自由修改）
│   ├── ai_scoring/
│   ├── market_filter/
│   ├── sentiment/
│   └── risk_factor/
├── cockpit/              ← 驾驶舱报告
├── reports/              ← 输出报告
├── health_check/         ← 健康检查
└── paper_trading/        ← 模拟交易
```

## 四种原版策略参数（v1.0 冻结）

| 模式 | 核心条件数 | 评分门槛 | 特点 |
|------|-----------|---------|------|
| MODE 1 回踩止跌 | 6个必须 | score≥4 | 缩量回踩，最稳定 |
| MODE 2 突破启动 | 4个必须 | score≥3 | 大阳突破，爆发力 |
| MODE 3 小阳启动 | 4个必须 | score≥3 | MA20走平转升 |
| MODE 4 2波启动 | 5个必须 | 特殊标记 | 前期强势股回调后第二波 |

## 共振级别（冻结）
- 4模式 → 最强观察仓
- 3模式 → 优先候选
- 2模式 → 次级观察
- 1模式 → 仅观察，不操作
- 0模式 → 空仓，不交易

## 禁止事项（强制执行）
- ❌ 禁止修改 baseline_v1/ 下的任何文件
- ❌ 禁止自动学习
- ❌ 禁止自动调参
- ❌ 禁止第三方策略污染 baseline
- ✅ AI实验只能在 experimental/ 下进行
