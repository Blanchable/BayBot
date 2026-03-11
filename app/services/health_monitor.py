"""Health monitor: checks connectivity to all external systems."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from app.utils.logging import get_logger

log = get_logger("health")


@dataclass
class ComponentHealth:
    component: str
    status: str  # "ok" | "degraded" | "down"
    message: str = ""
    latency_ms: float = 0.0
    last_check: float = field(default_factory=time.time)


class HealthMonitor:
    """Tracks the health of each subsystem."""

    def __init__(self):
        self._components: dict[str, ComponentHealth] = {}

    def report(self, component: str, status: str, message: str = "", latency_ms: float = 0.0):
        self._components[component] = ComponentHealth(
            component=component,
            status=status,
            message=message,
            latency_ms=latency_ms,
        )

    def get(self, component: str) -> Optional[ComponentHealth]:
        return self._components.get(component)

    def all_healthy(self) -> bool:
        if not self._components:
            return False
        return all(c.status == "ok" for c in self._components.values())

    def summary(self) -> dict[str, str]:
        return {name: c.status for name, c in self._components.items()}

    def get_heartbeats_for_db(self) -> list[dict]:
        return [
            {
                "component": c.component,
                "status": c.status,
                "message": c.message,
                "latency_ms": c.latency_ms,
                "heartbeat_time_utc": datetime.now(timezone.utc),
            }
            for c in self._components.values()
        ]
