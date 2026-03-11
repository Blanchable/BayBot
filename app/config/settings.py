"""Typed application settings loaded from .env and defaults."""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class TradingMode(str, Enum):
    PAPER = "paper"
    LIVE = "live"


class ExecutionStyle(str, Enum):
    PASSIVE_LIMIT = "passive_limit"
    AGGRESSIVE_LIMIT = "aggressive_limit"


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Trading mode
    trading_mode: TradingMode = TradingMode.PAPER

    # Polymarket
    polymarket_api_key: str = ""
    polymarket_secret: str = ""
    polymarket_passphrase: str = ""
    polymarket_api_url: str = "https://clob.polymarket.com"
    polymarket_funder: str = ""

    # Binance
    binance_api_key: str = ""
    binance_api_secret: str = ""
    binance_futures_ws: str = "wss://fstream.binance.com/ws"
    binance_futures_rest: str = "https://fapi.binance.com"

    # Database
    database_url: str = "sqlite+aiosqlite:///data/bot.db"

    # Bankroll & risk
    initial_bankroll: float = 1000.0
    max_fraction_per_trade: float = 0.05
    max_daily_loss: float = 100.0
    max_open_exposure: float = 300.0
    max_concurrent_markets: int = 4
    min_edge_threshold: float = 0.04
    min_order_size: float = 1.0

    # Signal lookbacks (seconds)
    vwap_lookback_short: int = 30
    vwap_lookback_medium: int = 60
    vwap_lookback_long: int = 180
    funding_lookback_periods: int = 48
    rvol_bucket_minutes: int = 5

    # Macro veto
    macro_veto_before_minutes: int = 30
    macro_veto_after_minutes: int = 30

    # Execution
    execution_style: ExecutionStyle = ExecutionStyle.PASSIVE_LIMIT
    stale_order_timeout_seconds: int = 30
    fee_rate: float = 0.002

    # Calibration
    calibration_artifact_dir: str = "data/artifacts"

    # GUI
    gui_refresh_interval_ms: int = 1000

    # Logging
    log_level: str = "INFO"
    log_file: str = "data/logs/bot.log"

    # Kelly sizing
    kelly_fraction: float = 0.5  # half-Kelly

    # Max losing streak before auto-pause
    max_losing_streak: int = 5
    cooldown_after_losses_seconds: int = 300

    # Auto-start bot on GUI launch
    auto_start: bool = False

    @property
    def is_live(self) -> bool:
        return self.trading_mode == TradingMode.LIVE

    @property
    def artifact_path(self) -> Path:
        return Path(self.calibration_artifact_dir)


def load_settings() -> AppSettings:
    return AppSettings()
