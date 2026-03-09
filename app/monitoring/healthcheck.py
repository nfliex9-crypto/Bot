"""
Health Checker.

Probes every critical subsystem and returns a structured health report.
Used by:
  - Docker HEALTHCHECK
  - Kubernetes liveness / readiness probes
  - FastAPI /health and /status endpoints
"""
import asyncio
import time
from datetime import datetime, timezone
from typing import Dict, Optional

UTC = timezone.utc


class ComponentStatus:
    OK = "ok"
    DEGRADED = "degraded"
    DOWN = "down"
    UNKNOWN = "unknown"


class HealthChecker:
    """
    Checks each component and aggregates an overall health status.
    """

    def __init__(self):
        self._results: Dict[str, dict] = {}
        self._last_check: Optional[datetime] = None

    async def run_all(
        self,
        db_url: Optional[str] = None,
        redis_url: Optional[str] = None,
        mt5_connected: bool = False,
        binance_connected: bool = False,
        bot_state: str = "unknown",
    ) -> dict:
        """Run all health checks and return aggregated result."""
        checks = await asyncio.gather(
            self._check_database(db_url),
            self._check_redis(redis_url),
            self._check_broker("mt5", mt5_connected),
            self._check_broker("binance", binance_connected),
            self._check_bot(bot_state),
            return_exceptions=True,
        )

        labels = ["database", "redis", "mt5_broker", "binance_broker", "bot_engine"]
        results = {}
        for label, check in zip(labels, checks):
            if isinstance(check, Exception):
                results[label] = {"status": ComponentStatus.DOWN, "error": str(check)}
            else:
                results[label] = check

        overall = self._aggregate(results)
        self._results = results
        self._last_check = datetime.now(UTC)

        return {
            "status": overall,
            "timestamp": self._last_check.isoformat(),
            "components": results,
        }

    async def _check_database(self, db_url: Optional[str]) -> dict:
        if not db_url:
            return {"status": ComponentStatus.UNKNOWN, "note": "no db_url provided"}
        t0 = time.perf_counter()
        try:
            import asyncpg
            conn = await asyncio.wait_for(
                asyncpg.connect(db_url.replace("postgresql+asyncpg://", "postgresql://")),
                timeout=3.0,
            )
            await conn.execute("SELECT 1")
            await conn.close()
            latency_ms = round((time.perf_counter() - t0) * 1000, 1)
            return {"status": ComponentStatus.OK, "latency_ms": latency_ms}
        except asyncio.TimeoutError:
            return {"status": ComponentStatus.DOWN, "error": "connection timeout"}
        except Exception as e:
            return {"status": ComponentStatus.DOWN, "error": str(e)[:100]}

    async def _check_redis(self, redis_url: Optional[str]) -> dict:
        if not redis_url:
            return {"status": ComponentStatus.UNKNOWN, "note": "redis not configured"}
        t0 = time.perf_counter()
        try:
            import redis.asyncio as aioredis
            client = aioredis.from_url(redis_url, socket_connect_timeout=3)
            await asyncio.wait_for(client.ping(), timeout=3.0)
            await client.aclose()
            latency_ms = round((time.perf_counter() - t0) * 1000, 1)
            return {"status": ComponentStatus.OK, "latency_ms": latency_ms}
        except asyncio.TimeoutError:
            return {"status": ComponentStatus.DEGRADED, "error": "timeout"}
        except Exception as e:
            return {"status": ComponentStatus.DEGRADED, "error": str(e)[:100]}

    async def _check_broker(self, name: str, connected: bool) -> dict:
        if connected:
            return {"status": ComponentStatus.OK}
        return {"status": ComponentStatus.DEGRADED, "note": f"{name} not connected (paper mode)"}

    async def _check_bot(self, state: str) -> dict:
        mapping = {
            "running": ComponentStatus.OK,
            "paused": ComponentStatus.DEGRADED,
            "stopped": ComponentStatus.DEGRADED,
            "starting": ComponentStatus.DEGRADED,
            "error": ComponentStatus.DOWN,
        }
        status = mapping.get(state, ComponentStatus.UNKNOWN)
        return {"status": status, "state": state}

    def _aggregate(self, results: Dict[str, dict]) -> str:
        statuses = [v.get("status", ComponentStatus.UNKNOWN) for v in results.values()]
        if ComponentStatus.DOWN in statuses:
            return ComponentStatus.DOWN
        if ComponentStatus.DEGRADED in statuses:
            return ComponentStatus.DEGRADED
        if all(s == ComponentStatus.OK for s in statuses):
            return ComponentStatus.OK
        return ComponentStatus.DEGRADED

    def last_result(self) -> dict:
        return {
            "status": self._aggregate(self._results) if self._results else ComponentStatus.UNKNOWN,
            "timestamp": self._last_check.isoformat() if self._last_check else None,
            "components": self._results,
        }
