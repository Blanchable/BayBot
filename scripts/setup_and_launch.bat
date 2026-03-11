@echo off
setlocal EnableDelayedExpansion

echo.
echo  ============================================================
echo    Polymarket BTC Bayesian Trading Bot - One-Click Setup
echo  ============================================================
echo.

:: ── Step 1: Check Python ─────────────────────────────────────
echo [1/8] Checking Python installation...
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo  ERROR: Python not found on PATH.
    echo  Please install Python 3.10+ from https://python.org
    echo  Make sure to check "Add Python to PATH" during install.
    echo.
    pause
    exit /b 1
)

for /f "tokens=*" %%i in ('python --version 2^>^&1') do set PYVER=%%i
echo   Found: %PYVER%
echo.

:: ── Step 2: Create virtual environment ───────────────────────
echo [2/8] Setting up virtual environment...
if not exist ".venv" (
    python -m venv .venv
    if %errorlevel% neq 0 (
        echo  ERROR: Failed to create virtual environment.
        pause
        exit /b 1
    )
    echo   Created .venv
) else (
    echo   .venv already exists, reusing.
)
echo.

:: Activate venv
call .venv\Scripts\activate.bat

:: ── Step 3: Install dependencies ─────────────────────────────
echo [3/8] Installing dependencies (this may take a minute)...
python -m pip install --upgrade pip --quiet 2>nul
pip install -r requirements.txt --quiet 2>nul
pip install qasync --quiet 2>nul
if %errorlevel% neq 0 (
    echo  WARNING: Some dependencies may have failed. Trying verbose install...
    pip install -r requirements.txt
    pip install qasync
)
echo   Dependencies installed.
echo.

:: ── Step 4: Create required folders ──────────────────────────
echo [4/8] Creating data directories...
if not exist "data\artifacts" mkdir "data\artifacts"
if not exist "data\exports"   mkdir "data\exports"
if not exist "data\logs"      mkdir "data\logs"
echo   Folders ready.
echo.

:: ── Step 5: Copy .env if needed ──────────────────────────────
echo [5/8] Checking environment configuration...
if not exist ".env" (
    if exist ".env.example" (
        copy ".env.example" ".env" >nul
        echo   Created .env from .env.example
        echo   IMPORTANT: Edit .env to add your API credentials before going live.
    ) else (
        echo   WARNING: No .env.example found. You will need to create .env manually.
    )
) else (
    echo   .env already exists.
)
echo.

:: ── Step 6: Initialize database ──────────────────────────────
echo [6/8] Initializing database...
python -c "import asyncio; from app.config.settings import load_settings; from app.db.session import init_engine, create_tables; s=load_settings(); init_engine(s); asyncio.run(create_tables()); print('  Database initialized.')"
if %errorlevel% neq 0 (
    echo  WARNING: Database init encountered an issue. The app will retry on launch.
)
echo.

:: ── Step 7: Validate connectivity ────────────────────────────
echo [7/8] Running connectivity check...
python -c "print('  Config loads OK'); from app.config.settings import load_settings; s=load_settings(); print(f'  Mode: {s.trading_mode.value}'); print(f'  DB: {s.database_url}')"
if %errorlevel% neq 0 (
    echo  WARNING: Config validation failed. Check your .env file.
)
echo.

:: ── Step 8: Create placeholder calibration if needed ─────────
echo [8/8] Ensuring calibration artifact...
python -c "from app.strategy.calibration import CalibrationEngine; c=CalibrationEngine(); c.create_placeholder(); print('  Calibration artifact ready.')"
if %errorlevel% neq 0 (
    echo  WARNING: Calibration setup failed. Bot will use uncalibrated mode.
)
echo.

:: ── Launch ───────────────────────────────────────────────────
echo  ============================================================
echo    Setup complete! Launching the control panel...
echo  ============================================================
echo.

python -m app.main

if %errorlevel% neq 0 (
    echo.
    echo  The application exited with an error.
    echo  Check data\logs\bot.log for details.
    pause
)
