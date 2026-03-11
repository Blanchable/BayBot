"""BotController: top-level orchestrator for the trading loop."""

from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select

from app.clients.binance_rest import BinanceRestClient
from app.clients.binance_ws import BinanceWebsocketClient
from app.clients.macro_calendar import MacroCalendarClient
from app.clients.polymarket_read import PolymarketReadClient
from app.clients.polymarket_trading import PolymarketTradingClient
from app.config.settings import AppSettings
from app.db.models import (
    BankrollHistory,
    CalibrationModel,
    DecisionSnapshot,
    FeatureSnapshot,
    SystemHeartbeat,
)
from app.db.session import get_session_factory
from app.services.health_monitor import HealthMonitor
from app.strategy.bayesian import BayesianUpdater, PriorEstimator
from app.strategy.calibration import CalibrationEngine
from app.strategy.decision import DecisionEngine, DecisionInput
from app.strategy.execution import ExecutionManager
from app.strategy.market_selector import MarketSelector
from app.strategy.risk import RiskManager
from app.strategy.signals import FeatureBundle, FundingEngine, RVOLEngine, VWAPEngine
from app.utils.logging import get_logger
from app.utils.time_utils import tod_bucket, utcnow

log = get_logger("bot_controller")


class BotState:
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    ERROR = "error"


