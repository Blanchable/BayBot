"""Unit tests for the calibration engine."""

import numpy as np
import pytest

from app.strategy.calibration import CalibrationEngine


@pytest.fixture
def engine(tmp_path):
    return CalibrationEngine(artifact_dir=str(tmp_path))


class TestCalibrationEngine:
    def test_uncalibrated_passthrough(self, engine):
        assert engine.calibrate(0.7) == 0.7
        assert not engine.is_loaded

    def test_train_and_calibrate(self, engine):
        np.random.seed(42)
        n = 200
        probs = np.random.uniform(0.1, 0.9, n)
        outcomes = (np.random.uniform(size=n) < probs).astype(float)

        meta = engine.train(probs, outcomes, version="test_v1")
        assert engine.is_loaded
        assert meta["version"] == "test_v1"
        assert meta["validation_metric_brier"] < 0.3
        assert "artifact_path" in meta

        calibrated = engine.calibrate(0.5)
        assert 0.01 <= calibrated <= 0.99

    def test_train_rejects_small_sample(self, engine):
        with pytest.raises(AssertionError):
            engine.train(np.array([0.5] * 10), np.array([1.0] * 10))

    def test_placeholder_creation(self, engine):
        meta = engine.create_placeholder()
        assert engine.is_loaded
        assert "placeholder" in meta["version"]

    def test_load_artifact(self, engine):
        meta = engine.create_placeholder()
        path = meta["artifact_path"]
        version = meta["version"]

        engine2 = CalibrationEngine(artifact_dir=str(engine._artifact_dir))
        assert engine2.load(path, version)
        assert engine2.is_loaded
        assert engine2.version == version

    def test_calibration_curve(self):
        predictions = np.array([0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9])
        outcomes = np.array([0, 0, 0, 1, 0, 1, 1, 1, 1])
        curve = CalibrationEngine.compute_calibration_curve(predictions, outcomes, n_bins=3)
        assert len(curve) > 0
        assert all("mean_predicted" in b for b in curve)
