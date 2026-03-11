"""Calibration engine: isotonic regression on posterior probabilities."""

from __future__ import annotations

import json
import pickle
from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import brier_score_loss, log_loss

from app.utils.logging import get_logger

log = get_logger("calibration")


class CalibrationEngine:
    """
    Manages isotonic regression calibration of raw posterior probabilities.

    The calibrator maps raw_posterior -> calibrated_posterior using a monotone
    function fit on historical (prediction, outcome) pairs.
    """

    def __init__(self, artifact_dir: str = "data/artifacts"):
        self._artifact_dir = Path(artifact_dir)
        self._artifact_dir.mkdir(parents=True, exist_ok=True)
        self._model: Optional[IsotonicRegression] = None
        self._version: Optional[str] = None
        self._is_loaded = False

    @property
    def is_loaded(self) -> bool:
        return self._is_loaded

    @property
    def version(self) -> Optional[str]:
        return self._version

    def calibrate(self, raw_posterior: float) -> float:
        """Apply calibration to a raw posterior. Returns raw if no model loaded."""
        if not self._is_loaded or self._model is None:
            return raw_posterior
        arr = np.array([raw_posterior])
        calibrated = self._model.predict(arr)[0]
        return float(np.clip(calibrated, 0.01, 0.99))

    def train(
        self,
        predictions: np.ndarray,
        outcomes: np.ndarray,
        version: str | None = None,
        training_start: datetime | None = None,
        training_end: datetime | None = None,
    ) -> dict:
        """
        Train isotonic regression calibrator.
        predictions: array of raw posterior probabilities [0,1]
        outcomes: array of binary outcomes (1 = UP resolved)
        """
        assert len(predictions) == len(outcomes), "Length mismatch"
        assert len(predictions) >= 20, "Need at least 20 samples to train"

        model = IsotonicRegression(out_of_bounds="clip", y_min=0.01, y_max=0.99)
        model.fit(predictions, outcomes)

        calibrated = model.predict(predictions)
        brier = brier_score_loss(outcomes, calibrated)
        ll = log_loss(outcomes, np.clip(calibrated, 1e-6, 1 - 1e-6))

        if version is None:
            version = datetime.utcnow().strftime("cal_%Y%m%d_%H%M%S")

        artifact_path = self._artifact_dir / f"{version}.pkl"
        with open(artifact_path, "wb") as f:
            pickle.dump(model, f)

        meta = {
            "version": version,
            "artifact_path": str(artifact_path),
            "model_type": "isotonic",
            "training_start_utc": training_start.isoformat() if training_start else None,
            "training_end_utc": training_end.isoformat() if training_end else None,
            "validation_metric_brier": round(brier, 6),
            "validation_metric_logloss": round(ll, 6),
            "sample_count": len(predictions),
        }
        meta_path = self._artifact_dir / f"{version}_meta.json"
        with open(meta_path, "w") as f:
            json.dump(meta, f, indent=2)

        log.info("calibration_trained", version=version, brier=brier, logloss=ll)

        self._model = model
        self._version = version
        self._is_loaded = True
        return meta

    def load(self, artifact_path: str, version: str):
        """Load a previously-trained calibration artifact."""
        path = Path(artifact_path)
        if not path.exists():
            log.error("calibration_artifact_missing", path=str(path))
            return False
        with open(path, "rb") as f:
            self._model = pickle.load(f)
        self._version = version
        self._is_loaded = True
        log.info("calibration_loaded", version=version, path=str(path))
        return True

    def create_placeholder(self) -> dict:
        """Create an identity-mapped placeholder calibrator for paper mode bootstrap."""
        x = np.linspace(0.01, 0.99, 100)
        y = x.copy()  # identity
        return self.train(
            predictions=x,
            outcomes=(x > 0.5).astype(float),
            version="placeholder_v0",
        )

    @staticmethod
    def compute_calibration_curve(
        predictions: np.ndarray,
        outcomes: np.ndarray,
        n_bins: int = 10,
    ) -> list[dict]:
        """Compute calibration curve bins for reporting."""
        bins = np.linspace(0, 1, n_bins + 1)
        result = []
        for i in range(n_bins):
            mask = (predictions >= bins[i]) & (predictions < bins[i + 1])
            if mask.sum() == 0:
                continue
            result.append({
                "bin_start": round(bins[i], 2),
                "bin_end": round(bins[i + 1], 2),
                "mean_predicted": round(float(np.mean(predictions[mask])), 4),
                "mean_actual": round(float(np.mean(outcomes[mask])), 4),
                "count": int(mask.sum()),
            })
        return result
