"""Data models for Blunit FX Internalizer."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class OrderSide(str, Enum):
    """Side of the order from the client's perspective for the base currency (EUR)."""
    BUY = "BUY"    # Client buys EUR, pays CZK
    SELL = "SELL"  # Client sells EUR, receives CZK

    @property
    def opposite(self) -> "OrderSide":
        """Return opposite side."""
        return OrderSide.SELL if self == OrderSide.BUY else OrderSide.BUY


@dataclass(frozen=True)
class ClientOrder:
    """Incoming client FX order."""
    order_id: str
    timestamp: datetime
    side: OrderSide
    volume_eur: float


@dataclass(frozen=True)
class ExecutionReport:
    """Result of internalizing a client order."""
    order_id: str
    timestamp: datetime
    side: OrderSide
    volume_eur: float
    client_rate: float
    mid_rate: float
    volume_czk: float
    spread_profit_czk: float
    nop_after_eur: float


@dataclass(frozen=True)
class HedgeTrade:
    """External hedge execution to neutralize Net Open Position (NOP)."""
    hedge_id: str
    timestamp: datetime
    side: OrderSide   # Side of hedge trade for EUR on external market
    volume_eur: float
    hedge_rate: float # Executed at mid rate (0 spread)
    volume_czk: float
    nop_before_eur: float
    nop_after_eur: float


@dataclass
class AccountState:
    """Current state of omnibus internalizer account."""
    balance_eur: float = 0.0
    balance_czk: float = 0.0
    total_spread_profit_czk: float = 0.0

    @property
    def nop_eur(self) -> float:
        """Net Open Position in base currency (EUR)."""
        return self.balance_eur

    def mtm_pnl_czk(self, mid_rate: float) -> float:
        """
        Mark-to-Market total PnL in quote currency (CZK).
        MtM PnL = balance_czk + balance_eur * mid_rate.
        """
        return self.balance_czk + (self.balance_eur * mid_rate)


@dataclass(frozen=True)
class TradeRecord:
    """
    Unified ledger record of an executed transaction (client trade or hedge)
    including resulting account balances and running Mark-to-Market PnL.
    """
    trade_id: str
    timestamp: datetime
    event_type: str         # "CLIENT" or "HEDGE"
    side: OrderSide
    volume_eur: float
    execution_rate: float
    volume_czk: float
    spread_profit_czk: float
    balance_eur: float
    balance_czk: float
    nop_eur: float
    market_rate: float
    running_pnl_czk: float
    running_pnl_eur: float

