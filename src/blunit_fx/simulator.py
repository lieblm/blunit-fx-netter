"""Order generation and simulation runner for Blunit FX Internalizer."""

import csv
import random
from datetime import datetime, timedelta
from pathlib import Path
from typing import Generator, List, Optional, Dict, Any, Union

from .models import ClientOrder, OrderSide, ExecutionReport, HedgeTrade, TradeRecord
from .engine import InternalizerEngine
from .pricing import PricingModel
from .data_loader import MarketCandle


class OrderGenerator:
    """Generates synthetic client FX order streams."""

    def __init__(self, seed: Optional[int] = None) -> None:
        self.rng = random.Random(seed)

    def generate_orders(
        self,
        count: int = 100,
        min_volume: float = 500.0,
        max_volume: float = 4000.0,
        buy_probability: float = 0.52,
        start_time: Optional[datetime] = None,
    ) -> List[ClientOrder]:
        """Generate a batch list of synthetic client orders with static or relative timestamps."""
        return list(
            self.stream_orders(
                count=count,
                min_volume=min_volume,
                max_volume=max_volume,
                buy_probability=buy_probability,
                start_time=start_time,
            )
        )

    def stream_orders(
        self,
        count: int = 100,
        min_volume: float = 500.0,
        max_volume: float = 4000.0,
        buy_probability: float = 0.52,
        start_time: Optional[datetime] = None,
    ) -> Generator[ClientOrder, None, None]:
        """Stream synthetic client orders iteratively."""
        curr_time = start_time or datetime.now()

        for i in range(1, count + 1):
            curr_time += timedelta(seconds=self.rng.randint(2, 45))
            side = (
                OrderSide.BUY
                if self.rng.random() < buy_probability
                else OrderSide.SELL
            )
            raw_volume = self.rng.uniform(min_volume, max_volume)
            volume = round(raw_volume / 50.0) * 50.0

            yield ClientOrder(
                order_id=f"ORD-{i:05d}",
                timestamp=curr_time,
                side=side,
                volume_eur=float(volume),
            )

    def generate_orders_for_candles(
        self,
        candles: List[MarketCandle],
        orders_per_candle: int = 1,
        min_volume: float = 500.0,
        max_volume: float = 4000.0,
        buy_probability: float = 0.50,
    ) -> List[tuple[ClientOrder, MarketCandle]]:
        """
        Generate orders synchronized with historical market candles.
        Each order is matched to its corresponding candle and prevailing price.
        """
        order_candle_pairs: List[tuple[ClientOrder, MarketCandle]] = []
        counter = 0

        for candle in candles:
            for j in range(orders_per_candle):
                counter += 1
                # Offset timestamp slightly within the 4-hour window
                offset_seconds = (j * 3600) + self.rng.randint(60, 1800)
                order_ts = candle.timestamp + timedelta(seconds=offset_seconds)

                side = (
                    OrderSide.BUY
                    if self.rng.random() < buy_probability
                    else OrderSide.SELL
                )
                raw_vol = self.rng.uniform(min_volume, max_volume)
                volume = round(raw_vol / 50.0) * 50.0

                order = ClientOrder(
                    order_id=f"ORD-{counter:06d}",
                    timestamp=order_ts,
                    side=side,
                    volume_eur=float(volume),
                )
                order_candle_pairs.append((order, candle))

        return order_candle_pairs


