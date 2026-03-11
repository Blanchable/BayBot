"""Signal computation engines: VWAP, Funding Rate, RVOL."""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from app.clients.binance_ws import Trade
from app.utils.logging import get_logger

log = get_logger("signals")


@dataclass
class VWAPResult:
    rolling_vwap: float
    btc_price: float
    deviation: float
    zscore: float
    direction: str  # "up" | "down" | "neutral"
    lookback_s: int
    sample_count: int


@dataclass
class FundingResult:
    raw_rate: float
    rolling_mean: float
    rolling_std: float
    zscore: float
    direction: str


@dataclass
class RVOLResult:
    current_volume: float
    expected_volume: float
    rvol: float
    direction: str


class VWAPEngine:
    """Rolling VWAP computation from websocket trade stream."""

    def __init__(self, lookback_seconds: int = 60, zscore_window: int = 100):
        self._lookback_s = lookback_seconds
        self._zscore_window = zscore_window
        self._trades: deque[Trade] = deque(maxlen=100_000)
        self._deviation_history: deque[float] = deque(maxlen=zscore_window)

    def ingest(self, trade: Trade):
        self._trades.append(trade)

    def compute(self) -> Optional[VWAPResult]:
        now_ms = int(time.time() * 1000)
        cutoff = now_ms - self._lookback_s * 1000

        prices, qtys = [], []
        for t in reversed(self._trades):
            if t.timestamp_ms < cutoff:
                break
            prices.append(t.price)
            qtys.append(t.qty)

        if len(prices) < 5:
            return None

        p_arr = np.array(prices)
        q_arr = np.array(qtys)
        vwap = np.sum(p_arr * q_arr) / np.sum(q_arr)
        latest_price = prices[0]
        deviation = (latest_price - vwap) / vwap

        self._deviation_history.append(deviation)

        if len(self._deviation_history) < 10:
            zscore = 0.0
        else:
            dev_arr = np.array(self._deviation_history)
            mu = np.mean(dev_arr)
            sigma = np.std(dev_arr)
            zscore = (deviation - mu) / sigma if sigma > 1e-10 else 0.0

        direction = "up" if zscore > 0.3 else ("down" if zscore < -0.3 else "neutral")

        return VWAPResult(
            rolling_vwap=round(vwap, 2),
            btc_price=round(latest_price, 2),
            deviation=round(deviation, 8),
            zscore=round(zscore, 4),
            direction=direction,
            lookback_s=self._lookback_s,
            sample_count=len(prices),
        )


class FundingEngine:
    """Normalized funding rate signal from Binance funding history."""

    def __init__(self, lookback_periods: int = 48):
        self._lookback = lookback_periods
        self._history: deque[float] = deque(maxlen=lookback_periods * 2)

    def ingest(self, funding_rates: list[float]):
        for r in funding_rates:
            self._history.append(r)

    def compute(self, current_rate: float | None = None) -> Optional[FundingResult]:
        if current_rate is not None:
            self._history.append(current_rate)

        if len(self._history) < 8:
            return None

        arr = np.array(list(self._history)[-self._lookback:])
        rate = arr[-1]
        mu = np.mean(arr)
        sigma = np.std(arr)
        zscore = (rate - mu) / sigma if sigma > 1e-10 else 0.0

        # High positive funding = market overleveraged long = bearish signal
        direction = "down" if zscore > 0.5 else ("up" if zscore < -0.5 else "neutral")

        return FundingResult(
            raw_rate=round(float(rate), 8),
            rolling_mean=round(float(mu), 8),
            rolling_std=round(float(sigma), 8),
            zscore=round(float(zscore), 4),
            direction=direction,
        )


class RVOLEngine:
    """Relative volume engine: current volume vs. time-of-day baseline."""

    def __init__(self, bucket_minutes: int = 5):
        self._bucket_min = bucket_minutes
        # tod_bucket -> list of historical volumes
        self._baselines: dict[str, list[float]] = {}

    def set_baselines(self, baselines: dict[str, list[float]]):
        self._baselines = baselines

    def ingest_baseline(self, tod_bucket: str, volume: float):
        self._baselines.setdefault(tod_bucket, []).append(volume)

    def compute(
        self,
        current_volume: float,
        tod_bucket: str,
        price_direction: str = "neutral",
    ) -> Optional[RVOLResult]:
        hist = self._baselines.get(tod_bucket, [])
        if not hist:
            expected = current_volume  # fallback: assume normal
        else:
            expected = float(np.mean(hist))

        rvol = current_volume / expected if expected > 0 else 1.0

        # RVOL is directional only when paired with price direction
        if rvol > 1.3 and price_direction != "neutral":
            direction = price_direction
        else:
            direction = "neutral"

        return RVOLResult(
            current_volume=round(current_volume, 4),
            expected_volume=round(expected, 4),
            rvol=round(rvol, 4),
            direction=direction,
        )


@dataclass
class FeatureBundle:
    """All signal outputs bundled for downstream consumption."""
    vwap: Optional[VWAPResult] = None
    funding: Optional[FundingResult] = None
    rvol: Optional[RVOLResult] = None
    timestamp: float = field(default_factory=time.time)

    @property
    def all_valid(self) -> bool:
        return all(s is not None for s in [self.vwap, self.funding, self.rvol])

    @property
    def agreed_direction(self) -> Optional[str]:
        """Return direction if all three signals agree, else None."""
        if not self.all_valid:
            return None
        dirs = {self.vwap.direction, self.funding.direction, self.rvol.direction}
        if dirs == {"up"}:
            return "up"
        if dirs == {"down"}:
            return "down"
        return None

    @property
    def freshness_ok(self) -> bool:
        return (time.time() - self.timestamp) < 10.0
