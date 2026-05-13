# 今日市场核心摘要
日期：{{date}}

## 1. 北向资金
{{northbound}}

## 2. 主线板块
{{main_sector}}

## 3. 机构净买
{{institution}}

## 4. 情绪周期
{{emotion}}

## 5. 明日观察方向
{{tomorrow_focus}}

## 6. 四模式扫描统计
{{strategy_summary}}

### 6.1 各模式数量
- **回踩止跌型**：{{mode_1_count}} 只
- **突破启动型**：{{mode_2_count}} 只  
- **小阳启动型**：{{mode_3_count}} 只
- **2波启动型**：{{mode_4_count}} 只

### 6.2 候选总数
今日共有 **{{any_mode_count}}** 只股票符合至少一种模式（总股票数：{{total_symbols}}）。

### 6.3 热门模式
当前最活跃模式：**{{hot_mode}}**

### 6.4 风险提示
{{risk_note}}

## 7. 市场情绪快照
{{emotion_snapshot}}

### 7.1 情绪分数
**{{emotion_score}}/100** - {{emotion_interpretation}}

### 7.2 市场阶段
**{{market_phase}}** - {{phase_interpretation}}

### 7.3 风险等级
**{{market_risk_level}}** - {{risk_interpretation}}

### 7.4 模式强度
- 最强模式：**{{strongest_mode}}**
- 最弱模式：**{{weakest_mode}}**

### 7.5 快照说明
{{snapshot_explanation}}

## 8. 情绪历史趋势
{{emotion_history_trend}}

### 8.1 最近5日情绪分数
{{recent_scores_chart}}

### 8.2 当前趋势
**{{trend_direction}}** - {{trend_explanation}}

### 8.3 历史统计
{{history_statistics}}

### 8.4 趋势解读
{{trend_interpretation}}

---

## 11. Paper Trading Summary

- **模式**: {{paper_trading_mode}} ({{paper_trading_kill_switch}})
- **持仓数量**: {{paper_trading_position_count}}
- **总持仓市值**: ¥{{paper_trading_total_value}}
- **浮动盈亏**: ¥{{paper_trading_floating_pnl}} ({{paper_trading_floating_ratio}})

### 11.1 交易统计

- **买入**: {{paper_trading_buy_trades}} 笔
- **卖出**: {{paper_trading_sell_trades}} 笔
- **实现盈亏**: ¥{{paper_trading_realized_pnl}}

### 11.2 持仓详情

{{paper_trading_positions_detail}}

### 11.3 风险状态

- **状态**: {{paper_trading_risk_status}}
- **最大仓位占比**: {{paper_trading_largest_ratio}}

---

## 12. Runtime Event Health

- **活跃模块**: {{rehealth_active_today}}/{{rehealth_total_modules}}
- **缺失模块**: {{rehealth_missing_today}}
- **Warning 模块**: {{rehealth_warning_modules}}
- **Error 模块**: {{rehealth_error_modules}}
- **总体状态**: {{rehealth_status}}

## 13. Runtime Event Summary

- **总模块数**: {{runtime_total_modules}}
- **活跃模块数**: {{runtime_active_modules}}
- **Execution Layer**: {{runtime_exec_active}}/7 active
- **Governance Layer**: {{runtime_gov_active}}/7 active
- **Cockpit Layer**: {{runtime_cockpit_active}}/3 active

### 最近事件
{{runtime_latest_events_text}}

---

*数据来源：技术因子缓存 + 原版四模式扫描器 + 市场情绪快照系统 + 情绪历史分析器*  
*生成时间：{{timestamp}}*