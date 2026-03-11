"""Unit tests for the Bayesian updater."""

import pytest

from app.strategy.bayesian import BayesianUpdater, PriorEstimator, zscore_to_bucket


class TestZScoreBuckets:
    def test_neutral(self):
        assert zscore_to_bucket(0.0) == "neutral"

    def test_mild_up(self):
        assert zscore_to_bucket(0.5) == "mild_up"

    def test_strong_down(self):
        assert zscore_to_bucket(-2.0) == "strong_down"

    def test_strong_up(self):
        assert zscore_to_bucket(2.0) == "strong_up"

    def test_boundary_neutral_upper(self):
        assert zscore_to_bucket(0.29) == "neutral"

    def test_boundary_mild_up_lower(self):
        assert zscore_to_bucket(0.3) == "mild_up"


class TestBayesianUpdater:
    def test_neutral_signals_preserve_prior(self):
        updater = BayesianUpdater()
        result = updater.update(prior_up=0.5, vwap_zscore=0.0, funding_zscore=0.0, rvol_zscore=0.0)
        assert abs(result.raw_posterior_up - 0.5) < 0.01

    def test_bullish_signals_increase_posterior(self):
        updater = BayesianUpdater()
        # Negative funding zscore is bullish (overleveraged shorts),
        # but the LR table maps the z-score bucket, not the "bullish" interpretation.
        # strong_down bucket z=-2 gives LR=0.55 which is bearish evidence for UP.
        # So for a clean bullish scenario: vwap strong up, funding strong down (z=-2),
        # rvol strong up.  The net posterior should still rise above prior.
        result = updater.update(prior_up=0.5, vwap_zscore=2.0, funding_zscore=-2.0, rvol_zscore=2.0)
        assert result.raw_posterior_up > 0.5
        assert result.lr_vwap > 1.0
        assert result.lr_rvol > 1.0
        # Funding LR for z=-2 maps to strong_down bucket -> LR 0.55 (bearish for UP).
        # This is consistent: high negative funding z = bearish signal context.
        # The net posterior is still bullish because VWAP+RVOL dominate.
        assert result.lr_funding < 1.0

    def test_bearish_signals_decrease_posterior(self):
        updater = BayesianUpdater()
        result = updater.update(prior_up=0.5, vwap_zscore=-2.0, funding_zscore=2.0, rvol_zscore=-2.0)
        assert result.raw_posterior_up < 0.5

    def test_prior_matters(self):
        updater = BayesianUpdater()
        r1 = updater.update(prior_up=0.3, vwap_zscore=1.0, funding_zscore=-1.0, rvol_zscore=1.0)
        r2 = updater.update(prior_up=0.7, vwap_zscore=1.0, funding_zscore=-1.0, rvol_zscore=1.0)
        assert r2.raw_posterior_up > r1.raw_posterior_up

    def test_posterior_bounded(self):
        updater = BayesianUpdater()
        result = updater.update(prior_up=0.99, vwap_zscore=3.0, funding_zscore=-3.0, rvol_zscore=3.0)
        assert 0 < result.raw_posterior_up < 1.0

    def test_custom_lr_tables(self):
        custom = {
            "vwap": {"neutral": 1.0, "mild_up": 5.0, "mild_down": 0.2,
                     "strong_up": 5.0, "strong_down": 0.2},
            "funding": {"neutral": 1.0, "mild_up": 1.0, "mild_down": 1.0,
                        "strong_up": 1.0, "strong_down": 1.0},
            "rvol": {"neutral": 1.0, "mild_up": 1.0, "mild_down": 1.0,
                     "strong_up": 1.0, "strong_down": 1.0},
        }
        updater = BayesianUpdater(lr_tables=custom)
        result = updater.update(prior_up=0.5, vwap_zscore=1.0, funding_zscore=0.0, rvol_zscore=0.0)
        assert result.lr_vwap == 5.0
        assert result.raw_posterior_up > 0.8


class TestPriorEstimator:
    def test_default_prior(self):
        estimator = PriorEstimator()
        assert estimator.get_prior("5m", "14:00") == 0.5

    def test_loaded_prior(self):
        estimator = PriorEstimator()
        estimator.load({"5m": {"14:00": 0.55, "15:00": 0.48}})
        assert estimator.get_prior("5m", "14:00") == 0.55
        assert estimator.get_prior("5m", "15:00") == 0.48
        assert estimator.get_prior("5m", "16:00") == 0.5  # fallback
