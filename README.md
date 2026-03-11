# Polymarket BTC Bayesian Trading Bot

A production-minded, local-first Python desktop trading bot for Polymarket BTC Up/Down markets (5m and 15m contracts) using a three-signal Bayesian probability model with isotonic calibration.

## Quick Start (Windows)

1. Install [Python 3.10+](https://python.org) (check "Add to PATH")
2. Double-click `scripts/setup_and_launch.bat`
3. The GUI control panel opens automatically

## Quick Start (Linux / Mac)

```bash
chmod +x scripts/setup_and_launch.sh
./scripts/setup_and_launch.sh
```

## Manual Setup

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/Mac: source .venv/bin/activate
pip install -r requirements.txt
pip install qasync
cp .env.example .env        # edit with your credentials
python scripts/migrate_db.py
python scripts/train_calibrator.py
python -m app.main
```

## Running in Paper Mode (Default)

The bot starts in **paper trading mode** by default. No real orders are placed. To verify:

1. Launch the GUI
2. Confirm the top-right badge reads **PAPER**
3. Click **Start Bot**
4. Watch signals, decisions, and simulated fills in the dashboard

To switch to live trading, set `TRADING_MODE=live` in `.env` and restart.

## Architecture

```
app/
  clients/     - External API adapters (Binance WS/REST, Polymarket, Macro calendar)
  config/      - Typed settings from .env
  core/        - Reserved for shared domain types
  db/          - SQLAlchemy models (15 tables) and session management
  gui/         - PySide6 dark-themed desktop GUI
  models/      - Reserved for ML model wrappers
  services/    - BotController, HealthMonitor orchestration
  strategy/    - Signal engines, Bayesian updater, calibration, decision, risk, execution
  utils/       - Logging, time helpers

scripts/       - One-click setup, DB migration, calibration training, data backfill
tests/         - Unit tests (signals, Bayes, calibration, risk, decision, macro) + integration
data/          - Local SQLite DB, calibration artifacts, logs, exports
```

## Strategy Overview

1. **Three signals** computed from Binance data: VWAP deviation z-score, funding rate z-score, relative volume (RVOL)
2. **Bayesian update**: time-of-day prior x likelihood ratios per signal -> raw posterior
3. **Isotonic calibration**: maps raw posterior to calibrated probability
4. **Trade gate**: all three signals must agree directionally + minimum 4% edge + macro veto clear + risk limits pass
5. **Half-Kelly sizing** with hard caps on fraction, daily loss, open exposure, and concurrent markets
6. **Paper or live execution** against Polymarket CLOB

## Testing

```bash
python -m pytest tests/ -v
```

61 tests covering signal math, Bayesian updates, calibration, decision gates, risk/sizing, macro veto, and DB lifecycle.

## Configuration

All settings are in `.env`. Key groups:

| Group | Examples |
|-------|---------|
| Trading mode | `TRADING_MODE=paper` |
| Polymarket | `POLYMARKET_API_KEY`, `POLYMARKET_SECRET` |
| Binance | `BINANCE_API_KEY`, `BINANCE_API_SECRET` |
| Risk | `MAX_DAILY_LOSS=100`, `MAX_FRACTION_PER_TRADE=0.05` |
| Signals | `VWAP_LOOKBACK_MEDIUM=60`, `FUNDING_LOOKBACK_PERIODS=48` |
| Macro | `MACRO_VETO_BEFORE_MINUTES=30` |
| Execution | `EXECUTION_STYLE=passive_limit`, `FEE_RATE=0.002` |

## Utility Scripts

| Script | Purpose |
|--------|---------|
| `scripts/setup_and_launch.bat` | Windows one-click setup + GUI launch |
| `scripts/setup_and_launch.sh` | Linux/Mac equivalent |
| `scripts/migrate_db.py` | Create/update database schema |
| `scripts/train_calibrator.py` | Train isotonic calibration model |
| `scripts/backfill_data.py` | Backfill historical data from Binance |