class BotController:
    """
    Central orchestrator that wires together all subsystems and runs the main trading loop.
    Designed to be driven from the GUI via start/stop methods.
    """

    def __init__(self, settings: AppSettings):
        self.settings = settings
        self.state = BotState.STOPPED
        self.bankroll: float = settings.initial_bankroll

        # Clients
        self.binance_ws = BinanceWebsocketClient(ws_url=settings.binance_futures_ws)
        self.binance_rest = BinanceRestClient(base_url=settings.binance_futures_rest)
        self.pm_read = PolymarketReadClient(api_url=settings.polymarket_api_url)
        self.pm_trade = PolymarketTradingClient(settings)
        self.macro = MacroCalendarClient(
            veto_before_min=settings.macro_veto_before_minutes,
            veto_after_min=settings.macro_veto_after_minutes,
        )

        # Strategy components
        self.vwap_engine = VWAPEngine(lookback_seconds=settings.vwap_lookback_medium)
        self.funding_engine = FundingEngine(lookback_periods=settings.funding_lookback_periods)
        self.rvol_engine = RVOLEngine(bucket_minutes=settings.rvol_bucket_minutes)
        self.bayesian = BayesianUpdater()
        self.prior_estimator = PriorEstimator()
        self.calibration = CalibrationEngine(artifact_dir=settings.calibration_artifact_dir)
        self.decision_engine = DecisionEngine()
        self.risk_manager = RiskManager(settings)
        self.execution = ExecutionManager(settings, self.pm_trade)
        self.market_selector = MarketSelector(self.pm_read)

        # Health
        self.health = HealthMonitor()

        # Internal
        self._loop_task: Optional[asyncio.Task] = None
        self._ws_task: Optional[asyncio.Task] = None
        self._latest_features: Optional[FeatureBundle] = None
        self._latest_decision: Optional[dict] = None
        self._callbacks: list = []

    def on_update(self, callback):
        """Register a callback for GUI updates."""
        self._callbacks.append(callback)

    def _notify(self, event: str, data: dict | None = None):
        for cb in self._callbacks:
            try:
                cb(event, data or {})
            except Exception:
                pass

    async def start(self):
        if self.state == BotState.RUNNING:
            return
        self.state = BotState.STARTING
        self._notify("state_change", {"state": self.state})
        log.info("bot_starting")

        try:
            await self._warm_up()
            self.state = BotState.RUNNING
            self._notify("state_change", {"state": self.state})

            self._ws_task = asyncio.create_task(self.binance_ws.start())
            self.binance_ws.on_trade(self._on_trade)
            self._loop_task = asyncio.create_task(self._main_loop())
            log.info("bot_running")
        except Exception as exc:
            self.state = BotState.ERROR
            self._notify("state_change", {"state": self.state, "error": str(exc)})
            log.error("bot_start_failed", error=str(exc))

    async def stop(self):
        if self.state == BotState.STOPPED:
            return
        self.state = BotState.STOPPING
        self._notify("state_change", {"state": self.state})
        log.info("bot_stopping")

        if self._loop_task:
            self._loop_task.cancel()
        await self.binance_ws.stop()
        if self._ws_task:
            self._ws_task.cancel()

        async with get_session_factory()() as session:
            await self.execution.cancel_stale_orders(session, timeout_s=0)

        await self.binance_rest.close()
        await self.pm_read.close()
        await self.pm_trade.close()

        self.state = BotState.STOPPED
        self._notify("state_change", {"state": self.state})
        log.info("bot_stopped")

    async def _warm_up(self):
        """Pre-flight checks."""
        # Binance REST ping
        ok = await self.binance_rest.ping()
        self.health.report("binance_rest", "ok" if ok else "down")

        # Polymarket ping
        ok = await self.pm_read.ping()
        self.health.report("polymarket", "ok" if ok else "down")

        # Load macro calendar
        events = MacroCalendarClient.seed_2025_2026_events()
        self.macro.load_events(events)

        # Load calibration
        async with get_session_factory()() as session:
            stmt = select(CalibrationModel).where(CalibrationModel.is_approved == True).order_by(CalibrationModel.created_at.desc())
            result = await session.execute(stmt)
            cal = result.scalar_one_or_none()

        if cal:
            self.calibration.load(cal.artifact_path, cal.version)
        else:
            meta = self.calibration.create_placeholder()
            log.warning("using_placeholder_calibration")

        self.health.report("calibration", "ok" if self.calibration.is_loaded else "down")
        self.health.report("database", "ok")

        # Load initial funding
        try:
            funding_data = await self.binance_rest.get_funding_rate(limit=self.settings.funding_lookback_periods)
            rates = [float(f["fundingRate"]) for f in funding_data]
            self.funding_engine.ingest(rates)
        except Exception as exc:
            log.warning("funding_warmup_failed", error=str(exc))

    def _on_trade(self, trade):
        self.vwap_engine.ingest(trade)

    async def _main_loop(self):
        """Core loop that runs on a timer."""
        cycle_interval = max(self.settings.gui_refresh_interval_ms / 1000.0, 1.0)

        while self.state == BotState.RUNNING:
            try:
                await self._run_cycle()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                log.exception("cycle_error", error=str(exc))
            await asyncio.sleep(cycle_interval)

    async def _run_cycle(self):
        """Single evaluation cycle."""
        now = utcnow()
        session_factory = get_session_factory()

        # Health checks
        self.health.report(
            "binance_ws",
            "ok" if self.binance_ws.is_connected else "down",
            latency_ms=round((time.time() - self.binance_ws.last_trade_ts) * 1000, 1)
            if self.binance_ws.last_trade_ts > 0
            else 0,
        )

        # Compute features
        vwap = self.vwap_engine.compute()
        funding = self.funding_engine.compute()

        # Compute RVOL with context from VWAP direction
        volume_info = await self._get_current_volume()
        current_vol = volume_info.get("volume", 0.0)
        rvol = self.rvol_engine.compute(
            current_volume=current_vol,
            tod_bucket=tod_bucket(now),
            price_direction=vwap.direction if vwap else "neutral",
        )

        features = FeatureBundle(vwap=vwap, funding=funding, rvol=rvol)
        self._latest_features = features

        # Discover markets
        async with session_factory() as session:
            markets = await self.market_selector.discover_and_store(session)

        if not markets:
            self._notify("cycle", {"status": "no_markets"})
            return

        for market in markets:
            if market.status != "active":
                continue

            async with session_factory() as session:
                await self._evaluate_market(session, market, features, now)

        self._notify("cycle", {
            "features": features,
            "state": self.state,
            "bankroll": self.bankroll,
        })

    async def _evaluate_market(self, session, market, features: FeatureBundle, now):
        """Evaluate a single market for trade eligibility."""
        # Snapshot the market
        snap = await self.market_selector.snapshot_market(session, market)
        if snap is None:
            return

        liq_ok, spread_ok = self.market_selector.validate_snapshot(snap)

        if not features.all_valid:
            return

        # Get prior
        bucket = tod_bucket(now)
        prior_up = self.prior_estimator.get_prior(market.contract_horizon, bucket)

        # Bayesian update
        bayes = self.bayesian.update(
            prior_up=prior_up,
            vwap_zscore=features.vwap.zscore,
            funding_zscore=features.funding.zscore,
            rvol_zscore=features.rvol.rvol - 1.0,  # center around 0
        )

        # Calibrate
        calibrated = self.calibration.calibrate(bayes.raw_posterior_up)

        # Market implied probability
        market_implied = snap.up_mid if snap.up_mid else 0.5

        # Macro veto
        veto_active, veto_event = self.macro.is_veto_active(now)

        # Risk check
        risk_ok, risk_reason = self.risk_manager.check_risk_ok()

        # Existing position check
        direction = features.agreed_direction
        has_pos = False
        if direction:
            has_pos = await self.execution.check_existing_position(
                session, market.id, direction,
            )

        # Decision
        decision_input = DecisionInput(
            calibrated_posterior_up=calibrated,
            market_implied_up=market_implied,
            agreed_direction=direction,
            macro_veto_active=veto_active,
            freshness_ok=features.freshness_ok,
            calibration_loaded=self.calibration.is_loaded,
            liquidity_ok=liq_ok,
            spread_ok=spread_ok,
            risk_ok=risk_ok,
            has_existing_position=has_pos,
            min_edge_threshold=self.settings.min_edge_threshold,
        )
        decision = self.decision_engine.evaluate(decision_input)

        # Persist decision
        ds = DecisionSnapshot(
            market_catalog_id=market.id,
            asof_utc=now,
            prior_up=prior_up,
            lr_vwap=bayes.lr_vwap,
            lr_funding=bayes.lr_funding,
            lr_rvol=bayes.lr_rvol,
            raw_posterior_up=bayes.raw_posterior_up,
            calibrated_posterior_up=calibrated,
            market_implied_up=market_implied,
            edge_up=decision.edge,
            agreed_direction=direction,
            macro_veto_active=veto_active,
            liquidity_ok=liq_ok,
            spread_ok=spread_ok,
            risk_ok=risk_ok,
            should_trade=decision.should_trade,
            blocked_reason=decision.blocked_reason,
            calibration_version=self.calibration.version,
        )
        session.add(ds)

        # Persist feature snapshot
        fs = FeatureSnapshot(
            market_catalog_id=market.id,
            asof_utc=now,
            btc_price=features.vwap.btc_price if features.vwap else None,
            rolling_vwap=features.vwap.rolling_vwap if features.vwap else None,
            vwap_deviation=features.vwap.deviation if features.vwap else None,
            vwap_zscore=features.vwap.zscore if features.vwap else None,
            funding_rate=features.funding.raw_rate if features.funding else None,
            funding_zscore=features.funding.zscore if features.funding else None,
            current_volume=features.rvol.current_volume if features.rvol else None,
            expected_volume=features.rvol.expected_volume if features.rvol else None,
            rvol=features.rvol.rvol if features.rvol else None,
            signal_vwap_direction=features.vwap.direction if features.vwap else None,
            signal_funding_direction=features.funding.direction if features.funding else None,
            signal_rvol_direction=features.rvol.direction if features.rvol else None,
            freshness_ok=features.freshness_ok,
        )
        session.add(fs)
        await session.commit()

        self._latest_decision = {
            "market": market.slug,
            "horizon": market.contract_horizon,
            "prior_up": prior_up,
            "lr_vwap": bayes.lr_vwap,
            "lr_funding": bayes.lr_funding,
            "lr_rvol": bayes.lr_rvol,
            "raw_posterior": bayes.raw_posterior_up,
            "calibrated_posterior": calibrated,
            "market_implied": market_implied,
            "edge": decision.edge,
            "direction": direction,
            "should_trade": decision.should_trade,
            "blocked_reason": decision.blocked_reason,
            "macro_veto": veto_active,
        }
        self._notify("decision", self._latest_decision)

        # Execute if approved
        if decision.should_trade and decision.direction:
            await self._execute_trade(session, market, snap, decision, calibrated)

    async def _execute_trade(self, session, market, snap, decision, calibrated_prob):
        """Size and submit an order."""
        if decision.direction == "up":
            token_id = market.up_token_id
            price = snap.up_ask if snap.up_ask else 0.5
        else:
            token_id = market.down_token_id
            price = snap.down_ask if snap.down_ask else 0.5

        if not token_id:
            return

        sizing = self.risk_manager.compute_size(
            calibrated_prob=calibrated_prob if decision.direction == "up" else (1 - calibrated_prob),
            market_price=price,
            bankroll=self.bankroll,
        )

        if sizing.skip_reason:
            log.info("trade_skipped_sizing", reason=sizing.skip_reason)
            return

        order = await self.execution.submit_order(
            session=session,
            market_catalog_id=market.id,
            token_id=token_id,
            side="buy",
            price=price,
            size=sizing.position_size,
            intent="entry",
        )

        if order.status == "filled":
            await self.execution.update_position(
                session, market.id, decision.direction,
                sizing.position_size, price,
            )
            self.bankroll -= sizing.notional
            self._notify("fill", {
                "market": market.slug,
                "direction": decision.direction,
                "size": sizing.position_size,
                "price": price,
            })

    async def _get_current_volume(self) -> dict:
        """Get recent volume from Binance REST."""
        try:
            ticker = await self.binance_rest.get_ticker_24h()
            return {"volume": float(ticker.get("volume", 0))}
        except Exception:
            return {"volume": 0.0}
