#!/usr/bin/env python3
"""
Position Manager - 仓位管理器
负责维护模拟交易仓位，支持买入/卖出/持仓查询
"""

import json
import sys
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

# 项目根目录
BASE_DIR = Path(__file__).resolve().parent.parent
POSITIONS_FILE = BASE_DIR / "portfolio" / "unified_positions.json"

# 运行时事件记录
def _log_event(module: str, layer: str, status: str, message: str, runtime_ms: Optional[int] = None):
    """写入 runtime event"""
    try:
        sys.path.insert(0, str(BASE_DIR / "runtime_events"))
        from runtime_event_logger import log_event as _le
        _le(module=module, layer=layer, status=status, message=message, runtime_ms=runtime_ms)
    except Exception:
        pass


class PositionManager:
    """
    模拟仓位管理器
    
    功能:
    - 记录持仓股票
    - 买入/卖出操作（模拟）
    - 持仓查询
    - 仓位快照保存
    """
    
    def __init__(self, positions_file: Optional[Path] = None, kill_switch: bool = False):
        """
        Args:
            positions_file: 持仓文件路径，默认使用 unified_positions.json
            kill_switch: 是否为观察模式，默认 False (观察模式)
        """
        self.positions_file = positions_file or POSITIONS_FILE
        self.kill_switch = kill_switch  # False = 观察模式（只记录，不执行真实交易）
        self.positions = self._load_positions()
    
    def _load_positions(self) -> dict:
        """从文件加载持仓数据"""
        if self.positions_file.exists():
            try:
                with open(self.positions_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass
        return self._default_positions()
    
    def _default_positions(self) -> dict:
        """返回默认空持仓结构"""
        return {
            "last_updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "mode": "OBSERVE_ONLY" if self.kill_switch else "PAPER_TRADING",
            "positions": [],
            "cash_balance": 0.0,
            "total_value": 0.0,
        }
    
    def _save_positions(self) -> None:
        """保存持仓到文件"""
        self.positions["last_updated"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        self.positions_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.positions_file, "w", encoding="utf-8") as f:
            json.dump(self.positions, f, ensure_ascii=False, indent=2)
    
    def get_positions(self) -> list:
        """获取当前所有持仓"""
        return self.positions.get("positions", [])
    
    def get_position(self, symbol: str) -> Optional[dict]:
        """根据股票代码获取持仓"""
        for pos in self.get_positions():
            if pos.get("symbol") == symbol:
                return pos
        return None
    
    def add_position(self, symbol: str, name: str, quantity: int, avg_price: float,
                     entry_date: Optional[str] = None) -> dict:
        """
        添加新持仓（模拟买入）
        
        Args:
            symbol: 股票代码
            name: 股票名称
            quantity: 买入数量
            avg_price: 买入均价
            entry_date: 买入日期
        
        Returns:
            新增的持仓记录
        """
        start = datetime.now(timezone.utc)
        
        if self.get_position(symbol):
            # 已存在持仓，执行加仓
            return self._add_to_position(symbol, quantity, avg_price)
        
        entry_date = entry_date or datetime.now().strftime("%Y-%m-%d")
        
        new_pos = {
            "symbol": symbol,
            "name": name,
            "quantity": quantity,
            "avg_price": avg_price,
            "entry_date": entry_date,
            "entry_reason": "",
            "mode": "paper_trade",
            "paper_trade": True,
        }
        
        self.positions.setdefault("positions", []).append(new_pos)
        self._save_positions()
        
        runtime_ms = int((datetime.now(timezone.utc) - start).total_seconds() * 1000)
        _log_event("position_manager", "execution_layer", "success",
                   f"paper_trade add: {symbol} x{quantity} @ {avg_price}", runtime_ms)
        
        return new_pos
    
    def _add_to_position(self, symbol: str, quantity: int, avg_price: float) -> dict:
        """加仓到已有持仓"""
        pos = self.get_position(symbol)
        if not pos:
            raise ValueError(f"Position {symbol} not found")
        
        old_qty = pos["quantity"]
        old_avg = pos["avg_price"]
        new_qty = old_qty + quantity
        new_avg = (old_qty * old_avg + quantity * avg_price) / new_qty
        
        pos["quantity"] = new_qty
        pos["avg_price"] = round(new_avg, 2)
        
        self._save_positions()
        
        _log_event("position_manager", "execution_layer", "success",
                   f"paper_trade add: {symbol} +{quantity} => {new_qty} @ avg {new_avg}")
        
        return pos
    
    def reduce_position(self, symbol: str, quantity: int, sell_price: float) -> dict:
        """
        减仓（模拟卖出部分）
        
        Args:
            symbol: 股票代码
            quantity: 卖出数量
            sell_price: 卖出价格
        
        Returns:
            更新后的持仓记录
        """
        pos = self.get_position(symbol)
        if not pos:
            raise ValueError(f"No position found for {symbol}")
        
        if quantity >= pos["quantity"]:
            return self.close_position(symbol, sell_price)
        
        pos["quantity"] -= quantity
        self._save_positions()
        
        _log_event("position_manager", "execution_layer", "success",
                   f"paper_trade reduce: {symbol} -{quantity} @ {sell_price}")
        
        return pos
    
    def close_position(self, symbol: str, sell_price: float) -> Optional[dict]:
        """
        平仓（全部卖出）
        
        Args:
            symbol: 股票代码
            sell_price: 卖出价格
        
        Returns:
            被移除的持仓记录（平仓前）
        """
        pos = self.get_position(symbol)
        if not pos:
            return None
        
        self.positions["positions"] = [p for p in self.get_positions() if p.get("symbol") != symbol]
        self._save_positions()
        
        _log_event("position_manager", "execution_layer", "success",
                   f"paper_trade close: {symbol} @ {sell_price}")
        
        return pos
    
    def update_price(self, symbol: str, current_price: float) -> None:
        """
        更新持仓的当前价格（快照用）
        
        Args:
            symbol: 股票代码
            current_price: 当前价格
        """
        pos = self.get_position(symbol)
        if pos:
            pos["current_price"] = current_price
            pos["last_price_update"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            self._save_positions()
    
    def get_summary(self) -> dict:
        """获取持仓汇总"""
        positions = self.get_positions()
        total_value = sum(p.get("quantity", 0) * p.get("current_price", p.get("avg_price", 0))
                          for p in positions)
        return {
            "mode": self.positions.get("mode", "PAPER_TRADING"),
            "kill_switch": self.kill_switch,
            "total_positions": len(positions),
            "total_value": round(total_value, 2),
            "last_updated": self.positions.get("last_updated"),
        }
    
    def export_snapshot(self) -> dict:
        """导出自包含快照（用于日报）"""
        return {
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "mode": self.positions.get("mode", "PAPER_TRADING"),
            "kill_switch": self.kill_switch,
            "positions": self.get_positions(),
            "summary": self.get_summary(),
        }


if __name__ == "__main__":
    pm = PositionManager()
    print(json.dumps(pm.get_summary(), ensure_ascii=False, indent=2))
