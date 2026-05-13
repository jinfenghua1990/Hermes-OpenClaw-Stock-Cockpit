"""
Paper Trading System - 模拟交易模块
提供仓位管理、风险控制、盈亏追踪功能，用于观察模式下的交易模拟

KILL_SWITCH=false (观察模式) 时记录所有交易但不执行真实下单
"""

from .position_manager import PositionManager
from .risk_controller import RiskController
from .pnl_tracker import PnLTracker

__all__ = ["PositionManager", "RiskController", "PnLTracker"]
