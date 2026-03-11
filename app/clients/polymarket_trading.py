"""Polymarket CLOB trading client — order placement and management."""

from __future__ import annotations

import time
import uuid
from typing import Any

import httpx

from app.config.settings import AppSettings, TradingMode
from app.utils.logging import get_logger

log = get_logger("polymarket_trade")


class PolymarketTradingClient:
    """
    Handles order placement, cancellation, and status polling on Polymarket CLOB.
    In paper mode, orders are simulated locally and never sent to the exchange.
    """

    def __init__(self, settings: AppSettings):
        self._settings = settings
        self._base = settings.polymarket_api_url.rstrip("/")
        self._client: httpx.AsyncClient | None = None
        self._paper_fills: list[dict] = []

    @property
    def is_paper(self) -> bool:
        return self._settings.trading_mode == TradingMode.PAPER

    async def _ensure_client(self):
        if self._client is None or self._client.is_closed:
            headers = {}
            if not self.is_paper:
                headers["Authorization"] = f"Bearer {self._settings.polymarket_api_key}"
                headers["X-Passphrase"] = self._settings.polymarket_passphrase
            self._client = httpx.AsyncClient(timeout=10.0, headers=headers)

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def place_order(
        self,
        token_id: str,
        side: str,
        price: float,
        size: float,
        order_type: str = "limit",
    ) -> dict:
        client_order_id = str(uuid.uuid4())

        if self.is_paper:
            log.info(
                "paper_order",
                token_id=token_id,
                side=side,
                price=price,
                size=size,
            )
            fill = {
                "client_order_id": client_order_id,
                "exchange_order_id": f"paper-{client_order_id[:8]}",
                "status": "filled",
                "fill_price": price,
                "fill_size": size,
                "fee_paid": round(price * size * self._settings.fee_rate, 6),
                "timestamp": time.time(),
            }
            self._paper_fills.append(fill)
            return fill

        await self._ensure_client()
        payload = {
            "tokenID": token_id,
            "side": side.upper(),
            "price": str(price),
            "size": str(size),
            "type": order_type,
            "funder": self._settings.polymarket_funder,
        }
        resp = await self._client.post(f"{self._base}/order", json=payload)
        resp.raise_for_status()
        data = resp.json()
        log.info("live_order_placed", data=data)
        return {
            "client_order_id": client_order_id,
            "exchange_order_id": data.get("orderID", data.get("id", "")),
            "status": data.get("status", "posted"),
            **data,
        }

    async def cancel_order(self, exchange_order_id: str) -> dict:
        if self.is_paper:
            log.info("paper_cancel", order_id=exchange_order_id)
            return {"status": "canceled"}

        await self._ensure_client()
        resp = await self._client.delete(f"{self._base}/order/{exchange_order_id}")
        resp.raise_for_status()
        return resp.json()

    async def get_order_status(self, exchange_order_id: str) -> dict:
        if self.is_paper:
            for f in self._paper_fills:
                if f.get("exchange_order_id") == exchange_order_id:
                    return f
            return {"status": "unknown"}

        await self._ensure_client()
        resp = await self._client.get(f"{self._base}/order/{exchange_order_id}")
        resp.raise_for_status()
        return resp.json()
