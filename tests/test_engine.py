"""Unit tests for Blunit FX Internalizer."""

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from blunit_fx.models import OrderSide, ClientOrder, TradeRecord
from blunit_fx.pricing import PricingModel
from blunit_fx.engine import NetterEngine, InternalizerEngine
from blunit_fx.simulator import OrderGenerator, SimulationRunner
from blunit_fx.data_loader import MarketCandle, load_market_data



class TestPricingModel(unittest.TestCase):
    def setUp(self):
        self.pricing = PricingModel(mid_rate=24.50, spread_pct=0.004)

    def test_bid_ask_calculation(self):
        self.assertAlmostEqual(self.pricing.bid_rate, 24.451, places=4)
        self.assertAlmostEqual(self.pricing.ask_rate, 24.549, places=4)

    def test_get_client_rate(self):
        self.assertEqual(
            self.pricing.get_client_rate(OrderSide.BUY),
            self.pricing.ask_rate,
        )
        self.assertEqual(
            self.pricing.get_client_rate(OrderSide.SELL),
            self.pricing.bid_rate,
        )

    def test_dynamic_mid_rate(self):
        # Dynamic rate 25.00
        rate = self.pricing.get_client_rate(OrderSide.BUY, mid_rate=25.00)
        # 25.00 * 1.002 = 25.050
        self.assertAlmostEqual(rate, 25.050, places=4)

    def test_spread_profit(self):
        volume = 1_000.0
        profit = self.pricing.calculate_spread_profit(volume)
        self.assertAlmostEqual(profit, 49.0, places=4)

    def test_inventory_skew(self):
        skew_pricing = PricingModel(
            mid_rate=25.00,
            spread_pct=0.004,
            skew_factor=0.0010,  # 10 bps max skew
            hedge_limit=10_000.0,
        )
        # Unskewed mid = 25.00
        # When NOP = +10_000 (long EUR), skewed mid = 25.00 * (1 - 0.0010) = 24.975
        skewed_mid_long = skew_pricing.get_skewed_mid(mid_rate=25.00, current_nop=10_000.0)
        self.assertAlmostEqual(skewed_mid_long, 24.975, places=4)

        # Client buy rate when long EUR should be cheaper (attractive for buyer)
        buy_rate = skew_pricing.get_client_rate(OrderSide.BUY, mid_rate=25.00, current_nop=10_000.0)
        self.assertAlmostEqual(buy_rate, 24.975 * 1.002, places=4)

        # When NOP = -10_000 (short EUR), skewed mid = 25.00 * (1 + 0.0010) = 25.025
        skewed_mid_short = skew_pricing.get_skewed_mid(mid_rate=25.00, current_nop=-10_000.0)
        self.assertAlmostEqual(skewed_mid_short, 25.025, places=4)


