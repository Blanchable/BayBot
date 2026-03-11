"""Risk manager and position sizer (half-Kelly)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.config.settings import AppSettings
from app.utils.logging import get_logger

log = get_logger("risk")


@dataclass
class SizingResult:
    raw_kelly: float
    half_kelly: float
    clamped_fraction: float
    position_size: float
    notional: float
    skip_reason: Optional[str] = None


class RiskManager:
    """
    Manages position sizing (half-Kelly), bankroll caps, and circuit breakers.
    """

    def __init__(self, settings: AppSettings):
        self._s = settings
        self._daily_pnl: float = 0.0
        self._losing_streak: int = 0
        self._open_exposure: float = 0.0
        self._open_market_count: int = 0
        self._emergency_stop: bool = False
        self._cooldown_until: float = 0.0

    @property
    def emergency_stop(self) -> bool:
        return self._emergency_stop

    def set_emergency_stop(self, active: bool):
        self._emergency_stop = active
        if active:
            log.warning("emergency_stop_activated")

    def update_state(
        self,
        daily_pnl: float,
        losing_streak: int,
        open_exposure: float,
        open_market_count: int,
    ):
        self._daily_pnl = daily_pnl
        self._losing_streak = losing_streak
        self._open_exposure = open_exposure
        self._open_market_count = open_market_count

    def check_risk_ok(self) -> tuple[bool, Optional[str]]:
        """Return (is_ok, reason_if_not)."""
        if self._emergency_stop:
            return False, "emergency_stop"

        import time
        if time.time() < self._cooldown_until:
            return False, "cooldown_active"

        if self._daily_pnl <= -self._s.max_daily_loss:
            return False, "daily_loss_limit"

        if self._losing_streak >= self._s.max_losing_streak:
            self._cooldown_until = time.time() + self._s.cooldown_after_losses_seconds
            return False, "losing_streak_limit"

        if self._open_exposure >= self._s.max_open_exposure:
            return False, "max_open_exposure"

        if self._open_market_count >= self._s.max_concurrent_markets:
            return False, "max_concurrent_markets"

        return True, None

    def compute_size(
        self,
        calibrated_prob: float,
        market_price: float,
        bankroll: float,
        fee_rate: float | None = None,
    ) -> SizingResult:
        """
        Half-Kelly sizing:
            kelly_fraction = p - (1-p)/b
        where p = calibrated_prob, b = payout odds = (1/market_price) - 1
        """
        fee = fee_rate or self._s.fee_rate
        if market_price <= 0 or market_price >= 1:
            return SizingResult(0, 0, 0, 0, 0, skip_reason="invalid_market_price")

        b = (1.0 / market_price) - 1.0
        if b <= 0:
            return SizingResult(0, 0, 0, 0, 0, skip_reason="non_positive_odds")

        # Adjust prob for fees
        p = calibrated_prob - fee
        if p <= 0:
            return SizingResult(0, 0, 0, 0, 0, skip_reason="prob_below_fee")

        raw_kelly = p - (1 - p) / b
        if raw_kelly <= 0:
            return SizingResult(raw_kelly, 0, 0, 0, 0, skip_reason="negative_kelly")

        half_kelly = raw_kelly * self._s.kelly_fraction

        clamped = min(half_kelly, self._s.max_fraction_per_trade)

        remaining_capacity = max(0, self._s.max_open_exposure - self._open_exposure)
        notional = min(bankroll * clamped, remaining_capacity)

        position_size = notional / market_price if market_price > 0 else 0

        if notional < self._s.min_order_size:
            return SizingResult(
                raw_kelly, half_kelly, clamped, 0, 0,
                skip_reason="below_min_order_size",
            )

        log.info(
            "position_sized",
            raw_kelly=round(raw_kelly, 4),
            half_kelly=round(half_kelly, 4),
            clamped=round(clamped, 4),
            notional=round(notional, 2),
        )

        return SizingResult(
            raw_kelly=round(raw_kelly, 6),
            half_kelly=round(half_kelly, 6),
            clamped_fraction=round(clamped, 6),
            position_size=round(position_size, 4),
            notional=round(notional, 4),
        )
