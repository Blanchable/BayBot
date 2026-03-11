"""Binance Futures REST client for funding rate, klines, volume data."""

from __future__ import annotations

import time
from typing import Any

import httpx

from app.utils.logging import get_logger

log = get_logger("binance_rest")


class BinanceRestClient:
    """Read-only Binance Futures REST endpoints."""

    def __init__(self, base_url: str = "https://fapi.binance.com"):
        self._base = base_url.rstrip("/")
        self._client: httpx.AsyncClient | None = None

    async def _ensure_client(self):
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=10.0)

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
        log.debug("rest_call", path=path, latency_ms=round(latency, 1))
        return resp.json()

    async def get_funding_rate(self, symbol: str = "BTCUSDT", limit: int = 100) -> list[dict]:
        return await self._get("/fapi/v1/fundingRate", {"symbol": symbol, "limit": limit})

    async def get_premium_index(self, symbol: str = "BTCUSDT") -> dict:
        data = await self._get("/fapi/v1/premiumIndex", {"symbol": symbol})
        if isinstance(data, list):
            return data[0] if data else {}
        return data

    async def get_klines(
        self,
        symbol: str = "BTCUSDT",
        interval: str = "5m",
        limit: int = 100,
    ) -> list[list]:
        return await self._get(
            "/fapi/v1/klines",
            {"symbol": symbol, "interval": interval, "limit": limit},
        )

    async def get_ticker_24h(self, symbol: str = "BTCUSDT") -> dict:
        return await self._get("/fapi/v1/ticker/24hr", {"symbol": symbol})

    async def ping(self) -> bool:
        try:
            await self._get("/fapi/v1/ping")
            return True
        except Exception:
            return False
