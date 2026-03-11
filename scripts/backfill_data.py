"""
Backfill historical data for calibration training.

Fetches historical klines and funding from Binance, generates features,
and stores them for downstream calibration and analysis.

Usage:
    python scripts/backfill_data.py [--days 7]
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.clients.binance_rest import BinanceRestClient
from app.config.settings import load_settings
from app.db.models import FeatureSnapshot, MarketCatalog
from app.db.session import create_tables, get_session_factory, init_engine


async def main(days: int = 7):
    settings = load_settings()
    init_engine(settings)
    await create_tables()

    client = BinanceRestClient(base_url=settings.binance_futures_rest)
    sf = get_session_factory()

    print(f"Backfilling {days} days of data...")

    # Fetch 5m klines
    klines = await client.get_klines(symbol="BTCUSDT", interval="5m", limit=min(days * 288, 1500))
    print(f"  Fetched {len(klines)} klines")

    # Fetch funding history
    funding = await client.get_funding_rate(symbol="BTCUSDT", limit=min(days * 3, 100))
    print(f"  Fetched {len(funding)} funding rate records")

    # Generate synthetic features for each kline
    async with sf() as session:
        for kl in klines:
            ts = datetime.fromtimestamp(kl[0] / 1000, tz=timezone.utc)
            close = float(kl[4])
            volume = float(kl[5])
            high = float(kl[2])
            low = float(kl[3])
            vwap_approx = (high + low + close) / 3
            deviation = (close - vwap_approx) / vwap_approx if vwap_approx > 0 else 0

            fs = FeatureSnapshot(
                market_catalog_id=0,
                asof_utc=ts,
                btc_price=close,
                rolling_vwap=vwap_approx,
                vwap_deviation=deviation,
                vwap_zscore=deviation * 100,  # rough scaling
                current_volume=volume,
                expected_volume=volume,
                rvol=1.0,
                freshness_ok=True,
            )
            session.add(fs)

        await session.commit()

    await client.close()
    print(f"  Stored {len(klines)} feature snapshots.")
    print("Backfill complete.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=7)
    args = parser.parse_args()
    asyncio.run(main(args.days))
