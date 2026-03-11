"""Binance Futures websocket client for real-time trade streaming."""

from __future__ import annotations

import asyncio
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Callable, Optional

import orjson
import websockets

from app.utils.logging import get_logger

log = get_logger("binance_ws")


@dataclass
class Trade:
    price: float
    qty: float
    timestamp_ms: int
    is_buyer_maker: bool


class BinanceWebsocketClient:
    """Streams BTCUSDT perpetual aggregate trades from Binance Futures."""

    def __init__(
        self,
        ws_url: str = "wss://fstream.binance.com/ws",
        symbol: str = "btcusdt",
        max_buffer: int = 50_000,
    ):
        self._ws_url = f"{ws_url}/{symbol}@aggTrade"
        self._symbol = symbol
        self._max_buffer = max_buffer
        self._trades: deque[Trade] = deque(maxlen=max_buffer)
        self._ws = None
        self._running = False
        self._callbacks: list[Callable] = []
        self._reconnect_delay = 1.0
        self._last_trade_ts: float = 0.0

    @property
    def trades(self) -> deque[Trade]:
        return self._trades

    @property
    def last_trade_ts(self) -> float:
        return self._last_trade_ts

    @property
    def is_connected(self) -> bool:
        return self._ws is not None and self._running

    def on_trade(self, callback: Callable):
        self._callbacks.append(callback)

    async def start(self):
        self._running = True
        while self._running:
            try:
                await self._connect_and_stream()
            except Exception as exc:
                log.warning("ws_error", error=str(exc), reconnect_in=self._reconnect_delay)
                await asyncio.sleep(self._reconnect_delay)
                self._reconnect_delay = min(self._reconnect_delay * 2, 30.0)

    async def _connect_and_stream(self):
        async with websockets.connect(self._ws_url, ping_interval=20) as ws:
            self._ws = ws
            self._reconnect_delay = 1.0
            log.info("ws_connected", url=self._ws_url)
            async for msg in ws:
                if not self._running:
                    break
                data = orjson.loads(msg)
                trade = Trade(
                    price=float(data["p"]),
                    qty=float(data["q"]),
                    timestamp_ms=int(data["T"]),
                    is_buyer_maker=data["m"],
                )
                self._trades.append(trade)
                self._last_trade_ts = time.time()
                for cb in self._callbacks:
                    try:
                        cb(trade)
                    except Exception:
                        log.exception("trade_callback_error")

    async def stop(self):
        self._running = False
        if self._ws:
            await self._ws.close()
            self._ws = None
        log.info("ws_stopped")
