#!/usr/bin/env python3
"""
Risk Controller - 风险控制器
用于模拟交易的仓位风险检查，支持：
- 单股仓位上限
- 总仓位上限
- 亏损阈值保护
- 观察模式（KILL_SWITCH）下记录但不阻止
"""

import json
import sys
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, List

BASE_DIR = Path(__file__).resolve().parent.parent

def _log_event(module: str, layer: str, status: str, message: str, runtime_ms: Optional[int] = None):
    try:
        sys.path.insert(0, str(BASE_DIR / "runtime_events"))
        from runtime_event_logger import log_event as _le
        _le(module=module, layer=layer, status=status, message=message, runtime_ms=runtime_ms)
    except Exception:
        pass


class RiskController:
    """
    模拟交易风险控制器
    
    规则:
    - 单股最大仓位占比（默认 25%）
    - 总仓位最大价值（默认 100万）
    - 单股亏损阈值（默认 -15% 止损）
    - 观察模式（KILL_SWITCH=false）: 记录警告但允许执行
    """
    
    DEFAULT_CONFIG = {
        "max_position_ratio": 0.25,       # 单股最大占总资产比例
        "max_total_value": 1_000_000.0,    # 最大总仓位价值
        "stop_loss_threshold": -0.15,      # 止损阈值 -15%
        "max_positions": 20,              # 最大持仓股票数
        "kill_switch": False,              # False = 观察模式
    }
    
    def __init__(self, config_path: Optional[Path] = None, **overrides):
        """
        Args:
            config_path: 风险配置文件路径
            **overrides: 配置覆盖（如 kill_switch=True）
        """
        self.config = self.DEFAULT_CONFIG.copy()
        if config_path and config_path.exists():
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    self.config.update(json.load(f))
            except Exception:
                pass
        self.config.update(overrides)  # 命令行参数优先级最高
        
        self.kill_switch = self.config.get("kill_switch", False)
        self._warnings: List[str] = []
    
    def check_buy(self, symbol: str, quantity: int, price: float,
                  current_positions: List[dict], total_cash: float) -> dict:
        """
        检查买入信号是否通过风险控制
        
        Args:
            symbol: 股票代码
            quantity: 买入数量
            price: 买入价格
            current_positions: 当前持仓列表
            total_cash: 账户现金余额
        
        Returns:
            {
                "approved": bool,
                "reason": str,
                "warnings": list,
                "action": "executed" | "recorded" | "blocked"
            }
        """
        self._warnings = []
        start = datetime.now(timezone.utc)
        
        trade_value = quantity * price
        current_total = sum(p.get("quantity", 0) * p.get("current_price", p.get("avg_price", 0))
                           for p in current_positions)
        proposed_total = current_total + trade_value
        total_assets = current_total + total_cash
        
        # 计算当前持仓中该股的数量
        existing_pos = next((p for p in current_positions if p.get("symbol") == symbol), None)
        existing_qty = existing_pos.get("quantity", 0) if existing_pos else 0
        existing_value = existing_qty * price
        
        # 1. 检查总仓位上限
        if proposed_total > self.config["max_total_value"]:
            warning = f"[WARN] 总仓位 {proposed_total:.2f} 超过上限 {self.config['max_total_value']}"
            self._warnings.append(warning)
            if self.kill_switch:
                _log_event("risk_controller", "governance_layer", "warning",
                           f"buy blocked: {symbol} - total limit exceeded")
                return self._build_result(False, warning, "blocked")
            else:
                _log_event("risk_controller", "governance_layer", "warning",
                           f"buy recorded (observe): {symbol} - total limit exceeded")
        
        # 2. 检查单股仓位上限
        if total_assets > 0:
            position_ratio = (existing_value + trade_value) / total_assets
        else:
            position_ratio = 0
        
        if position_ratio > self.config["max_position_ratio"]:
            warning = f"[WARN] {symbol} 仓位占比 {position_ratio:.2%} 超过上限 {self.config['max_position_ratio']:.2%}"
            self._warnings.append(warning)
            if self.kill_switch:
                _log_event("risk_controller", "governance_layer", "warning",
                           f"buy blocked: {symbol} - position ratio exceeded")
                return self._build_result(False, warning, "blocked")
            else:
                _log_event("risk_controller", "governance_layer", "warning",
                           f"buy recorded (observe): {symbol} - position ratio exceeded")
        
        # 3. 检查持仓数量上限
        if len(current_positions) >= self.config["max_positions"] and not existing_pos:
            warning = f"[WARN] 持仓数量 {len(current_positions)} 已达上限"
            self._warnings.append(warning)
            if self.kill_switch:
                return self._build_result(False, warning, "blocked")
        
        # 4. 检查资金是否足够
        if trade_value > total_cash:
            warning = f"[WARN] 资金不足: 需要 {trade_value:.2f}, 现金 {total_cash:.2f}"
            self._warnings.append(warning)
            if self.kill_switch:
                return self._build_result(False, warning, "blocked")
        
        # 通过所有检查
        runtime_ms = int((datetime.now(timezone.utc) - start).total_seconds() * 1000)
        
        if self.kill_switch:
            # 观察模式：记录但不执行
            _log_event("risk_controller", "governance_layer", "success",
                       f"buy recorded (observe): {symbol} x{quantity} @ {price}", runtime_ms)
            return self._build_result(True, "观察模式：已记录买入信号", "recorded")
        else:
            _log_event("risk_controller", "governance_layer", "success",
                       f"buy approved: {symbol} x{quantity} @ {price}", runtime_ms)
            return self._build_result(True, "买入通过风险控制", "executed")
    
    def check_sell(self, symbol: str, quantity: int, price: float,
                   current_positions: List[dict]) -> dict:
        """
        检查卖出信号
        
        Args:
            symbol: 股票代码
            quantity: 卖出数量
            price: 卖出价格
            current_positions: 当前持仓列表
        
        Returns:
            {
                "approved": bool,
                "reason": str,
                "warnings": list,
                "action": "executed" | "recorded" | "blocked"
            }
        """
        self._warnings = []
        start = datetime.now(timezone.utc)
        
        existing_pos = next((p for p in current_positions if p.get("symbol") == symbol), None)
        if not existing_pos:
            reason = f"[WARN] 无持仓可卖: {symbol}"
            _log_event("risk_controller", "governance_layer", "error", f"sell blocked: {symbol} - no position")
            return self._build_result(False, reason, "blocked")
        
        if quantity > existing_pos.get("quantity", 0):
            reason = f"[WARN] 卖出数量超过持仓: 要求 {quantity}, 持有 {existing_pos.get('quantity', 0)}"
            _log_event("risk_controller", "governance_layer", "error", f"sell blocked: {symbol} - qty exceeded")
            return self._build_result(False, reason, "blocked")
        
        runtime_ms = int((datetime.now(timezone.utc) - start).total_seconds() * 1000)
        
        if self.kill_switch:
            _log_event("risk_controller", "governance_layer", "success",
                       f"sell recorded (observe): {symbol} x{quantity} @ {price}", runtime_ms)
            return self._build_result(True, "观察模式：已记录卖出信号", "recorded")
        else:
            _log_event("risk_controller", "governance_layer", "success",
                       f"sell approved: {symbol} x{quantity} @ {price}", runtime_ms)
            return self._build_result(True, "卖出通过风险控制", "executed")
    
    def check_stop_loss(self, symbol: str, current_price: float,
                         avg_price: float) -> dict:
        """
        检查是否触发止损
        
        Args:
            symbol: 股票代码
            current_price: 当前价格
            avg_price: 持仓均价
        
        Returns:
            {"triggered": bool, "loss_ratio": float, "action": str}
        """
        if avg_price <= 0 or current_price <= 0:
            return {"triggered": False, "loss_ratio": 0.0, "action": "none"}
        
        loss_ratio = (current_price - avg_price) / avg_price
        threshold = self.config["stop_loss_threshold"]
        
        if loss_ratio <= threshold:
            message = f"[STOP_LOSS] {symbol} 亏损 {loss_ratio:.2%} 触发止损阈值 {threshold:.2%}"
            _log_event("risk_controller", "governance_layer", "warning", message)
            
            if self.kill_switch:
                return {"triggered": True, "loss_ratio": loss_ratio,
                        "action": "recorded (observe)", "message": message}
            else:
                return {"triggered": True, "loss_ratio": loss_ratio,
                        "action": "execute_stop_loss", "message": message}
        
        return {"triggered": False, "loss_ratio": loss_ratio, "action": "none"}
    
    def _build_result(self, approved: bool, reason: str, action: str) -> dict:
        return {
            "approved": approved,
            "reason": reason,
            "warnings": self._warnings.copy(),
            "action": action,
            "kill_switch": self.kill_switch,
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
    
    def get_config(self) -> dict:
        """获取当前风险配置"""
        return self.config.copy()
    
    def export_snapshot(self) -> dict:
        """导出自包含快照"""
        return {
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "kill_switch": self.kill_switch,
            "config": self.config,
        }


if __name__ == "__main__":
    rc = RiskController()
    print(json.dumps(rc.get_config(), ensure_ascii=False, indent=2))