class SimulationRunner:
    """Runs internalization simulation and produces formatted reporting & CSV export."""

    def __init__(self, engine: Optional[InternalizerEngine] = None) -> None:
        self.engine: InternalizerEngine = engine or InternalizerEngine()

    def run(
        self,
        orders: List[ClientOrder],
        verbose: bool = False,
    ) -> Dict[str, Any]:
        """Execute simulation over a static order sequence."""
        for order in orders:
            exec_rep, hedge = self.engine.process_order(order)
            if verbose:
                print(
                    f"[{exec_rep.timestamp.strftime('%Y-%m-%d %H:%M:%S')}] {exec_rep.order_id} | "
                    f"Client {exec_rep.side.value:<4} {exec_rep.volume_eur:9.2f} EUR @ {exec_rep.client_rate:.4f} | "
                    f"NOP: {exec_rep.nop_after_eur:10.2f} EUR"
                )
            if hedge:
                if verbose:
                    print(
                        f"  >>> HEDGE TRIGGERED: {hedge.hedge_id} | Market {hedge.side.value:<4} "
                        f"{hedge.volume_eur:9.2f} EUR @ {hedge.hedge_rate:.4f} (Mid) | "
                        f"NOP reset to {hedge.nop_after_eur:.2f} EUR"
                    )

        return self.engine.get_summary()

    def run_historical(
        self,
        candles: List[MarketCandle],
        orders_per_candle: int = 1,
        min_volume: float = 500.0,
        max_volume: float = 4000.0,
        buy_probability: float = 0.50,
        seed: Optional[int] = 42,
        verbose: bool = False,
    ) -> Dict[str, Any]:
        """
        Execute simulation over real historical candles with dynamic market pricing.

        Args:
            candles: Chronological sequence of real market candles.
            orders_per_candle: Number of client orders generated per candle.
            min_volume: Minimum EUR client trade volume.
            max_volume: Maximum EUR client trade volume.
            buy_probability: Probability of client BUY order.
            seed: RNG seed for reproducible client flow.
            verbose: Verbose console logging flag.

        Returns:
            Dictionary with aggregated simulation metrics.
        """
        generator = OrderGenerator(seed=seed)
        pairs = generator.generate_orders_for_candles(
            candles=candles,
            orders_per_candle=orders_per_candle,
            min_volume=min_volume,
            max_volume=max_volume,
            buy_probability=buy_probability,
        )

        for order, candle in pairs:
            exec_rep, hedge = self.engine.process_order(
                order=order,
                current_market_rate=candle.mid_price,
            )
            if verbose:
                print(
                    f"[{order.timestamp.strftime('%Y-%m-%d %H:%M:%S')}] {exec_rep.order_id} | "
                    f"Market: {candle.mid_price:.4f} | Client {exec_rep.side.value:<4} "
                    f"{exec_rep.volume_eur:9.2f} EUR @ {exec_rep.client_rate:.4f} | "
                    f"NOP: {exec_rep.nop_after_eur:10.2f} EUR"
                )
            if hedge:
                if verbose:
                    print(
                        f"  >>> HEDGE: {hedge.hedge_id} | Market {hedge.side.value:<4} "
                        f"{hedge.volume_eur:9.2f} EUR @ {hedge.hedge_rate:.4f} (Mid) | "
                        f"NOP reset to {hedge.nop_after_eur:.2f} EUR"
                    )

        summary = self.engine.get_summary()
        if candles:
            summary["period_start"] = candles[0].timestamp
            summary["period_end"] = candles[-1].timestamp
            summary["total_candles"] = len(candles)
            summary["start_rate"] = candles[0].mid_price
            summary["end_rate"] = candles[-1].mid_price

        return summary

    def export_csv(self, filepath: Union[str, Path]) -> Path:
        """Export full trade ledger (trades, balances, running PnL) to CSV."""
        return self.engine.export_csv(filepath)

    def print_csv(self, max_rows: Optional[int] = None) -> None:
        """Print trade ledger CSV content directly to stdout."""
        records = self.engine.trade_log
        if not records:
            print("No trades executed.")
            return

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

        print(",".join(fieldnames))
        display_records = records if (max_rows is None or len(records) <= max_rows) else records[:max_rows]

        for r in display_records:
            print(
                f"{r.trade_id},"
                f"{r.timestamp.isoformat()},"
                f"{r.event_type},"
                f"{r.side.value},"
                f"{r.volume_eur:.2f},"
                f"{r.execution_rate:.4f},"
                f"{r.volume_czk:.2f},"
                f"{r.spread_profit_czk:.2f},"
                f"{r.balance_eur:.2f},"
                f"{r.balance_czk:.2f},"
                f"{r.nop_eur:.2f},"
                f"{r.market_rate:.4f},"
                f"{r.running_pnl_czk:.2f},"
                f"{r.running_pnl_eur:.2f}"
            )

        if max_rows is not None and len(records) > max_rows:
            print(f"# ... ({len(records) - max_rows} additional trade records omitted from console output)")

    def print_report(self, summary: Dict[str, Any]) -> None:
        """Render a clean, structured console report."""
        divider = "=" * 72
        sub_divider = "-" * 72

        print("\n" + divider)
        print("          BLUNIT FX INTERNALIZER - SIMULATION REPORT")
        print(divider)

        if "period_start" in summary and "period_end" in summary:
            print(" [Simulation Period & Real FX Data]")
            start_str = summary["period_start"].strftime("%Y-%m-%d %H:%M")
            end_str = summary["period_end"].strftime("%Y-%m-%d %H:%M")
            print(f"   Period:                 {start_str}  -->  {end_str}")
            print(f"   Processed Candles:      {summary.get('total_candles', 0):,} (H4 bars)")
            print(f"   Market Rates:           Start: {summary.get('start_rate', 0.0):.4f} CZK/EUR | End: {summary.get('end_rate', 0.0):.4f} CZK/EUR")
            print()

        print(" [Configuration]")
        print(f"   Latest Reference Rate:  {summary['mid_rate']:.4f} CZK/EUR")
        print(f"   Client Spread:          {summary['spread_pct'] * 100:.2f}% (Half-spread: {summary['spread_pct'] * 50:.2f}%)")
        print(f"   Auto-Hedge Limit:       {summary['hedge_limit_eur']:,.2f} EUR")

        print("\n [Client Order Flow]")
        print(f"   Total Orders:           {summary['total_orders']:,}")
        print(f"   - Client BUY EUR:       {summary['buy_orders_count']:,} orders ({summary['buy_volume_eur']:,.2f} EUR)")
        print(f"   - Client SELL EUR:      {summary['sell_orders_count']:,} orders ({summary['sell_volume_eur']:,.2f} EUR)")
        print(f"   Total Volume (EUR):     {summary['total_volume_eur']:,.2f} EUR")
        print(f"   Total Volume (CZK):     {summary['total_volume_czk']:,.2f} CZK")

        print("\n [Internalization & Risk Management]")
        print(f"   Hedge Operations:       {summary['hedge_count']:,} external market trade(s)")
        print(f"   Total Hedged Volume:    {summary['total_hedged_eur']:,.2f} EUR")
        print(f"   Internalized Volume:    {summary['internalized_volume_eur']:,.2f} EUR")
        print(f"   Internalization Rate:   {summary['internalization_rate_pct']:.2f}%")
        print(f"   Final Net Open Pos (NOP): {summary['final_nop_eur']:,.2f} EUR")

        print("\n [Account Balances & Profitability]")
        print(f"   Ending EUR Balance:     {summary['final_balance_eur']:,.2f} EUR")
        print(f"   Ending CZK Balance:     {summary['final_balance_czk']:,.2f} CZK")
        print(f"   Accumulated Spread:     {summary['accumulated_spread_czk']:,.2f} CZK")
        print(f"   Mark-to-Market PnL:     {summary['total_pnl_czk']:,.2f} CZK (~ {summary['total_pnl_eur']:,.2f} EUR)")
        print(f"   Total Ledger Records:   {summary.get('total_records', 0):,} (client trades + hedges)")
        print(sub_divider)
        print(" [Conclusion]")
        if summary['total_pnl_czk'] > 0:
            print(f"   SUCCESS: Strategy generated positive spread revenue of {summary['total_pnl_czk']:,.2f} CZK.")
        else:
            print(f"   RESULT: Strategy recorded PnL of {summary['total_pnl_czk']:,.2f} CZK.")
        print(divider + "\n")
