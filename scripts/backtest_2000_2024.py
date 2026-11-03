"""
Run comprehensive annual backtests from 2000 to 2024 following the 2025 institutional pattern.
Generates full annual statistics, comparison metrics, and CSV summary.
"""

import csv
import sys
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from blunit_fx.pricing import PricingModel
from blunit_fx.engine import NetterEngine
from blunit_fx.simulator import SimulationRunner
from blunit_fx.data_loader import load_market_data

DATA_FILE = Path("fxdata/eurczk-h4-bid-2000-01-03-2026-10-15.csv")
OUT_CSV = Path("fxdata/annual_backtests_2000_2024.csv")


def run_all_years():
    annual_results = []
    
    print("=" * 80)
    print("      BLUNIT FX NETTER - 25-YEAR HISTORICAL BACKTEST (2000 - 2024)")
    print("=" * 80)
    print("Configuration: Limit 25k EUR | 50% Buffer | 5 bps Skew | Opportunistic Timing")
    print("-" * 80)

    for year in range(2000, 2025):
        start_dt = datetime(year, 1, 1, tzinfo=timezone.utc)
        end_dt = datetime(year, 12, 31, 23, 59, 59, tzinfo=timezone.utc)

        candles = load_market_data(
            filepath=DATA_FILE,
            start_date=start_dt,
            end_date=end_dt,
        )

        if not candles:
            print(f"Warning: No candles found for year {year}")
            continue

        start_rate = candles[0].mid_price
        end_rate = candles[-1].mid_price
        min_rate = min(c.mid_price for c in candles)
        max_rate = max(c.mid_price for c in candles)
        rate_change_pct = ((end_rate - start_rate) / start_rate) * 100.0

        pricing = PricingModel(
            mid_rate=start_rate,
            spread_pct=0.004,
            skew_factor=0.0005,
            hedge_limit=25000.0,
        )

        engine = NetterEngine(
            pricing_model=pricing,
            hedge_limit=25000.0,
            hedge_target_ratio=0.5,
            enable_opportunistic_hedge=True,
            opportunistic_threshold=17500.0,
            timing_window=20,
            timing_k=0.75,
        )

        runner = SimulationRunner(engine=engine)
        summary = runner.run_historical(
            candles=candles,
            orders_per_candle=1,
            seed=42,
            verbose=False,
        )

        records = engine.trade_log
        max_nop = max(abs(r.nop_eur) for r in records) if records else 0.0
        var99_czk = max_nop * end_rate * 2.326 * 0.002165

        row = {
            "year": year,
            "candles": len(candles),
            "start_rate": round(start_rate, 4),
            "end_rate": round(end_rate, 4),
            "rate_change_pct": round(rate_change_pct, 2),
            "min_rate": round(min_rate, 4),
            "max_rate": round(max_rate, 4),
            "client_volume_eur": round(summary["total_volume_eur"], 2),
            "client_volume_czk": round(summary["total_volume_czk"], 2),
            "orders_count": summary["total_orders"],
            "internalization_rate_pct": round(summary["netting_rate_pct"], 2),
            "hedged_volume_eur": round(summary["total_hedged_eur"], 2),
            "total_hedges": summary["hedge_count"],
            "opportunistic_hedges": summary.get("opportunistic_hedge_count", 0),
            "hard_hedges": summary.get("hard_hedge_count", summary["hedge_count"]),
            "accumulated_spread_czk": round(summary["accumulated_spread_czk"], 2),
            "mtm_pnl_czk": round(summary["total_pnl_czk"], 2),
            "mtm_pnl_eur": round(summary["total_pnl_eur"], 2),
            "max_nop_eur": round(max_nop, 2),
            "var99_czk": round(var99_czk, 2),
        }
        annual_results.append(row)

        print(
            f"Year {year:4d} | Candles: {len(candles):4d} | Rate: {start_rate:.2f} -> {end_rate:.2f} ({rate_change_pct:+5.1f}%) | "
            f"Netting: {row['internalization_rate_pct']:5.2f}% | Hedges: {row['total_hedges']:2d} (Opp: {row['opportunistic_hedges']:2d}, Hard: {row['hard_hedges']:2d}) | "
            f"PnL: {int(row['mtm_pnl_czk']):+9,d} CZK (~{int(row['mtm_pnl_eur']):+6,d} EUR)"
        )

    # Save to CSV
    df = pd.DataFrame(annual_results)
    df.to_csv(OUT_CSV, index=False)
    print("-" * 80)
    print(f"Full annual CSV exported to: {OUT_CSV}")

    # Summary Statistics
    total_vol_eur = df["client_volume_eur"].sum()
    total_vol_czk = df["client_volume_czk"].sum()
    total_pnl_czk = df["mtm_pnl_czk"].sum()
    total_pnl_eur = df["mtm_pnl_eur"].sum()
    total_spread_czk = df["accumulated_spread_czk"].sum()
    avg_internalization = df["internalization_rate_pct"].mean()
    total_orders = df["orders_count"].sum()
    total_hedges = df["total_hedges"].sum()
    total_opp = df["opportunistic_hedges"].sum()
    total_hard = df["hard_hedges"].sum()

    print("\n" + "=" * 80)
    print("                     25-YEAR AGGREGATE SUMMARY (2000 - 2024)")
    print("=" * 80)
    print(f"Total Client Turnover:          {total_vol_eur / 1e6:,.2f} mil. EUR ({total_vol_czk / 1e6:,.2f} mil. CZK)")
    print(f"Total Client Orders:            {total_orders:,} orders across 25 years (~{total_orders / 25:,.0f} / year)")
    print(f"Average Internalization Rate:   {avg_internalization:.2f}% (min: {df['internalization_rate_pct'].min():.2f}%, max: {df['internalization_rate_pct'].max():.2f}%)")
    print(f"Total External Hedges:          {total_hedges:,} (Opportunistic: {total_opp:,} = {total_opp/total_hedges*100:.1f}%, Hard: {total_hard:,})")
    print(f"Cumulative Gross Spread:        {total_spread_czk:,.0f} CZK")
    print(f"Cumulative Clean MtM PnL:       {total_pnl_czk:+,.0f} CZK (~ {total_pnl_eur:+,.0f} EUR)")
    print(f"Average Annual Clean PnL:       {df['mtm_pnl_czk'].mean():+,.0f} CZK / year (~ {df['mtm_pnl_eur'].mean():+,.0f} EUR / year)")
    print(f"Profitable Years Ratio:         {(df['mtm_pnl_czk'] > 0).sum()} / {len(df)} years ({(df['mtm_pnl_czk'] > 0).mean() * 100:.1f}%)")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    run_all_years()
