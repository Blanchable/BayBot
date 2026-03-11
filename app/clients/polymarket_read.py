"""Polymarket CLOB read-only client for market discovery and orderbook."""

from __future__ import annotations

import re
import time
from datetime import datetime, timezone
from typing import Any

import httpx

from app.utils.logging import get_logger

log = get_logger("polymarket_read")


class PolymarketReadClient:
    """Discovers and reads BTC Up/Down markets from Polymarket CLOB."""

    def __init__(self, api_url: str = "https://clob.polymarket.com"):
        self._base = api_url.rstrip("/")
        self._client: httpx.AsyncClient | None = None

    async def _ensure_client(self):
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=15.0)

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def _get(self, path: str, params: dict | None = None) -> Any:
        await self._ensure_client()
        url = f"{self._base}{path}"
        t0 = time.monotonic()
        resp = await self._client.get(url, params=params)
        latency = (time.monotonic() - t0) * 1000
        resp.raise_for_status()
        log.debug("pm_rest", path=path, latency_ms=round(latency, 1))
        return resp.json()

    async def discover_btc_markets(self) -> list[dict]:
        """Find active BTC 5m and 15m Up/Down markets."""
        try:
            data = await self._get("/markets", params={"active": "true"})
        except Exception:
            log.warning("market_discovery_failed")
            return []

        markets = data if isinstance(data, list) else data.get("data", data.get("markets", []))
        btc_markets = []
        for m in markets:
            q = (m.get("question", "") + m.get("description", "")).lower()
            if "btc" not in q and "bitcoin" not in q:
                continue
            horizon = self._detect_horizon(q)
            if horizon not in ("5m", "15m"):
                continue
            btc_markets.append({
                "venue_market_id": m.get("condition_id", m.get("id", "")),
                "slug": m.get("slug", ""),
                "question": m.get("question", ""),
                "market_type": "btc_updown",
                "contract_horizon": horizon,
                "tokens": m.get("tokens", []),
                "end_date_iso": m.get("end_date_iso", ""),
                "active": m.get("active", True),
                "raw": m,
            })
        return btc_markets

    async def get_orderbook(self, token_id: str) -> dict:
        try:
            return await self._get(f"/book", params={"token_id": token_id})
        except Exception:
            log.warning("orderbook_fetch_failed", token_id=token_id)
            return {"bids": [], "asks": []}

    async def get_market_price(self, token_id: str) -> dict:
        try:
            return await self._get(f"/price", params={"token_id": token_id})
        except Exception:
            return {}

    async def ping(self) -> bool:
        try:
            await self._get("/")
            return True
        except Exception:
            return False

    @staticmethod
    def _detect_horizon(text: str) -> str | None:
        if re.search(r"\b5[\s-]?min", text):
            return "5m"
        if re.search(r"\b15[\s-]?min", text):
            return "15m"
        return None

    @staticmethod
    def parse_tokens(tokens: list[dict]) -> tuple[str | None, str | None]:
        """Return (up_token_id, down_token_id) from token list."""
        up_id = down_id = None
        for t in tokens:
            outcome = t.get("outcome", "").lower()
            tid = t.get("token_id", "")
            if "up" in outcome or "yes" in outcome:
                up_id = tid
            elif "down" in outcome or "no" in outcome:
                down_id = tid
        return up_id, down_id
