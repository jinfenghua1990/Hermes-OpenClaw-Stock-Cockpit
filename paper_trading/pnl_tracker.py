#!/usr/bin/env python3
"""
PnL Tracker - 盈亏追踪器
负责追踪模拟交易的持仓盈亏、历史交易记录、收益率计算
"""

import json
import sys
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, List

BASE_DIR = Path(__file__).resolve().parent.parent
REPORTS_DIR = BASE_DIR / "paper_trading" / "reports"

def _log_event(module: str, layer: str, status: str, message: str, runtime_ms: Optional[int] = None):
    try:
        sys.path.insert(0, str(BASE_DIR / "runtime_events"))
        from runtime_event_logger import log_event as _le
        _le(module=module, layer=layer, status=status, message=message, runtime_ms=runtime_ms)
    except Exception:
        pass


class PnLTracker:
    """
    模拟交易盈亏追踪器
    
    功能:
    - 按市值法计算浮动盈亏
    - 记录历史交易（含手续费模拟）
    - 计算日收益率
    - 生成 PnL 报告 JSON
    """
    
    DEFAULT_CONFIG = {
        "commission_rate": 0.0003,    # 印花税+佣金 约万3
        "stamp_tax": 0.001,           # 印花税 千1（卖出时）
        "kill_switch": False,         # 观察模式
    }
    
    def __init__(self, reports_dir: Optional[Path] = None, **overrides):
        """
        Args:
            reports_dir: 报告输出目录
            **overrides: 配置覆盖
        """
        self.reports_dir = reports_dir or REPORTS_DIR
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        
        self.config = self.DEFAULT_CONFIG.copy()
        self.config.update(overrides)
        self.kill_switch = self.config.get("kill_switch", False)
        
        # 内存中的当日交易记录
        self._today_trades: List[dict] = []
        self._trade_id_counter = 0
        
        # 加载历史报告
        self._load_today_report()
    
    def _load_today_report(self) -> None:
        """加载今日 PnL 报告（如存在）"""
        today = datetime.now().strftime("%Y-%m-%d")
        self._report_file = self.reports_dir / f"pnl_report_{today}.json"
        
        if self._report_file.exists():
            try:
                with open(self._report_file, "r", encoding="utf-8") as f:
                    self._today_report = json.load(f)
                # 恢复 trade_id 计数器
                trades = self._today_report.get("trades", [])
                if trades:
                    max_id = max(int(t.get("trade_id", "0").split("-")[-1] or 0) for t in trades)
                    self._trade_id_counter = max_id + 1
            except Exception:
                self._today_report = self._new_empty_report()
        else:
            self._today_report = self._new_empty_report()
    
    def _new_empty_report(self) -> dict:
        today = datetime.now().strftime("%Y-%m-%d")
        return {
            "date": today,
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "kill_switch": self.kill_switch,
            "trades": [],
            "positions_snapshot": [],
            "summary": {
                "total_pnl": 0.0,
                "total_pnl_ratio": 0.0,
                "day_return": 0.0,
                "win_count": 0,
                "loss_count": 0,
                "total_trades": 0,
                "sell_trades": 0,
                "buy_trades": 0,
            }
        }
    
    def record_buy(self, symbol: str, name: str, quantity: int, price: float) -> dict:
        """
        记录一笔买入交易
        
        Args:
            symbol: 股票代码
            name: 股票名称
            quantity: 买入数量
            price: 买入价格
        
        Returns:
            交易记录
        """
        start = datetime.now(timezone.utc)
        
        commission = quantity * price * (self.config["commission_rate"])
        total_cost = quantity * price + commission
        
        trade = {
            "trade_id": f"PT-{datetime.now().strftime('%Y%m%d')}-{self._trade_id_counter:04d}",
            "timestamp": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "symbol": symbol,
            "name": name,
            "direction": "BUY",
            "quantity": quantity,
            "price": price,
            "commission": round(commission, 2),
            "total_amount": round(total_cost, 2),
            "kill_switch": self.kill_switch,
        }
        
        self._trade_id_counter += 1
        self._today_trades.append(trade)
        self._today_report["trades"].append(trade)
        self._update_summary()
        self._save_report()
        
        runtime_ms = int((datetime.now(timezone.utc) - start).total_seconds() * 1000)
        action = "recorded (observe)" if self.kill_switch else "executed"
        _log_event("pnl_tracker", "execution_layer", "success",
                   f"{action} BUY: {symbol} x{quantity} @ {price}", runtime_ms)
        
        return trade
    
    def record_sell(self, symbol: str, name: str, quantity: int, price: float) -> dict:
        """
        记录一笔卖出交易（含印花税）
        
        Args:
            symbol: 股票代码
            name: 股票名称
            quantity: 卖出数量
            price: 卖出价格
        
        Returns:
            交易记录（含盈亏计算）
        """
        start = datetime.now(timezone.utc)
        
        # 查找对应买入记录计算盈亏
        buy_amount = 0
        buy_commission = 0
        matched_buys = [t for t in self._today_report["trades"]
                       if t.get("symbol") == symbol and t.get("direction") == "BUY"]
        
        remaining_qty = quantity
        for buy_trade in matched_buys:
            if remaining_qty <= 0:
                break
            qty_to_match = min(remaining_qty, buy_trade["quantity"])
            buy_amount += qty_to_match * buy_trade["price"]
            buy_commission += buy_trade["commission"] * (qty_to_match / buy_trade["quantity"])
            remaining_qty -= qty_to_match
        
        sell_amount = quantity * price
        commission = sell_amount * (self.config["commission_rate"])
        stamp_tax = sell_amount * (self.config["stamp_tax"])
        total_proceed = sell_amount - commission - stamp_tax
        
        pnl = total_proceed - buy_amount - buy_commission
        pnl_ratio = pnl / buy_amount if buy_amount > 0 else 0
        
        trade = {
            "trade_id": f"PT-{datetime.now().strftime('%Y%m%d')}-{self._trade_id_counter:04d}",
            "timestamp": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "symbol": symbol,
            "name": name,
            "direction": "SELL",
            "quantity": quantity,
            "price": price,
            "commission": round(commission, 2),
            "stamp_tax": round(stamp_tax, 2),
            "total_amount": round(sell_amount, 2),
            "net_proceed": round(total_proceed, 2),
            "cost_basis": round(buy_amount, 2),
            "pnl": round(pnl, 2),
            "pnl_ratio": round(pnl_ratio, 4),
            "kill_switch": self.kill_switch,
        }
        
        self._trade_id_counter += 1
        self._today_trades.append(trade)
        self._today_report["trades"].append(trade)
        self._update_summary()
        self._save_report()
        
        runtime_ms = int((datetime.now(timezone.utc) - start).total_seconds() * 1000)
        action = "recorded (observe)" if self.kill_switch else "executed"
        _log_event("pnl_tracker", "execution_layer", "success",
                   f"{action} SELL: {symbol} x{quantity} @ {price}, PnL={pnl:.2f}", runtime_ms)
        
        return trade
    
    def update_positions_snapshot(self, positions: List[dict]) -> None:
        """更新持仓快照（用于日报）"""
        self._today_report["positions_snapshot"] = positions
        self._save_report()
    
    def calculate_floating_pnl(self, positions: List[dict]) -> dict:
        """
        计算浮动盈亏
        
        Args:
            positions: 持仓列表，每项需含 symbol/quantity/avg_price/current_price
        
        Returns:
            {"total_floating_pnl": float, "positions": list}
        """
        total_cost = 0
        total_market_value = 0
        position_details = []
        
        for pos in positions:
            qty = pos.get("quantity", 0)
            avg_price = pos.get("avg_price", 0)
            current_price = pos.get("current_price", avg_price)
            
            cost = qty * avg_price
            market_value = qty * current_price
            floating_pnl = market_value - cost
            floating_ratio = floating_pnl / cost if cost > 0 else 0
            
            total_cost += cost
            total_market_value += market_value
            
            position_details.append({
                "symbol": pos.get("symbol", ""),
                "name": pos.get("name", ""),
                "quantity": qty,
                "avg_price": avg_price,
                "current_price": current_price,
                "cost": round(cost, 2),
                "market_value": round(market_value, 2),
                "floating_pnl": round(floating_pnl, 2),
                "floating_ratio": round(floating_ratio, 4),
            })
        
        total_floating_pnl = total_market_value - total_cost
        total_ratio = total_floating_pnl / total_cost if total_cost > 0 else 0
        
        return {
            "total_cost": round(total_cost, 2),
            "total_market_value": round(total_market_value, 2),
            "total_floating_pnl": round(total_floating_pnl, 2),
            "total_floating_ratio": round(total_ratio, 4),
            "positions": position_details,
        }
    
    def _update_summary(self) -> None:
        """更新当日汇总"""
        trades = self._today_report.get("trades", [])
        sells = [t for t in trades if t.get("direction") == "SELL"]
        buys = [t for t in trades if t.get("direction") == "BUY"]
        
        total_pnl = sum(t.get("pnl", 0) for t in sells)
        win_count = sum(1 for t in sells if t.get("pnl", 0) > 0)
        loss_count = sum(1 for t in sells if t.get("pnl", 0) < 0)
        
        self._today_report["summary"] = {
            "total_pnl": round(total_pnl, 2),
            "total_pnl_ratio": 0.0,
            "day_return": 0.0,
            "win_count": win_count,
            "loss_count": loss_count,
            "total_trades": len(trades),
            "sell_trades": len(sells),
            "buy_trades": len(buys),
        }
        self._today_report["generated_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    
    def _save_report(self) -> None:
        """保存当日报告"""
        with open(self._report_file, "w", encoding="utf-8") as f:
            json.dump(self._today_report, f, ensure_ascii=False, indent=2)
    
    def get_today_report(self) -> dict:
        """获取当日 PnL 报告"""
        return self._today_report.copy()
    
    def export_daily_summary(self) -> dict:
        """导出日报用摘要"""
        return {
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "date": datetime.now().strftime("%Y-%m-%d"),
            "kill_switch": self.kill_switch,
            "report_file": str(self._report_file),
            "summary": self._today_report.get("summary", {}),
            "total_trades": len(self._today_report.get("trades", [])),
        }


if __name__ == "__main__":
    tracker = PnLTracker()
    print(json.dumps(tracker.get_today_report(), ensure_ascii=False, indent=2))
