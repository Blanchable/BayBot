"""Unit tests for risk manager and position sizing."""

import pytest

from app.config.settings import AppSettings
from app.strategy.risk import RiskManager


@pytest.fixture
def settings():
    return AppSettings(
        initial_bankroll=1000.0,
        max_fraction_per_trade=0.05,
        max_daily_loss=100.0,
        max_open_exposure=300.0,
        max_concurrent_markets=4,
        min_order_size=1.0,
        kelly_fraction=0.5,
        fee_rate=0.002,
        max_losing_streak=5,
    )


@pytest.fixture
def risk(settings):
    return RiskManager(settings)


class TestRiskManager:
    def test_initial_risk_ok(self, risk):
        ok, reason = risk.check_risk_ok()
        assert ok
        assert reason is None

    def test_daily_loss_limit(self, risk):
        risk.update_state(daily_pnl=-100.0, losing_streak=0, open_exposure=0, open_market_count=0)
        ok, reason = risk.check_risk_ok()
        assert not ok
        assert reason == "daily_loss_limit"

    def test_max_exposure(self, risk):
        risk.update_state(daily_pnl=0, losing_streak=0, open_exposure=300.0, open_market_count=1)
        ok, reason = risk.check_risk_ok()
        assert not ok
        assert reason == "max_open_exposure"

    def test_max_concurrent(self, risk):
        risk.update_state(daily_pnl=0, losing_streak=0, open_exposure=50, open_market_count=4)
        ok, reason = risk.check_risk_ok()
        assert not ok
        assert reason == "max_concurrent_markets"

    def test_emergency_stop(self, risk):
        risk.set_emergency_stop(True)
        ok, reason = risk.check_risk_ok()
        assert not ok
        assert reason == "emergency_stop"


class TestPositionSizing:
    def test_basic_sizing(self, risk):
        result = risk.compute_size(
            calibrated_prob=0.65,
            market_price=0.50,
            bankroll=1000.0,
        )
        assert result.position_size > 0
        assert result.notional > 0
        assert result.half_kelly > 0
        assert result.raw_kelly > result.half_kelly

    def test_small_edge_produces_small_size(self, risk):
        result = risk.compute_size(
            calibrated_prob=0.505,
            market_price=0.50,
            bankroll=1000.0,
        )
        # Very small edge -> very small Kelly fraction -> small position
        assert result.notional < 10.0

    def test_invalid_market_price(self, risk):
        result = risk.compute_size(
            calibrated_prob=0.7,
            market_price=0.0,
            bankroll=1000.0,
        )
        assert result.skip_reason == "invalid_market_price"

    def test_max_fraction_clamp(self, risk):
        result = risk.compute_size(
            calibrated_prob=0.95,
            market_price=0.10,
            bankroll=10000.0,
        )
        assert result.clamped_fraction <= 0.05

    def test_below_min_order_size(self, risk):
        result = risk.compute_size(
            calibrated_prob=0.52,
            market_price=0.50,
            bankroll=5.0,
        )
        assert result.skip_reason is not None
