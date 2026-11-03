"""Pricing model for EUR/CZK client trades with inventory skewing support."""

from dataclasses import dataclass
from .models import OrderSide


@dataclass
class PricingModel:
    """
    Market pricing model for EUR/CZK with symmetric bid/ask spread
    and optional inventory-based price skewing (Avellaneda-Stoikov).

    Currency pair: EUR/CZK (Base: EUR, Quote: CZK).
    mid_rate: Market reference mid rate (e.g., 24.50 CZK per EUR).
    spread_pct: Full bid-ask spread as a fraction (e.g., 0.004 for 0.4%).
                Half-spread applied to each side is spread_pct / 2.
    skew_factor: Price skew intensity per unit of inventory ratio (e.g., 0.0005 for 5 bps).
    hedge_limit: Net Open Position limit in EUR used to normalize inventory ratio.
    """
    mid_rate: float = 24.50
    spread_pct: float = 0.004
    skew_factor: float = 0.0
    hedge_limit: float = 25_000.0

    @property
    def half_spread(self) -> float:
        """Half-spread margin applied to mid rate."""
        return self.spread_pct / 2.0

    @property
    def bid_rate(self) -> float:
        """Client sell rate (Internalizer buys EUR from client) at base mid rate."""
        return self.mid_rate * (1.0 - self.half_spread)

    @property
    def ask_rate(self) -> float:
        """Client buy rate (Internalizer sells EUR to client) at base mid rate."""
        return self.mid_rate * (1.0 + self.half_spread)

    def get_skewed_mid(self, mid_rate: float | None = None, current_nop: float = 0.0) -> float:
        """
        Calculate skewed reference mid rate based on inventory position.
        - When long EUR (NOP > 0): Skew mid downwards to attract buyers of EUR and deter sellers.
        - When short EUR (NOP < 0): Skew mid upwards to attract sellers of EUR and deter buyers.
        """
        base_mid = mid_rate if mid_rate is not None else self.mid_rate
        if self.skew_factor > 0.0 and self.hedge_limit > 0.0:
            inv_ratio = max(-1.0, min(1.0, current_nop / self.hedge_limit))
            return base_mid * (1.0 - self.skew_factor * inv_ratio)
        return base_mid

    def get_client_rate(
        self,
        side: OrderSide,
        mid_rate: float | None = None,
        current_nop: float = 0.0,
    ) -> float:
        """
        Get execution rate for client based on order side and inventory skew.
        - BUY: Client buys EUR at Ask.
        - SELL: Client sells EUR at Bid.
        """
        ref_mid = self.get_skewed_mid(mid_rate=mid_rate, current_nop=current_nop)
        if side == OrderSide.BUY:
            return ref_mid * (1.0 + self.half_spread)
        return ref_mid * (1.0 - self.half_spread)

    def calculate_spread_profit(
        self,
        volume_eur: float,
        side: OrderSide = OrderSide.BUY,
        mid_rate: float | None = None,
        current_nop: float = 0.0,
    ) -> float:
        """
        Calculate internalized spread profit in CZK for a trade against market mid.
        Difference between client execution rate and unskewed market mid rate.
        """
        base_mid = mid_rate if mid_rate is not None else self.mid_rate
        client_rate = self.get_client_rate(side=side, mid_rate=base_mid, current_nop=current_nop)

        if side == OrderSide.BUY:
            # Client pays client_rate to engine, market benchmark is base_mid
            return volume_eur * (client_rate - base_mid)
        else:
            # Engine pays client_rate to client, receives EUR worth base_mid
            return volume_eur * (base_mid - client_rate)


@dataclass
class InventorySkewPricingModel(PricingModel):
    """Convenience subclass with active inventory skewing defaults."""
    skew_factor: float = 0.0005  # 5 bps max skew
    hedge_limit: float = 25_000.0
