#!/usr/bin/env bash
# Polymarket BTC Bayesian Bot — Linux/Mac setup and launch
set -e

echo ""
echo "  ============================================================"
echo "    Polymarket BTC Bayesian Trading Bot - Setup"
echo "  ============================================================"
echo ""

# Step 1: Check Python
echo "[1/8] Checking Python..."
PYTHON=""
if command -v python3 &>/dev/null; then
    PYTHON=python3
elif command -v python &>/dev/null; then
    PYTHON=python
else
    echo "  ERROR: Python 3.10+ not found. Install from https://python.org"
    exit 1
fi
echo "  Found: $($PYTHON --version)"

# Step 2: Virtual environment
echo "[2/8] Virtual environment..."
if [ ! -d ".venv" ]; then
    $PYTHON -m venv .venv
    echo "  Created .venv"
else
    echo "  .venv exists"
fi
source .venv/bin/activate

# Step 3: Dependencies
echo "[3/8] Installing dependencies..."
pip install --upgrade pip -q
pip install -r requirements.txt -q
pip install qasync -q
echo "  Done"

# Step 4: Directories
echo "[4/8] Creating directories..."
mkdir -p data/{artifacts,exports,logs}
echo "  Done"

# Step 5: .env
echo "[5/8] Environment config..."
if [ ! -f ".env" ] && [ -f ".env.example" ]; then
    cp .env.example .env
    echo "  Created .env from .env.example"
    echo "  IMPORTANT: Edit .env with your API credentials before going live."
else
    echo "  .env exists"
fi

# Step 6: Database
echo "[6/8] Initializing database..."
$PYTHON -c "
import asyncio
from app.config.settings import load_settings
from app.db.session import init_engine, create_tables
s = load_settings(); init_engine(s); asyncio.run(create_tables())
print('  Done')
"

# Step 7: Validation
echo "[7/8] Config validation..."
$PYTHON -c "
from app.config.settings import load_settings
s = load_settings()
print(f'  Mode: {s.trading_mode.value}')
print(f'  DB: {s.database_url}')
"

# Step 8: Calibration
echo "[8/8] Calibration artifact..."
$PYTHON -c "
from app.strategy.calibration import CalibrationEngine
c = CalibrationEngine(); c.create_placeholder()
print('  Ready')
"

echo ""
echo "  ============================================================"
echo "    Setup complete! Launching GUI..."
echo "  ============================================================"
echo ""

$PYTHON -m app.main
