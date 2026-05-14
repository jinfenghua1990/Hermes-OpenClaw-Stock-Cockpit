# Hermes Baseline v1.0（冻结版）

## 状态
- **版本**: v1.0
- **冻结日期**: 2026-03-25
- **状态**: PERMANENTLY FROZEN
- **可修改**: ❌ false

## 四种选股模式

| 模式 | 名称 | 核心逻辑 | 稳定性 |
|------|------|----------|--------|
| MODE 1 | 回踩止跌型 | MA20上升中的缩量回踩 | ⭐⭐⭐⭐⭐ 最稳定 |
| MODE 2 | 突破启动型 | 大阳+MA20加速上行 | ⭐⭐⭐⭐ 爆发力强 |
| MODE 3 | 小阳启动型 | MA20走平转升阶段启动 | ⭐⭐⭐ |
| MODE 4 | 2波启动型 | 前期强势股回调后第二波 | 低频高波动 |

## 共振机制

```
4_modes_triggered → 最强观察仓
3_modes_triggered → 优先候选
2_modes_triggered → 次级观察
1_mode_triggered → 仅观察，不操作
0_mode_triggered → 空仓，不交易
```

## 冻结原则

- ❌ 禁止任何自动学习
- ❌ 禁止自动调参
- ❌ 禁止修改 baseline 参数
- ❌ 禁止第三方策略污染
- ✅ 所有实验性功能 → experimental/
- ✅ 长期稳定运行

## 目录结构

```
Hermes/
├── baseline_v1/          ← 永久冻结区
│   ├── strategies/       ← 四种原版策略
│   ├── configs/          ← 冻结配置
│   └── docs/             ← 冻结文档
├── experimental/         ← AI实验区（可自由探索）
│   ├── ai_scoring/
│   ├── market_filter/
│   ├── sentiment/
│   └── risk_factor/
├── cockpit/              ← 驾驶舱报告
├── reports/              ← 输出报告
├── health_check/         ← 健康检查
└── paper_trading/        ← 模拟交易
```
