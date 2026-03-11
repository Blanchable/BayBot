"""SQLAlchemy ORM models — all 15 tables for the Polymarket Bayesian bot."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


def _uuid() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.utcnow()


# ── 1. settings ──────────────────────────────────────────────────────────

class Setting(Base):
    __tablename__ = "settings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String(256), unique=True, nullable=False)
    value = Column(Text, nullable=True)
    value_type = Column(String(32), nullable=False, default="str")
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)


# ── 2. macro_events ─────────────────────────────────────────────────────

class MacroEvent(Base):
    __tablename__ = "macro_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_type = Column(String(64), nullable=False)
    source = Column(String(64), nullable=True)
    title = Column(String(256), nullable=False)
    event_time_utc = Column(DateTime, nullable=False, index=True)
    event_time_local = Column(DateTime, nullable=True)
    country = Column(String(8), nullable=True)
    importance = Column(String(16), nullable=True)
    veto_start_utc = Column(DateTime, nullable=False)
    veto_end_utc = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=_utcnow)

    __table_args__ = (
        Index("ix_macro_veto_window", "veto_start_utc", "veto_end_utc"),
    )


# ── 3. market_catalog ───────────────────────────────────────────────────

class MarketCatalog(Base):
    __tablename__ = "market_catalog"

    id = Column(Integer, primary_key=True, autoincrement=True)
    venue_market_id = Column(String(128), nullable=False)
    slug = Column(String(256), nullable=True)
    market_type = Column(String(32), nullable=False)
    contract_horizon = Column(String(16), nullable=False)
    underlying = Column(String(16), nullable=False, default="BTC")
    start_time_utc = Column(DateTime, nullable=False)
    end_time_utc = Column(DateTime, nullable=False)
    up_token_id = Column(String(128), nullable=True)
    down_token_id = Column(String(128), nullable=True)
    tick_size = Column(Float, nullable=True)
    min_order_size = Column(Float, nullable=True)
    fee_enabled = Column(Boolean, default=True)
    status = Column(String(16), nullable=False, default="active")
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    snapshots = relationship("MarketSnapshot", back_populates="market")
    features = relationship("FeatureSnapshot", back_populates="market")
    decisions = relationship("DecisionSnapshot", back_populates="market")
    orders = relationship("Order", back_populates="market")
    positions = relationship("Position", back_populates="market")

    __table_args__ = (
        Index("ix_mkt_lookup", "underlying", "contract_horizon", "start_time_utc"),
        Index("ix_mkt_status", "status"),
    )


# ── 4. market_snapshots ────────────────────────────────────────────────

class MarketSnapshot(Base):
    __tablename__ = "market_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    market_catalog_id = Column(Integer, ForeignKey("market_catalog.id"), nullable=False)
    snapshot_time_utc = Column(DateTime, nullable=False)
    up_bid = Column(Float, nullable=True)
    up_ask = Column(Float, nullable=True)
    down_bid = Column(Float, nullable=True)
    down_ask = Column(Float, nullable=True)
    up_mid = Column(Float, nullable=True)
    down_mid = Column(Float, nullable=True)
    spread_up = Column(Float, nullable=True)
    spread_down = Column(Float, nullable=True)
    liquidity_score = Column(Float, nullable=True)
    source_latency_ms = Column(Float, nullable=True)

    market = relationship("MarketCatalog", back_populates="snapshots")

    __table_args__ = (
        Index("ix_mktsn_time", "market_catalog_id", "snapshot_time_utc"),
    )


# ── 5. feature_snapshots ───────────────────────────────────────────────

class FeatureSnapshot(Base):
    __tablename__ = "feature_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    market_catalog_id = Column(Integer, ForeignKey("market_catalog.id"), nullable=False)
    asof_utc = Column(DateTime, nullable=False)
    btc_price = Column(Float, nullable=True)
    rolling_vwap = Column(Float, nullable=True)
    vwap_deviation = Column(Float, nullable=True)
    vwap_zscore = Column(Float, nullable=True)
    funding_rate = Column(Float, nullable=True)
    funding_zscore = Column(Float, nullable=True)
    current_volume = Column(Float, nullable=True)
    expected_volume = Column(Float, nullable=True)
    rvol = Column(Float, nullable=True)
    signal_vwap_direction = Column(String(8), nullable=True)
    signal_funding_direction = Column(String(8), nullable=True)
    signal_rvol_direction = Column(String(8), nullable=True)
    freshness_ok = Column(Boolean, default=True)
    created_at = Column(DateTime, default=_utcnow)

    market = relationship("MarketCatalog", back_populates="features")

    __table_args__ = (
        Index("ix_feat_mkt_asof", "market_catalog_id", "asof_utc"),
        Index("ix_feat_asof", "asof_utc"),
    )


# ── 6. priors ───────────────────────────────────────────────────────────

class Prior(Base):
    __tablename__ = "priors"

    id = Column(Integer, primary_key=True, autoincrement=True)
    market_type = Column(String(32), nullable=False)
    contract_horizon = Column(String(16), nullable=False)
    tod_bucket = Column(String(8), nullable=False)
    prior_up = Column(Float, nullable=False, default=0.5)
    sample_size = Column(Integer, nullable=True)
    version = Column(String(32), nullable=False)
    created_at = Column(DateTime, default=_utcnow)


# ── 7. likelihood_models ────────────────────────────────────────────────

class LikelihoodModel(Base):
    __tablename__ = "likelihood_models"

    id = Column(Integer, primary_key=True, autoincrement=True)
    signal_name = Column(String(32), nullable=False)
    bucket_label = Column(String(32), nullable=False)
    direction = Column(String(8), nullable=False)
    likelihood_ratio = Column(Float, nullable=False)
    sample_size = Column(Integer, nullable=True)
    version = Column(String(32), nullable=False)
    created_at = Column(DateTime, default=_utcnow)

    __table_args__ = (
        Index("ix_lr_signal_ver", "signal_name", "version"),
    )


# ── 8. calibration_models ──────────────────────────────────────────────

class CalibrationModel(Base):
    __tablename__ = "calibration_models"

    id = Column(Integer, primary_key=True, autoincrement=True)
    version = Column(String(32), nullable=False, unique=True)
    artifact_path = Column(String(512), nullable=False)
    model_type = Column(String(32), nullable=False, default="isotonic")
    training_start_utc = Column(DateTime, nullable=True)
    training_end_utc = Column(DateTime, nullable=True)
    validation_metric_brier = Column(Float, nullable=True)
    validation_metric_logloss = Column(Float, nullable=True)
    is_approved = Column(Boolean, default=False)
    created_at = Column(DateTime, default=_utcnow)

    __table_args__ = (
        Index("ix_cal_approved", "is_approved"),
        Index("ix_cal_version", "version"),
    )


# ── 9. decision_snapshots ──────────────────────────────────────────────

class DecisionSnapshot(Base):
    __tablename__ = "decision_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    market_catalog_id = Column(Integer, ForeignKey("market_catalog.id"), nullable=False)
    asof_utc = Column(DateTime, nullable=False)
    prior_up = Column(Float, nullable=True)
    lr_vwap = Column(Float, nullable=True)
    lr_funding = Column(Float, nullable=True)
    lr_rvol = Column(Float, nullable=True)
    raw_posterior_up = Column(Float, nullable=True)
    calibrated_posterior_up = Column(Float, nullable=True)
    market_implied_up = Column(Float, nullable=True)
    edge_up = Column(Float, nullable=True)
    agreed_direction = Column(String(8), nullable=True)
    macro_veto_active = Column(Boolean, default=False)
    liquidity_ok = Column(Boolean, default=True)
    spread_ok = Column(Boolean, default=True)
    risk_ok = Column(Boolean, default=True)
    should_trade = Column(Boolean, default=False)
    blocked_reason = Column(Text, nullable=True)
    calibration_version = Column(String(32), nullable=True)
    created_at = Column(DateTime, default=_utcnow)

    market = relationship("MarketCatalog", back_populates="decisions")

    __table_args__ = (
        Index("ix_dec_mkt_asof", "market_catalog_id", "asof_utc"),
        Index("ix_dec_should_trade", "should_trade"),
    )


# ── 10. orders ─────────────────────────────────────────────────────────

class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, autoincrement=True)
    client_order_id = Column(String(128), unique=True, nullable=False, default=_uuid)
    market_catalog_id = Column(Integer, ForeignKey("market_catalog.id"), nullable=False)
    token_id = Column(String(128), nullable=False)
    side = Column(String(8), nullable=False)
    price = Column(Float, nullable=False)
    size = Column(Float, nullable=False)
    order_type = Column(String(32), nullable=False, default="limit")
    intent = Column(String(16), nullable=True)
    status = Column(String(24), nullable=False, default="created")
    submitted_at_utc = Column(DateTime, default=_utcnow)
    updated_at_utc = Column(DateTime, default=_utcnow, onupdate=_utcnow)
    exchange_order_id = Column(String(128), nullable=True)
    rejection_reason = Column(Text, nullable=True)

    market = relationship("MarketCatalog", back_populates="orders")
    fills = relationship("Fill", back_populates="order")

    __table_args__ = (
        Index("ix_ord_coid", "client_order_id"),
        Index("ix_ord_mkt_time", "market_catalog_id", "submitted_at_utc"),
        Index("ix_ord_status", "status"),
    )


# ── 11. fills ──────────────────────────────────────────────────────────

class Fill(Base):
    __tablename__ = "fills"

    id = Column(Integer, primary_key=True, autoincrement=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    fill_time_utc = Column(DateTime, nullable=False)
    fill_price = Column(Float, nullable=False)
    fill_size = Column(Float, nullable=False)
    fee_paid = Column(Float, default=0.0)
    rebate_received = Column(Float, default=0.0)
    liquidity_role = Column(String(8), nullable=True)
    execution_slippage = Column(Float, nullable=True)

    order = relationship("Order", back_populates="fills")

    __table_args__ = (
        Index("ix_fill_order", "order_id"),
        Index("ix_fill_time", "fill_time_utc"),
    )


# ── 12. positions ──────────────────────────────────────────────────────

class Position(Base):
    __tablename__ = "positions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    market_catalog_id = Column(Integer, ForeignKey("market_catalog.id"), nullable=False)
    direction = Column(String(8), nullable=False)
    qty = Column(Float, nullable=False, default=0.0)
    avg_price = Column(Float, nullable=True)
    notional = Column(Float, nullable=True)
    opened_at_utc = Column(DateTime, default=_utcnow)
    closed_at_utc = Column(DateTime, nullable=True)
    realized_pnl = Column(Float, default=0.0)
    unrealized_pnl = Column(Float, default=0.0)
    status = Column(String(16), nullable=False, default="open")

    market = relationship("MarketCatalog", back_populates="positions")

    __table_args__ = (
        Index("ix_pos_mkt", "market_catalog_id"),
        Index("ix_pos_status", "status"),
    )


# ── 13. bankroll_history ───────────────────────────────────────────────

class BankrollHistory(Base):
    __tablename__ = "bankroll_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp_utc = Column(DateTime, nullable=False, index=True, default=_utcnow)
    cash_balance = Column(Float, nullable=False)
    reserved_balance = Column(Float, default=0.0)
    realized_pnl_day = Column(Float, default=0.0)
    unrealized_pnl = Column(Float, default=0.0)
    total_equity = Column(Float, nullable=False)


# ── 14. system_heartbeats ──────────────────────────────────────────────

class SystemHeartbeat(Base):
    __tablename__ = "system_heartbeats"

    id = Column(Integer, primary_key=True, autoincrement=True)
    component = Column(String(64), nullable=False)
    status = Column(String(16), nullable=False)
    message = Column(Text, nullable=True)
    latency_ms = Column(Float, nullable=True)
    heartbeat_time_utc = Column(DateTime, default=_utcnow, nullable=False)

    __table_args__ = (
        Index("ix_hb_comp_time", "component", "heartbeat_time_utc"),
    )


# ── 15. app_logs ───────────────────────────────────────────────────────

class AppLog(Base):
    __tablename__ = "app_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp_utc = Column(DateTime, nullable=False, default=_utcnow, index=True)
    level = Column(String(16), nullable=False, index=True)
    component = Column(String(64), nullable=True)
    message = Column(Text, nullable=False)
    context_json = Column(Text, nullable=True)
