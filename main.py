#!/usr/bin/env python3
"""
Blunit FX Internalizer - Main Execution Script.

Runs simulation of EUR/CZK internalization engine with real market rates
from historical data, start/end date range, auto-hedging, and CSV export.

Usage:
    python3 main.py --start-date 2023-01-01 --end-date 2023-12-31
    python3 main.py --print-csv --csv-limit 30
    python3 main.py --export-csv fxdata/my_results.csv
"""

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# Ensure src is on Python path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from blunit_fx.pricing import PricingModel
from blunit_fx.engine import InternalizerEngine
from blunit_fx.simulator import OrderGenerator, SimulationRunner
from blunit_fx.data_loader import load_market_data


def parse_date(date_str: Optional[str]) -> Optional[datetime]:
    """Parse date from CLI string into UTC datetime."""
    if not date_str:
        return None
    date_str = date_str.strip()
    for fmt in (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d",
        "%Y.%m.%d",
        "%d.%m.%Y",
    ):
        try:
            return datetime.strptime(date_str, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    try:
        return datetime.fromisoformat(date_str).replace(tzinfo=timezone.utc)
    except Exception as exc:
        raise ValueError(
            f"Invalid date format: '{date_str}'. Expected YYYY-MM-DD or YYYY-MM-DD HH:MM:SS."
        ) from exc


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Blunit FX Internalizer - Backtest & Simulation on Real FX Data",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--data-file",
        type=str,
        default="fxdata/eurczk-h4-bid-2017-01-02-2026-10-15.csv",
        help="Path to real historical FX market quotes CSV file",
    )
    parser.add_argument(
        "--start-date",
        type=str,
        default=None,
        help="Počátek testu / Start date filter (e.g. 2023-01-01 or 2024-01-01 00:00:00)",
    )
    parser.add_argument(
        "--end-date",
        type=str,
        default=None,
        help="Konec testu / End date filter (e.g. 2023-12-31)",
    )
    parser.add_argument(
        "--orders-per-candle",
        type=int,
        default=1,
        help="Number of client orders generated per market candle interval",
    )
    parser.add_argument(
        "--spread",
        type=float,
        default=0.004,
        help="Full client spread percentage (0.004 = 0.40%%, half-spread = 0.20%%)",
    )
    parser.add_argument(
        "--hedge-limit",
        type=float,
        default=10_000.0,
        help="Net Open Position (NOP) threshold in EUR that triggers auto-hedging",
    )
    parser.add_argument(
        "--export-csv",
        type=str,
        default="fxdata/simulation_results.csv",
        help="Path to save individual trades, balances, and running PnL in CSV format",
    )
    parser.add_argument(
        "--print-csv",
        action="store_true",
        help="Print CSV output of trades, balances, and running PnL to stdout",
    )
    parser.add_argument(
        "--csv-limit",
        type=int,
        default=None,
        help="Limit number of CSV rows printed to console when --print-csv is used",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for reproducible order stream generation",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Print order-by-order execution log and hedge events",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    start_dt = parse_date(args.start_date)
    end_dt = parse_date(args.end_date)

    data_path = Path(args.data_file)

    # 1. Load real historical data if available
    if data_path.exists() and data_path.stat().st_size > 0:
        candles = load_market_data(
            filepath=data_path,
            start_date=start_dt,
            end_date=end_dt,
        )
        if not candles:
            print(f"Error: No candles found in {data_path} for date range {args.start_date} -> {args.end_date}")
            sys.exit(1)

        initial_mid = candles[0].mid_price
        pricing = PricingModel(mid_rate=initial_mid, spread_pct=args.spread)
        engine = InternalizerEngine(pricing_model=pricing, hedge_limit=args.hedge_limit)
        runner = SimulationRunner(engine=engine)

        summary = runner.run_historical(
            candles=candles,
            orders_per_candle=args.orders_per_candle,
            seed=args.seed,
            verbose=args.verbose,
        )
    else:
        # Fallback to synthetic mode if CSV not provided
        pricing = PricingModel(mid_rate=24.50, spread_pct=args.spread)
        engine = InternalizerEngine(pricing_model=pricing, hedge_limit=args.hedge_limit)
        generator = OrderGenerator(seed=args.seed)
        runner = SimulationRunner(engine=engine)

        orders = generator.generate_orders(count=100)
        summary = runner.run(orders=orders, verbose=args.verbose)

    # 2. Export trades, balances, and running PnL to CSV
    if args.export_csv:
        export_path = runner.export_csv(args.export_csv)
        summary["exported_csv_path"] = str(export_path)

    # 3. Print report to console
    runner.print_report(summary)

    # 4. If requested or as primary presentation, output CSV to console
    if args.print_csv:
        print("\n" + "=" * 72)
        print("          INDIVIDUAL TRADES, BALANCES & RUNNING PNL (CSV)")
        print("=" * 72)
        runner.print_csv(max_rows=args.csv_limit)
        print("=" * 72 + "\n")

    if "exported_csv_path" in summary:
        print(f"Full CSV results saved to: {summary['exported_csv_path']}")


if __name__ == "__main__":
    main()
