"""Pricing model for EUR/CZK client trades."""

from dataclasses import dataclass
from .models import OrderSide


@dataclass
class PricingModel:
    """
    Static market pricing model with symmetric bid/ask spread.
    
    Currency pair: EUR/CZK (Base: EUR, Quote: CZK).
    mid_rate: Market reference mid rate (e.g., 24.50 CZK per EUR).
    spread_pct: Full bid-ask spread as a fraction (e.g., 0.004 for 0.4%).
                Half-spread applied to each side is spread_pct / 2.
    """
    mid_rate: float = 24.50
    spread_pct: float = 0.004

    @property
    def half_spread(self) -> float:
        """Half-spread margin applied to mid rate."""
        return self.spread_pct / 2.0

    @property
    def bid_rate(self) -> float:
        """Client sell rate (Internalizer buys EUR from client)."""
        return self.mid_rate * (1.0 - self.half_spread)

    @property
    def ask_rate(self) -> float:
        """Client buy rate (Internalizer sells EUR to client)."""
        return self.mid_rate * (1.0 + self.half_spread)

    def get_client_rate(self, side: OrderSide, mid_rate: float | None = None) -> float:
        """
        Get execution rate for client based on order side.
        - BUY: Client buys EUR at Ask.
        - SELL: Client sells EUR at Bid.
        """
        ref_mid = mid_rate if mid_rate is not None else self.mid_rate
        if side == OrderSide.BUY:
            return ref_mid * (1.0 + self.half_spread)
        return ref_mid * (1.0 - self.half_spread)

    def calculate_spread_profit(self, volume_eur: float, mid_rate: float | None = None) -> float:
        """
        Calculate internalized spread profit in CZK for a trade.
        Symmetric spread profit is volume_eur * ref_mid * half_spread.
        """
        ref_mid = mid_rate if mid_rate is not None else self.mid_rate
        return volume_eur * ref_mid * self.half_spread

