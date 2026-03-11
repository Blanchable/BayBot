"""Market selector: discovers and validates BTC Up/Down markets."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.polymarket_read import PolymarketReadClient
from app.db.models import MarketCatalog, MarketSnapshot
from app.utils.logging import get_logger

log = get_logger("market_selector")

MAX_SPREAD = 0.10
MIN_LIQUIDITY_SCORE = 0.3


class MarketSelector:
    """Discovers and stores tradeable BTC 5m/15m Up/Down markets."""

    def __init__(self, read_client: PolymarketReadClient):
        self._client = read_client

    async def discover_and_store(self, session: AsyncSession) -> list[MarketCatalog]:
        """Discover markets from Polymarket and upsert into catalog."""
        raw_markets = await self._client.discover_btc_markets()
        stored = []

        for rm in raw_markets:
            venue_id = rm["venue_market_id"]
            stmt = select(MarketCatalog).where(MarketCatalog.venue_market_id == venue_id)
            result = await session.execute(stmt)
            existing = result.scalar_one_or_none()

            up_id, down_id = PolymarketReadClient.parse_tokens(rm.get("tokens", []))
            end_date = rm.get("end_date_iso", "")
            try:
                end_dt = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
            except Exception:
                end_dt = datetime.now(timezone.utc)

            if existing:
                existing.status = "active" if rm.get("active") else "expired"
                existing.up_token_id = up_id or existing.up_token_id
                existing.down_token_id = down_id or existing.down_token_id
                stored.append(existing)
            else:
                cat = MarketCatalog(
                    venue_market_id=venue_id,
                    slug=rm.get("slug", ""),
                    market_type=rm.get("market_type", "btc_updown"),
                    contract_horizon=rm["contract_horizon"],
                    underlying="BTC",
                    start_time_utc=datetime.now(timezone.utc),
                    end_time_utc=end_dt,
                    up_token_id=up_id or "",
                    down_token_id=down_id or "",
                    status="active",
                )
                session.add(cat)
                stored.append(cat)

        await session.commit()
        log.info("markets_discovered", count=len(stored))
        return stored

    async def snapshot_market(
        self,
        session: AsyncSession,
        market: MarketCatalog,
    ) -> Optional[MarketSnapshot]:
        """Fetch orderbook and store a price snapshot."""
        if not market.up_token_id:
            return None

        book_up = await self._client.get_orderbook(market.up_token_id)
        book_down = (
            await self._client.get_orderbook(market.down_token_id)
            if market.down_token_id
            else {"bids": [], "asks": []}
        )

        up_bid = float(book_up["bids"][0]["price"]) if book_up.get("bids") else None
        up_ask = float(book_up["asks"][0]["price"]) if book_up.get("asks") else None
        down_bid = float(book_down["bids"][0]["price"]) if book_down.get("bids") else None
        down_ask = float(book_down["asks"][0]["price"]) if book_down.get("asks") else None

        up_mid = (up_bid + up_ask) / 2 if up_bid and up_ask else None
        down_mid = (down_bid + down_ask) / 2 if down_bid and down_ask else None
        spread_up = (up_ask - up_bid) if up_bid and up_ask else None
        spread_down = (down_ask - down_bid) if down_bid and down_ask else None

        liq_score = self._compute_liquidity_score(book_up, book_down)

        snap = MarketSnapshot(
            market_catalog_id=market.id,
            snapshot_time_utc=datetime.now(timezone.utc),
            up_bid=up_bid,
            up_ask=up_ask,
            down_bid=down_bid,
            down_ask=down_ask,
            up_mid=up_mid,
            down_mid=down_mid,
            spread_up=round(spread_up, 6) if spread_up else None,
            spread_down=round(spread_down, 6) if spread_down else None,
            liquidity_score=liq_score,
        )
        session.add(snap)
        await session.commit()
        return snap

    def validate_snapshot(self, snap: MarketSnapshot) -> tuple[bool, bool]:
        """Returns (liquidity_ok, spread_ok)."""
        liq_ok = (snap.liquidity_score or 0) >= MIN_LIQUIDITY_SCORE
        spread_ok = True
        if snap.spread_up is not None and snap.spread_up > MAX_SPREAD:
            spread_ok = False
        if snap.spread_down is not None and snap.spread_down > MAX_SPREAD:
            spread_ok = False
        return liq_ok, spread_ok

    @staticmethod
    def _compute_liquidity_score(book_up: dict, book_down: dict) -> float:
        """Simple score based on top-of-book depth."""
        total_size = 0.0
        for book in [book_up, book_down]:
            for side_key in ["bids", "asks"]:
                for level in (book.get(side_key, []) or [])[:3]:
                    total_size += float(level.get("size", 0))
        return min(total_size / 1000.0, 1.0)
