"""Integration test: database schema creation and basic CRUD."""

import asyncio
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.models import (
    AppLog,
    BankrollHistory,
    Base,
    CalibrationModel,
    DecisionSnapshot,
    FeatureSnapshot,
    Fill,
    LikelihoodModel,
    MacroEvent,
    MarketCatalog,
    MarketSnapshot,
    Order,
    Position,
    Prior,
    Setting,
    SystemHeartbeat,
)


@pytest_asyncio.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as sess:
        yield sess

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.mark.asyncio
async def test_create_setting(session: AsyncSession):
    s = Setting(key="test_key", value="42", value_type="int")
    session.add(s)
    await session.commit()

    result = await session.execute(select(Setting).where(Setting.key == "test_key"))
    row = result.scalar_one()
    assert row.value == "42"


@pytest.mark.asyncio
async def test_market_catalog_crud(session: AsyncSession):
    m = MarketCatalog(
        venue_market_id="0xabc123",
        market_type="btc_updown",
        contract_horizon="5m",
        underlying="BTC",
        start_time_utc=datetime.now(timezone.utc),
        end_time_utc=datetime.now(timezone.utc),
        up_token_id="tok_up",
        down_token_id="tok_down",
        status="active",
    )
    session.add(m)
    await session.commit()

    result = await session.execute(
        select(MarketCatalog).where(MarketCatalog.venue_market_id == "0xabc123")
    )
    row = result.scalar_one()
    assert row.contract_horizon == "5m"
    assert row.underlying == "BTC"


@pytest.mark.asyncio
async def test_order_fill_relationship(session: AsyncSession):
    m = MarketCatalog(
        venue_market_id="0xdef456",
        market_type="btc_updown",
        contract_horizon="15m",
        underlying="BTC",
        start_time_utc=datetime.now(timezone.utc),
        end_time_utc=datetime.now(timezone.utc),
        status="active",
    )
    session.add(m)
    await session.flush()

    o = Order(
        client_order_id="test-order-1",
        market_catalog_id=m.id,
        token_id="tok_up",
        side="buy",
        price=0.55,
        size=10.0,
        status="filled",
    )
    session.add(o)
    await session.flush()

    f = Fill(
        order_id=o.id,
        fill_time_utc=datetime.now(timezone.utc),
        fill_price=0.55,
        fill_size=10.0,
        fee_paid=0.011,
    )
    session.add(f)
    await session.commit()

    result = await session.execute(select(Order).where(Order.client_order_id == "test-order-1"))
    order = result.scalar_one()
    assert order.status == "filled"


@pytest.mark.asyncio
async def test_all_tables_created(session: AsyncSession):
    """Verify all 15 tables exist by inserting one row into each."""
    now = datetime.now(timezone.utc)

    session.add(Setting(key="k", value="v", value_type="str"))
    session.add(MacroEvent(
        event_type="CPI", title="CPI", event_time_utc=now,
        veto_start_utc=now, veto_end_utc=now,
    ))
    m = MarketCatalog(
        venue_market_id="x", market_type="btc_updown", contract_horizon="5m",
        underlying="BTC", start_time_utc=now, end_time_utc=now, status="active",
    )
    session.add(m)
    await session.flush()

    session.add(MarketSnapshot(market_catalog_id=m.id, snapshot_time_utc=now))
    session.add(FeatureSnapshot(market_catalog_id=m.id, asof_utc=now))
    session.add(Prior(market_type="btc_updown", contract_horizon="5m", tod_bucket="14:00", prior_up=0.5, version="v1"))
    session.add(LikelihoodModel(signal_name="vwap", bucket_label="neutral", direction="up", likelihood_ratio=1.0, version="v1"))
    session.add(CalibrationModel(version="v1", artifact_path="/tmp/x.pkl"))
    session.add(DecisionSnapshot(market_catalog_id=m.id, asof_utc=now))
    o = Order(client_order_id="o1", market_catalog_id=m.id, token_id="t", side="buy", price=0.5, size=1.0)
    session.add(o)
    await session.flush()
    session.add(Fill(order_id=o.id, fill_time_utc=now, fill_price=0.5, fill_size=1.0))
    session.add(Position(market_catalog_id=m.id, direction="up", qty=1.0))
    session.add(BankrollHistory(cash_balance=1000, total_equity=1000))
    session.add(SystemHeartbeat(component="test", status="ok"))
    session.add(AppLog(level="INFO", message="test"))

    await session.commit()
