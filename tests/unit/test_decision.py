"""Unit tests for the decision engine."""

import pytest

from app.strategy.decision import DecisionEngine, DecisionInput


@pytest.fixture
def engine():
    return DecisionEngine()


def _base_input(**overrides) -> DecisionInput:
    defaults = dict(
        calibrated_posterior_up=0.65,
        market_implied_up=0.50,
        agreed_direction="up",
        macro_veto_active=False,
        freshness_ok=True,
        calibration_loaded=True,
        liquidity_ok=True,
        spread_ok=True,
        risk_ok=True,
        has_existing_position=False,
        min_edge_threshold=0.04,
    )
    defaults.update(overrides)
    return DecisionInput(**defaults)


class TestDecisionEngine:
    def test_all_gates_pass(self, engine):
        result = engine.evaluate(_base_input())
        assert result.should_trade
        assert result.direction == "up"
        assert result.edge > 0

    def test_signals_disagree_blocks(self, engine):
        result = engine.evaluate(_base_input(agreed_direction=None))
        assert not result.should_trade
        assert result.blocked_reason == "signals_disagree"

    def test_macro_veto_blocks(self, engine):
        result = engine.evaluate(_base_input(macro_veto_active=True))
        assert not result.should_trade
        assert result.blocked_reason == "macro_veto_active"

    def test_stale_data_blocks(self, engine):
        result = engine.evaluate(_base_input(freshness_ok=False))
        assert not result.should_trade
        assert result.blocked_reason == "stale_data"

    def test_no_calibration_blocks(self, engine):
        result = engine.evaluate(_base_input(calibration_loaded=False))
        assert not result.should_trade
        assert result.blocked_reason == "no_calibration_model"

    def test_insufficient_edge_blocks(self, engine):
        result = engine.evaluate(_base_input(
            calibrated_posterior_up=0.52,
            market_implied_up=0.50,
        ))
        assert not result.should_trade
        assert "insufficient_edge" in result.blocked_reason

    def test_poor_liquidity_blocks(self, engine):
        result = engine.evaluate(_base_input(liquidity_ok=False))
        assert not result.should_trade
        assert result.blocked_reason == "insufficient_liquidity"

    def test_spread_too_wide_blocks(self, engine):
        result = engine.evaluate(_base_input(spread_ok=False))
        assert not result.should_trade
        assert result.blocked_reason == "spread_too_wide"

    def test_risk_limit_blocks(self, engine):
        result = engine.evaluate(_base_input(risk_ok=False))
        assert not result.should_trade
        assert result.blocked_reason == "risk_limit_breach"

    def test_existing_position_blocks(self, engine):
        result = engine.evaluate(_base_input(has_existing_position=True))
        assert not result.should_trade
        assert result.blocked_reason == "existing_position"

    def test_down_direction(self, engine):
        result = engine.evaluate(_base_input(
            agreed_direction="down",
            calibrated_posterior_up=0.30,
            market_implied_up=0.50,
        ))
        assert result.should_trade
        assert result.direction == "down"
        assert result.edge > 0
