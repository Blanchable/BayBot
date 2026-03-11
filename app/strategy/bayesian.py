"""Bayesian updater: converts signals into posterior probability via likelihood ratios."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.utils.logging import get_logger

log = get_logger("bayesian")

# Default likelihood ratio tables (signal z-score bucket -> LR for UP direction).
# LR > 1 means evidence for UP; LR < 1 means evidence for DOWN.
DEFAULT_LR_TABLE: dict[str, dict[str, float]] = {
    "vwap": {
        "strong_up":   2.0,
        "mild_up":     1.3,
        "neutral":     1.0,
        "mild_down":   0.77,
        "strong_down": 0.5,
    },
    "funding": {
        "strong_up":   1.8,
        "mild_up":     1.2,
        "neutral":     1.0,
        "mild_down":   0.83,
        "strong_down": 0.55,
    },
    "rvol": {
        "strong_up":   1.5,
        "mild_up":     1.15,
        "neutral":     1.0,
        "mild_down":   0.87,
        "strong_down": 0.67,
    },
}

ZSCORE_BUCKET_THRESHOLDS = [
    (-float("inf"), -1.5, "strong_down"),
    (-1.5, -0.3, "mild_down"),
    (-0.3, 0.3, "neutral"),
    (0.3, 1.5, "mild_up"),
    (1.5, float("inf"), "strong_up"),
]


def zscore_to_bucket(z: float) -> str:
    for lo, hi, label in ZSCORE_BUCKET_THRESHOLDS:
        if lo <= z < hi:
            return label
    return "neutral"


@dataclass
class BayesianResult:
    prior_up: float
    lr_vwap: float
    lr_funding: float
    lr_rvol: float
    raw_posterior_up: float
    posterior_odds: float


class BayesianUpdater:
    """
    Multiplies prior odds by per-signal likelihood ratios to derive posterior.
    """

    def __init__(self, lr_tables: dict[str, dict[str, float]] | None = None):
        self._lr_tables = lr_tables or DEFAULT_LR_TABLE

    def set_lr_tables(self, tables: dict[str, dict[str, float]]):
        self._lr_tables = tables

    def get_likelihood_ratio(self, signal_name: str, zscore: float) -> float:
        bucket = zscore_to_bucket(zscore)
        table = self._lr_tables.get(signal_name, {})
        return table.get(bucket, 1.0)

    def update(
        self,
        prior_up: float,
        vwap_zscore: float,
        funding_zscore: float,
        rvol_zscore: float,
    ) -> BayesianResult:
        """
        Bayes update:
            posterior_odds = prior_odds * LR_vwap * LR_funding * LR_rvol
            posterior_prob = posterior_odds / (1 + posterior_odds)
        """
        eps = 1e-8
        prior_up = max(eps, min(1 - eps, prior_up))
        prior_odds = prior_up / (1 - prior_up)

        lr_vwap = self.get_likelihood_ratio("vwap", vwap_zscore)
        lr_funding = self.get_likelihood_ratio("funding", funding_zscore)
        lr_rvol = self.get_likelihood_ratio("rvol", rvol_zscore)

        posterior_odds = prior_odds * lr_vwap * lr_funding * lr_rvol
        raw_posterior = posterior_odds / (1.0 + posterior_odds)

        log.debug(
            "bayes_update",
            prior=round(prior_up, 4),
            lr_v=round(lr_vwap, 3),
            lr_f=round(lr_funding, 3),
            lr_r=round(lr_rvol, 3),
            raw_post=round(raw_posterior, 4),
        )

        return BayesianResult(
            prior_up=prior_up,
            lr_vwap=lr_vwap,
            lr_funding=lr_funding,
            lr_rvol=lr_rvol,
            raw_posterior_up=raw_posterior,
            posterior_odds=posterior_odds,
        )


class PriorEstimator:
    """
    Provides time-of-day base rate for P(BTC up) over the contract horizon.
    Falls back to 0.50 if no learned prior is available.
    """

    def __init__(self):
        self._priors: dict[str, dict[str, float]] = {}

    def load(self, priors: dict[str, dict[str, float]]):
        """Load priors keyed by contract_horizon -> tod_bucket -> prior_up."""
        self._priors = priors

    def get_prior(self, contract_horizon: str, tod_bucket: str) -> float:
        horizon_priors = self._priors.get(contract_horizon, {})
        return horizon_priors.get(tod_bucket, 0.50)
