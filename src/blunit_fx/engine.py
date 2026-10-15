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
    - Triggers auto-hedging against external market at current market rate when NOP limit is reached.
    - Maintains a complete chronological ledger (trade_log) for audit and CSV export.
    """

    def __init__(
        self,
        pricing_model: Optional[PricingModel] = None,
        hedge_limit: float = 10_000.0,
    ) -> None:
        self.pricing_model: PricingModel = pricing_model or PricingModel()
        self.hedge_limit: float = hedge_limit
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
        Process an incoming client order, update balances, and evaluate hedge trigger.

        Args:
            order: Client order instance.
            current_market_rate: Prevailing market mid/reference rate (defaults to pricing model's mid).

        Returns:
            Tuple of (ExecutionReport, Optional[HedgeTrade])
        """
        mid_rate = current_market_rate if current_market_rate is not None else self.pricing_model.mid_rate
        self.last_market_rate = mid_rate

        rate = self.pricing_model.get_client_rate(order.side, mid_rate=mid_rate)
        volume_czk = order.volume_eur * rate
        spread_profit = self.pricing_model.calculate_spread_profit(order.volume_eur, mid_rate=mid_rate)

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
            )
        )

        # Check auto-hedging condition
        hedge_trade = None
        if abs(self.account.nop_eur) >= self.hedge_limit:
            hedge_trade = self._execute_hedge(timestamp=order.timestamp, market_rate=mid_rate)

        return exec_report, hedge_trade

    def _execute_hedge(self, timestamp, market_rate: Optional[float] = None) -> HedgeTrade:
        """
        Execute an external market hedge trade at market rate to reset NOP to zero.
        """
        self._hedge_sequence += 1
        nop_before = self.account.nop_eur
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
            "total_records": len(self.trade_log),
        }


# Backwards compatibility alias
InternalizerEngine = NetterEngine
