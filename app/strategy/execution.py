"""Execution manager: order lifecycle, fill tracking, PnL attribution."""

from __future__ import annotations

import asyncio
import time
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.polymarket_trading import PolymarketTradingClient
from app.config.settings import AppSettings
from app.db.models import Fill, Order, Position
from app.utils.logging import get_logger

log = get_logger("execution")


class ExecutionManager:
    """Handles the full order lifecycle from submission through fill tracking."""

    def __init__(self, settings: AppSettings, trading_client: PolymarketTradingClient):
        self._settings = settings
        self._client = trading_client
        self._active_orders: dict[str, dict] = {}

    async def submit_order(
        self,
        session: AsyncSession,
        market_catalog_id: int,
        token_id: str,
        side: str,
        price: float,
        size: float,
        intent: str = "entry",
    ) -> Order:
        """Create, persist, and submit an order."""
        client_oid = str(uuid.uuid4())

        order = Order(
            client_order_id=client_oid,
            market_catalog_id=market_catalog_id,
            token_id=token_id,
            side=side,
            price=price,
            size=size,
            order_type="limit",
            intent=intent,
            status="created",
        )
        session.add(order)
        await session.flush()

        try:
            result = await self._client.place_order(
                token_id=token_id,
                side=side,
                price=price,
                size=size,
            )
            order.exchange_order_id = result.get("exchange_order_id", "")
            order.status = result.get("status", "posted")

            if order.status == "filled":
                fill = Fill(
                    order_id=order.id,
                    fill_time_utc=datetime.now(timezone.utc),
                    fill_price=result.get("fill_price", price),
                    fill_size=result.get("fill_size", size),
                    fee_paid=result.get("fee_paid", 0.0),
                    rebate_received=0.0,
                    liquidity_role="maker" if self._settings.execution_style.value == "passive_limit" else "taker",
                    execution_slippage=round(result.get("fill_price", price) - price, 6),
                )
                session.add(fill)

            self._active_orders[client_oid] = {
                "order_id": order.id,
                "submitted_at": time.time(),
            }

        except Exception as exc:
            order.status = "rejected"
            order.rejection_reason = str(exc)
            log.error("order_rejected", error=str(exc))

        await session.commit()
        log.info(
            "order_submitted",
            client_oid=client_oid,
            status=order.status,
            side=side,
            price=price,
            size=size,
        )
        return order

    async def cancel_stale_orders(self, session: AsyncSession, timeout_s: int | None = None):
        """Cancel orders older than the configured timeout."""
        timeout = timeout_s or self._settings.stale_order_timeout_seconds
        now = time.time()
        stale_keys = []

        for coid, info in self._active_orders.items():
            if now - info["submitted_at"] > timeout:
                stale_keys.append(coid)

        for coid in stale_keys:
            info = self._active_orders.pop(coid)
            stmt = select(Order).where(Order.id == info["order_id"])
            result = await session.execute(stmt)
            order = result.scalar_one_or_none()
            if order and order.status in ("created", "posted"):
                if order.exchange_order_id:
                    try:
                        await self._client.cancel_order(order.exchange_order_id)
                    except Exception as exc:
                        log.warning("cancel_failed", error=str(exc))
                order.status = "canceled"
                await session.commit()
                log.info("stale_order_canceled", client_oid=coid)

    async def update_position(
        self,
        session: AsyncSession,
        market_catalog_id: int,
        direction: str,
        fill_qty: float,
        fill_price: float,
    ) -> Position:
        """Open or update a position after a fill."""
        stmt = select(Position).where(
            Position.market_catalog_id == market_catalog_id,
            Position.direction == direction,
            Position.status == "open",
        )
        result = await session.execute(stmt)
        pos = result.scalar_one_or_none()

        if pos is None:
            pos = Position(
                market_catalog_id=market_catalog_id,
                direction=direction,
                qty=fill_qty,
                avg_price=fill_price,
                notional=round(fill_qty * fill_price, 4),
                status="open",
            )
            session.add(pos)
        else:
            total_qty = pos.qty + fill_qty
            pos.avg_price = (pos.avg_price * pos.qty + fill_price * fill_qty) / total_qty
            pos.qty = total_qty
            pos.notional = round(total_qty * pos.avg_price, 4)

        await session.commit()
        return pos

    async def check_existing_position(
        self,
        session: AsyncSession,
        market_catalog_id: int,
        direction: str,
    ) -> bool:
        stmt = select(Position).where(
            Position.market_catalog_id == market_catalog_id,
            Position.direction == direction,
            Position.status == "open",
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none() is not None