class TestInternalizerEngine(unittest.TestCase):
    def setUp(self):
        self.pricing = PricingModel(mid_rate=24.50, spread_pct=0.004)
        self.engine = InternalizerEngine(
            pricing_model=self.pricing,
            hedge_limit=10_000.0,
        )

    def test_single_client_buy(self):
        order = ClientOrder(
            order_id="ORD-001",
            timestamp=datetime(2026, 1, 1, 10, 0, 0, tzinfo=timezone.utc),
            side=OrderSide.BUY,
            volume_eur=1_000.0,
        )
        exec_rep, hedge = self.engine.process_order(order)

        self.assertIsNone(hedge)
        self.assertEqual(exec_rep.volume_eur, 1_000.0)
        self.assertAlmostEqual(exec_rep.client_rate, 24.549, places=4)
        self.assertAlmostEqual(self.engine.account.balance_eur, -1_000.0)
        self.assertAlmostEqual(self.engine.account.balance_czk, 24_549.0)
        self.assertAlmostEqual(self.engine.nop_eur, -1_000.0)
        self.assertAlmostEqual(self.engine.account.mtm_pnl_czk(24.50), 49.0, places=4)
        self.assertEqual(len(self.engine.trade_log), 1)

    def test_single_client_sell(self):
        order = ClientOrder(
            order_id="ORD-002",
            timestamp=datetime(2026, 1, 1, 10, 0, 0, tzinfo=timezone.utc),
            side=OrderSide.SELL,
            volume_eur=1_000.0,
        )
        exec_rep, hedge = self.engine.process_order(order)

        self.assertIsNone(hedge)
        self.assertAlmostEqual(self.engine.account.balance_eur, 1_000.0)
        self.assertAlmostEqual(self.engine.account.balance_czk, -24_451.0)
        self.assertAlmostEqual(self.engine.nop_eur, 1_000.0)
        self.assertAlmostEqual(self.engine.account.mtm_pnl_czk(24.50), 49.0, places=4)

    def test_auto_hedge_and_ledger(self):
        order = ClientOrder(
            order_id="ORD-BIG",
            timestamp=datetime(2026, 1, 1, 10, 0, 0, tzinfo=timezone.utc),
            side=OrderSide.BUY,
            volume_eur=12_000.0,
        )
        _, hedge = self.engine.process_order(order, current_market_rate=24.50)

        self.assertIsNotNone(hedge)
        self.assertEqual(hedge.side, OrderSide.BUY)
        self.assertAlmostEqual(self.engine.nop_eur, 0.0)

        # Ledger contains 2 entries: 1 CLIENT + 1 HEDGE
        self.assertEqual(len(self.engine.trade_log), 2)
        client_rec = self.engine.trade_log[0]
        hedge_rec = self.engine.trade_log[1]

        self.assertEqual(client_rec.event_type, "CLIENT")
        self.assertEqual(hedge_rec.event_type, "HEDGE")
        self.assertAlmostEqual(hedge_rec.nop_eur, 0.0)
        self.assertAlmostEqual(hedge_rec.running_pnl_czk, 588.0, places=4)

    def test_partial_auto_hedge(self):
        partial_engine = InternalizerEngine(
            pricing_model=self.pricing,
            hedge_limit=10_000.0,
            hedge_target_ratio=0.5,  # hedge down to 5 000 EUR
        )
        order = ClientOrder(
            order_id="ORD-PARTIAL",
            timestamp=datetime(2026, 1, 1, 10, 0, 0, tzinfo=timezone.utc),
            side=OrderSide.BUY,
            volume_eur=12_000.0,
        )
        _, hedge = partial_engine.process_order(order, current_market_rate=24.50)

        self.assertIsNotNone(hedge)
        self.assertEqual(hedge.side, OrderSide.BUY)
        # 12 000 EUR short -> hedged 7 000 EUR -> remaining NOP is -5 000 EUR (50% of limit)
        self.assertAlmostEqual(hedge.volume_eur, 7_000.0)
        self.assertAlmostEqual(partial_engine.nop_eur, -5_000.0)
        self.assertAlmostEqual(hedge.nop_after_eur, -5_000.0)

    def test_opportunistic_hedge(self):
        engine = InternalizerEngine(
            pricing_model=self.pricing,
            hedge_limit=10_000.0,
            hedge_target_ratio=0.5,
            enable_opportunistic_hedge=True,
            opportunistic_threshold=5_000.0,
            timing_window=5,
            timing_k=0.5,
        )
        # Establish rate history around 24.50
        for i in range(5):
            order = ClientOrder(
                order_id=f"ORD-PRE-{i}",
                timestamp=datetime(2026, 1, 1, 10, i, 0, tzinfo=timezone.utc),
                side=OrderSide.SELL,
                volume_eur=1_000.0,
            )
            engine.process_order(order, current_market_rate=24.50)

        # Current NOP is +5_000 EUR (at opportunistic threshold)
        self.assertAlmostEqual(engine.nop_eur, 5_000.0)
        self.assertEqual(len(engine.hedges), 0)

        # Client sells EUR 1 000 at a higher market rate (24.70), creating a peak
        spike_order = ClientOrder(
            order_id="ORD-SPIKE",
            timestamp=datetime(2026, 1, 1, 10, 10, 0, tzinfo=timezone.utc),
            side=OrderSide.SELL,
            volume_eur=1_000.0,
        )
        _, hedge = engine.process_order(spike_order, current_market_rate=24.70)

        # Opportunistic hedge should trigger because NOP >= 5_000 and rate is elevated!
        self.assertIsNotNone(hedge)
        self.assertEqual(hedge.hedge_type, "OPPORTUNISTIC")
        self.assertEqual(hedge.side, OrderSide.SELL)
        # Hard limit (10_000) was never breached
        self.assertLess(6_000.0, engine.hedge_limit)

    def test_csv_export(self):
        order = ClientOrder(
            order_id="ORD-CSV",
            timestamp=datetime(2026, 1, 1, 10, 0, 0, tzinfo=timezone.utc),
            side=OrderSide.BUY,
            volume_eur=2_000.0,
        )
        self.engine.process_order(order)

        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp:
            tmp_path = Path(tmp.name)

        try:
            exported = self.engine.export_csv(tmp_path)
            self.assertTrue(exported.exists())
            content = exported.read_text(encoding="utf-8")
            self.assertIn("trade_id,timestamp,event_type", content)
            self.assertIn("ORD-CSV", content)
            self.assertIn("CLIENT", content)
            self.assertIn("running_pnl_czk", content)
        finally:
            if tmp_path.exists():
                tmp_path.unlink()


class TestDataLoader(unittest.TestCase):
    def test_load_real_data(self):
        csv_path = Path("fxdata/eurczk-h4-bid-2017-01-02-2026-10-15.csv")
        if not csv_path.exists():
            self.skipTest("Historical data file not present")

        start = datetime(2023, 1, 1, tzinfo=timezone.utc)
        end = datetime(2023, 1, 31, tzinfo=timezone.utc)
        candles = load_market_data(csv_path, start_date=start, end_date=end)

        self.assertGreater(len(candles), 0)
        for c in candles:
            self.assertGreaterEqual(c.timestamp, start)
            self.assertLessEqual(c.timestamp, end)
            self.assertGreater(c.close, 20.0)
            self.assertLess(c.close, 30.0)


class TestSimulator(unittest.TestCase):
    def test_historical_simulation(self):
        candles = [
            MarketCandle(
                timestamp=datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc),
                open=24.50, high=24.55, low=24.48, close=24.52,
            ),
            MarketCandle(
                timestamp=datetime(2026, 1, 1, 4, 0, tzinfo=timezone.utc),
                open=24.52, high=24.60, low=24.50, close=24.58,
            ),
        ]
        engine = InternalizerEngine(hedge_limit=5_000.0)
        runner = SimulationRunner(engine=engine)
        summary = runner.run_historical(candles, orders_per_candle=2, seed=42)

        self.assertEqual(summary["total_orders"], 4)
        self.assertIn("total_records", summary)
        self.assertGreater(summary["total_records"], 0)


if __name__ == "__main__":
    unittest.main()
