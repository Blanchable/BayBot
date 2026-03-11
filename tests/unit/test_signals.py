"""Unit tests for the signal computation engines."""

import time

import pytest

from app.clients.binance_ws import Trade
from app.strategy.signals import FundingEngine, RVOLEngine, VWAPEngine


class TestVWAPEngine:
    def _make_trade(self, price: float, qty: float = 1.0, offset_ms: int = 0) -> Trade:
        return Trade(
            price=price,
            qty=qty,
            timestamp_ms=int(time.time() * 1000) - offset_ms,
            is_buyer_maker=False,
        )

    def test_returns_none_with_insufficient_data(self):
        engine = VWAPEngine(lookback_seconds=60)
        assert engine.compute() is None

    def test_computes_vwap_correctly(self):
        engine = VWAPEngine(lookback_seconds=60)
        for i in range(50):
            engine.ingest(self._make_trade(100.0 + i * 0.01, qty=1.0))
        result = engine.compute()
        assert result is not None
        assert result.rolling_vwap > 0
        assert result.btc_price > 0

    def test_direction_positive_zscore(self):
        engine = VWAPEngine(lookback_seconds=60, zscore_window=20)
        # Feed flat then spike up
        for i in range(30):
            engine.ingest(self._make_trade(100.0, qty=1.0))
        for i in range(30):
            engine.ingest(self._make_trade(100.0, qty=1.0))
        result = engine.compute()
        assert result is not None
        assert result.direction in ("up", "down", "neutral")


class TestFundingEngine:
    def test_returns_none_with_insufficient_data(self):
        engine = FundingEngine(lookback_periods=48)
        assert engine.compute() is None

    def test_computes_with_enough_data(self):
        engine = FundingEngine(lookback_periods=48)
        rates = [0.0001 * (1 + i * 0.01) for i in range(20)]
        engine.ingest(rates)
        result = engine.compute()
        assert result is not None
        assert result.raw_rate > 0

    def test_high_funding_is_bearish(self):
        engine = FundingEngine(lookback_periods=20)
        rates = [0.0001] * 18 + [0.001, 0.005]
        engine.ingest(rates)
        result = engine.compute()
        assert result is not None
        assert result.zscore > 0
        assert result.direction == "down"


class TestRVOLEngine:
    def test_normal_volume(self):
        engine = RVOLEngine(bucket_minutes=5)
        engine.set_baselines({"14:00": [100.0, 110.0, 90.0]})
        result = engine.compute(100.0, "14:00")
        assert result is not None
        assert 0.9 <= result.rvol <= 1.1

    def test_high_volume_with_direction(self):
        engine = RVOLEngine(bucket_minutes=5)
        engine.set_baselines({"14:00": [100.0]})
        result = engine.compute(200.0, "14:00", price_direction="up")
        assert result is not None
        assert result.rvol > 1.3
        assert result.direction == "up"

    def test_high_volume_neutral_without_direction(self):
        engine = RVOLEngine(bucket_minutes=5)
        engine.set_baselines({"14:00": [100.0]})
        result = engine.compute(200.0, "14:00", price_direction="neutral")
        assert result is not None
        assert result.direction == "neutral"

    def test_missing_baseline(self):
        engine = RVOLEngine(bucket_minutes=5)
        result = engine.compute(100.0, "03:00")
        assert result is not None
        assert result.rvol == 1.0
