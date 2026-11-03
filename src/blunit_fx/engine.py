"""Netter engine implementation for Blunit FX."""

import csv
from pathlib import Path
from typing import List, Optional, Tuple, Dict, Any, Union
from .models import ClientOrder, ExecutionReport, HedgeTrade, OrderSide, AccountState, TradeRecord
from .pricing import PricingModel


class NetterEngine:
    """
    Core netting and risk management engine for EUR/CZK.
    
    Acts as an internal netter and market maker:
    - Nets client flows against the omnibus account.
    - Charges bid/ask spread and accumulates spread revenue.
    - Tracks Net Open Position (NOP) in EUR.
    - Triggers auto-hedging against external market at current market rate.
    - Supports:
        1. Full hedging (reset to 0 EUR).
        2. Partial hedging (reduction to target buffer ratio).
        3. Opportunistic hedging (smart market-timing of inventory reduction before hitting hard stop).
    - Maintains a complete chronological ledger (trade_log) for audit and CSV export.
    """

    def __init__(
        self,
        pricing_model: Optional[PricingModel] = None,
        hedge_limit: float = 25_000.0,
        hedge_target_ratio: float = 0.0,
        enable_opportunistic_hedge: bool = False,
        opportunistic_threshold: float = 17_500.0,
        timing_window: int = 20,
        timing_k: float = 0.75,
    ) -> None:
        self.pricing_model: PricingModel = pricing_model or PricingModel(hedge_limit=hedge_limit)
        self.hedge_limit: float = hedge_limit
        self.hedge_target_ratio: float = max(0.0, min(0.9, hedge_target_ratio))
        self.enable_opportunistic_hedge: bool = enable_opportunistic_hedge
        self.opportunistic_threshold: float = opportunistic_threshold
        self.timing_window: int = timing_window
        self.timing_k: float = timing_k
        self.rate_history: List[float] = []

        self.account: AccountState = AccountState()
        self.executions: List[ExecutionReport] = []
        self.hedges: List[HedgeTrade] = []
        self.trade_log: List[TradeRecord] = []
        self._hedge_sequence: int = 0
        self.last_market_rate: float = self.pricing_model.mid_rate

    @property
    def nop_eur(self) -> float:
        """Current Net Open Position in EUR."""
        return self.account.nop_eur

    def process_order(
        self,
        order: ClientOrder,
        current_market_rate: Optional[float] = None,
    ) -> Tuple[ExecutionReport, Optional[HedgeTrade]]:
        """
        Process an incoming client order, update balances, and evaluate hedge triggers.

        Args:
            order: Client order instance.
            current_market_rate: Prevailing market mid/reference rate (defaults to pricing model's mid).

        Returns:
            Tuple of (ExecutionReport, Optional[HedgeTrade])
        """
        mid_rate = current_market_rate if current_market_rate is not None else self.pricing_model.mid_rate
        self.last_market_rate = mid_rate
        self.rate_history.append(mid_rate)

        rate = self.pricing_model.get_client_rate(
            side=order.side,
            mid_rate=mid_rate,
            current_nop=self.account.nop_eur,
        )
        volume_czk = order.volume_eur * rate
        spread_profit = self.pricing_model.calculate_spread_profit(
            volume_eur=order.volume_eur,
            side=order.side,
            mid_rate=mid_rate,
            current_nop=self.account.nop_eur,
        )

        # Update omnibus balances according to client flow
        if order.side == OrderSide.BUY:
            # Client buys EUR -> Engine delivers EUR, receives CZK
            self.account.balance_eur -= order.volume_eur
            self.account.balance_czk += volume_czk
        else:
            # Client sells EUR -> Engine receives EUR, delivers CZK
            self.account.balance_eur += order.volume_eur
            self.account.balance_czk -= volume_czk

        self.account.total_spread_profit_czk += spread_profit

        exec_report = ExecutionReport(
            order_id=order.order_id,
            timestamp=order.timestamp,
            side=order.side,
            volume_eur=order.volume_eur,
            client_rate=rate,
            mid_rate=mid_rate,
            volume_czk=volume_czk,
            spread_profit_czk=spread_profit,
            nop_after_eur=self.account.nop_eur,
        )
        self.executions.append(exec_report)

        # Calculate running Mark-to-Market PnL
        running_mtm_czk = self.account.mtm_pnl_czk(mid_rate)
        running_mtm_eur = running_mtm_czk / mid_rate if mid_rate > 0 else 0.0

        # Record to ledger
        self.trade_log.append(
            TradeRecord(
                trade_id=order.order_id,
                timestamp=order.timestamp,
                event_type="CLIENT",
                side=order.side,
                volume_eur=order.volume_eur,
                execution_rate=rate,
                volume_czk=volume_czk,
                spread_profit_czk=spread_profit,
                balance_eur=self.account.balance_eur,
                balance_czk=self.account.balance_czk,
                nop_eur=self.account.nop_eur,
                market_rate=mid_rate,
                running_pnl_czk=running_mtm_czk,
                running_pnl_eur=running_mtm_eur,
                event_subtype="",
            )
        )

        # Evaluate auto-hedging triggers
        hedge_trade = None
        nop = self.account.nop_eur

        # Trigger 1: Hard Stop emergency hedge
        if abs(nop) >= self.hedge_limit:
            hedge_trade = self._execute_hedge(
                timestamp=order.timestamp,
                market_rate=mid_rate,
                hedge_type="HARD_STOP",
            )
        # Trigger 2: Opportunistic Hedging (favorable market timing of inventory reduction)
        elif self.enable_opportunistic_hedge and abs(nop) >= self.opportunistic_threshold:
            if len(self.rate_history) >= max(5, self.timing_window // 2):
                recent_rates = self.rate_history[-self.timing_window:]
                mean_rate = sum(recent_rates) / len(recent_rates)
                variance = sum((r - mean_rate) ** 2 for r in recent_rates) / len(recent_rates)
                std_rate = variance ** 0.5 or 0.0001

                # If long EUR: offload EUR when market rate is at or above upper band
                if nop > 0 and mid_rate >= (mean_rate + self.timing_k * std_rate):
                    hedge_trade = self._execute_hedge(
                        timestamp=order.timestamp,
                        market_rate=mid_rate,
                        hedge_type="OPPORTUNISTIC",
                    )
                # If short EUR: cover EUR when market rate is at or below lower band
                elif nop < 0 and mid_rate <= (mean_rate - self.timing_k * std_rate):
                    hedge_trade = self._execute_hedge(
                        timestamp=order.timestamp,
                        market_rate=mid_rate,
                        hedge_type="OPPORTUNISTIC",
                    )

        return exec_report, hedge_trade

    def _execute_hedge(
        self,
        timestamp,
        market_rate: Optional[float] = None,
        hedge_type: str = "HARD_STOP",
    ) -> HedgeTrade:
        """
        Execute an external market hedge trade at market rate.
        If hedge_target_ratio is 0.0, resets NOP to 0.
        If hedge_target_ratio > 0.0, brings NOP down to hedge_limit * hedge_target_ratio.
        """
        self._hedge_sequence += 1
        nop_before = self.account.nop_eur

        target_nop_mag = self.hedge_limit * self.hedge_target_ratio
        target_nop = target_nop_mag if nop_before > 0 else -target_nop_mag
        hedge_volume = abs(nop_before) - abs(target_nop)
        if hedge_volume <= 0:
            hedge_volume = abs(nop_before)

        mid_rate = market_rate if market_rate is not None else self.last_market_rate

        if nop_before > 0:
            # Engine is long EUR -> Sell EUR on external market
            hedge_side = OrderSide.SELL
            czk_amount = hedge_volume * mid_rate
            self.account.balance_eur -= hedge_volume
            self.account.balance_czk += czk_amount
        else:
            # Engine is short EUR -> Buy EUR on external market
            hedge_side = OrderSide.BUY
            czk_amount = hedge_volume * mid_rate
            self.account.balance_eur += hedge_volume
            self.account.balance_czk -= czk_amount

        hedge = HedgeTrade(
            hedge_id=f"HEDGE-{self._hedge_sequence:04d}",
            timestamp=timestamp,
            side=hedge_side,
            volume_eur=hedge_volume,
            hedge_rate=mid_rate,
            volume_czk=czk_amount,
            nop_before_eur=nop_before,
            nop_after_eur=self.account.nop_eur,
            hedge_type=hedge_type,
        )
        self.hedges.append(hedge)

        # Running Mark-to-Market PnL after hedge
        running_mtm_czk = self.account.mtm_pnl_czk(mid_rate)
        running_mtm_eur = running_mtm_czk / mid_rate if mid_rate > 0 else 0.0

        # Record hedge to ledger
        self.trade_log.append(
            TradeRecord(
                trade_id=hedge.hedge_id,
                timestamp=timestamp,
                event_type="HEDGE",
                side=hedge_side,
                volume_eur=hedge_volume,
                execution_rate=mid_rate,
                volume_czk=czk_amount,
                spread_profit_czk=0.0,
                balance_eur=self.account.balance_eur,
                balance_czk=self.account.balance_czk,
                nop_eur=self.account.nop_eur,
                market_rate=mid_rate,
                running_pnl_czk=running_mtm_czk,
                running_pnl_eur=running_mtm_eur,
                event_subtype=hedge_type,
            )
        )

        return hedge

    def export_csv(self, filepath: Union[str, Path]) -> Path:
        """Export chronological trade ledger with balances and running PnL to CSV."""
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)

        fieldnames = [
            "trade_id",
            "timestamp",
            "event_type",
            "event_subtype",
            "side",
            "volume_eur",
            "execution_rate",
            "volume_czk",
            "spread_profit_czk",
            "balance_eur",
            "balance_czk",
            "nop_eur",
            "market_rate",
            "running_pnl_czk",
            "running_pnl_eur",
        ]

        with open(path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for record in self.trade_log:
                writer.writerow({
                    "trade_id": record.trade_id,
                    "timestamp": record.timestamp.isoformat(),
                    "event_type": record.event_type,
                    "event_subtype": record.event_subtype,
                    "side": record.side.value,
                    "volume_eur": f"{record.volume_eur:.2f}",
                    "execution_rate": f"{record.execution_rate:.4f}",
                    "volume_czk": f"{record.volume_czk:.2f}",
                    "spread_profit_czk": f"{record.spread_profit_czk:.2f}",
                    "balance_eur": f"{record.balance_eur:.2f}",
                    "balance_czk": f"{record.balance_czk:.2f}",
                    "nop_eur": f"{record.nop_eur:.2f}",
                    "market_rate": f"{record.market_rate:.4f}",
                    "running_pnl_czk": f"{record.running_pnl_czk:.2f}",
                    "running_pnl_eur": f"{record.running_pnl_eur:.2f}",
                })

        return path

    def get_summary(self) -> Dict[str, Any]:
        """Generate comprehensive execution and performance summary."""
        total_orders = len(self.executions)
        total_vol_eur = sum(e.volume_eur for e in self.executions)
        total_vol_czk = sum(e.volume_czk for e in self.executions)

        buy_orders = [e for e in self.executions if e.side == OrderSide.BUY]
        sell_orders = [e for e in self.executions if e.side == OrderSide.SELL]

        buy_vol_eur = sum(e.volume_eur for e in buy_orders)
        sell_vol_eur = sum(e.volume_eur for e in sell_orders)

        total_hedged_eur = sum(h.volume_eur for h in self.hedges)
        hard_hedges = [h for h in self.hedges if h.hedge_type == "HARD_STOP"]
        opp_hedges = [h for h in self.hedges if h.hedge_type == "OPPORTUNISTIC"]

        mtm_pnl_czk = self.account.mtm_pnl_czk(self.last_market_rate)
        mtm_pnl_eur = mtm_pnl_czk / self.last_market_rate if self.last_market_rate else 0.0

        netted_vol_eur = max(0.0, total_vol_eur - total_hedged_eur)
        netting_rate = (netted_vol_eur / total_vol_eur * 100.0) if total_vol_eur > 0 else 0.0

        return {
            "total_orders": total_orders,
            "buy_orders_count": len(buy_orders),
            "sell_orders_count": len(sell_orders),
            "total_volume_eur": total_vol_eur,
            "total_volume_czk": total_vol_czk,
            "buy_volume_eur": buy_vol_eur,
            "sell_volume_eur": sell_vol_eur,
            "hedge_count": len(self.hedges),
            "hard_hedge_count": len(hard_hedges),
            "opportunistic_hedge_count": len(opp_hedges),
            "total_hedged_eur": total_hedged_eur,
            "netted_volume_eur": netted_vol_eur,
            "netting_rate_pct": netting_rate,
            # Backwards compatibility aliases
            "internalized_volume_eur": netted_vol_eur,
            "internalization_rate_pct": netting_rate,
            "final_nop_eur": self.account.nop_eur,
            "final_balance_eur": self.account.balance_eur,
            "final_balance_czk": self.account.balance_czk,
            "accumulated_spread_czk": self.account.total_spread_profit_czk,
            "total_pnl_czk": mtm_pnl_czk,
            "total_pnl_eur": mtm_pnl_eur,
            "mid_rate": self.last_market_rate,
            "spread_pct": self.pricing_model.spread_pct,
            "hedge_limit_eur": self.hedge_limit,
            "hedge_target_ratio": self.hedge_target_ratio,
            "enable_opportunistic_hedge": self.enable_opportunistic_hedge,
            "opportunistic_threshold": self.opportunistic_threshold,
            "skew_factor": self.pricing_model.skew_factor,
            "total_records": len(self.trade_log),
        }


# Backwards compatibility alias
InternalizerEngine = NetterEngine
