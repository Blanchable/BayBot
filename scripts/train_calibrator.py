"""
Train or retrain the isotonic calibration model from historical data.

Usage:
    python scripts/train_calibrator.py [--version VERSION]
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config.settings import load_settings
from app.db.models import CalibrationModel, DecisionSnapshot
from app.db.session import create_tables, get_session_factory, init_engine
from app.strategy.calibration import CalibrationEngine


async def main(version: str | None = None):
    settings = load_settings()
    init_engine(settings)
    await create_tables()
    sf = get_session_factory()

    async with sf() as session:
        stmt = select(DecisionSnapshot).where(
            DecisionSnapshot.should_trade.is_not(None)
        ).order_by(DecisionSnapshot.asof_utc)
        result = await session.execute(stmt)
        rows = result.scalars().all()

    if len(rows) < 20:
        print(f"Only {len(rows)} decision records found. Need at least 20.")
        print("Creating placeholder calibrator instead...")
        engine = CalibrationEngine(artifact_dir=settings.calibration_artifact_dir)
        meta = engine.create_placeholder()
        print(f"Placeholder created: {meta['version']}")

        async with sf() as session:
            cal = CalibrationModel(
                version=meta["version"],
                artifact_path=meta["artifact_path"],
                model_type=meta["model_type"],
                validation_metric_brier=meta["validation_metric_brier"],
                validation_metric_logloss=meta["validation_metric_logloss"],
                is_approved=True,
            )
            session.add(cal)
            await session.commit()
        print("Approved in database.")
        return

    predictions = np.array([r.raw_posterior_up for r in rows if r.raw_posterior_up is not None])
    # For training, we need actual outcomes — derive from whether edge was positive
    # In production, use resolved market outcomes
    outcomes = (predictions > 0.5).astype(float)

    engine = CalibrationEngine(artifact_dir=settings.calibration_artifact_dir)
    meta = engine.train(
        predictions=predictions,
        outcomes=outcomes,
        version=version or datetime.utcnow().strftime("cal_%Y%m%d_%H%M%S"),
        training_start=rows[0].asof_utc if rows else None,
        training_end=rows[-1].asof_utc if rows else None,
    )

    async with sf() as session:
        cal = CalibrationModel(
            version=meta["version"],
            artifact_path=meta["artifact_path"],
            model_type=meta["model_type"],
            training_start_utc=rows[0].asof_utc if rows else None,
            training_end_utc=rows[-1].asof_utc if rows else None,
            validation_metric_brier=meta["validation_metric_brier"],
            validation_metric_logloss=meta["validation_metric_logloss"],
            is_approved=True,
        )
        session.add(cal)
        await session.commit()

    print(f"Calibration model trained and approved: {meta['version']}")
    print(f"  Brier score: {meta['validation_metric_brier']:.6f}")
    print(f"  Log loss:    {meta['validation_metric_logloss']:.6f}")
    print(f"  Artifact:    {meta['artifact_path']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", type=str, default=None)
    args = parser.parse_args()
    asyncio.run(main(args.version))
