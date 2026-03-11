"""Decision engine: gates that must pass before a trade is allowed."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from app.utils.logging import get_logger

log = get_logger("decision")


@dataclass
class DecisionInput:
    calibrated_posterior_up: float
    market_implied_up: float
    agreed_direction: Optional[str]
    macro_veto_active: bool
    freshness_ok: bool
    calibration_loaded: bool
    liquidity_ok: bool
    spread_ok: bool
    risk_ok: bool
    has_existing_position: bool
    min_edge_threshold: float = 0.04


@dataclass
class DecisionOutput:
    should_trade: bool
    direction: Optional[str] = None
    edge: float = 0.0
    blocked_reason: Optional[str] = None


class DecisionEngine:
    """
    Evaluates all trade gates sequentially.
    A trade is only allowed if every gate passes.
    """

    def evaluate(self, inp: DecisionInput) -> DecisionOutput:
        # Gate 1: All signals must agree directionally
        if inp.agreed_direction is None:
            return self._block("signals_disagree")

        # Gate 2: Macro veto
        if inp.macro_veto_active:
            return self._block("macro_veto_active")

        # Gate 3: Data freshness
        if not inp.freshness_ok:
            return self._block("stale_data")

        # Gate 4: Calibration must be loaded
        if not inp.calibration_loaded:
            return self._block("no_calibration_model")

        # Gate 5: Edge check
        if inp.agreed_direction == "up":
            edge = inp.calibrated_posterior_up - inp.market_implied_up
        else:
            edge = (1 - inp.calibrated_posterior_up) - (1 - inp.market_implied_up)

        if abs(edge) < inp.min_edge_threshold:
            return self._block(f"insufficient_edge_{edge:.4f}")

        if edge < 0:
            return self._block(f"negative_edge_{edge:.4f}")

        # Gate 6: Liquidity
        if not inp.liquidity_ok:
            return self._block("insufficient_liquidity")

        # Gate 7: Spread
        if not inp.spread_ok:
            return self._block("spread_too_wide")

        # Gate 8: Risk limits
        if not inp.risk_ok:
            return self._block("risk_limit_breach")

        # Gate 9: Existing position
        if inp.has_existing_position:
            return self._block("existing_position")

        log.info(
            "trade_approved",
            direction=inp.agreed_direction,
            edge=round(edge, 4),
        )

        return DecisionOutput(
            should_trade=True,
            direction=inp.agreed_direction,
            edge=round(edge, 6),
        )

    @staticmethod
    def _block(reason: str) -> DecisionOutput:
        log.debug("trade_blocked", reason=reason)
        return DecisionOutput(should_trade=False, blocked_reason=reason)
