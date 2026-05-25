from __future__ import annotations

import time
from dataclasses import dataclass, field
from threading import Lock
from typing import Any

from app.schemas.qa import FunctionTraceStep, RouteDecision


@dataclass(frozen=True)
class RouterTraceSnapshot:
    route: RouteDecision
    router_mode: str
    router_model: str
    router_availability: str
    router_fallback_used: bool
    router_error: str | None
    function_trace: list[FunctionTraceStep] = field(default_factory=list)


class _QARuntimeStore:
    def __init__(self) -> None:
        self._data: dict[str, tuple[dict[str, Any], float]] = {}
        self._lock = Lock()
        self._ttl_seconds = 7200

    def set_router_trace(self, request_id: str, snapshot: RouterTraceSnapshot) -> None:
        payload = {
            "route": snapshot.route.model_dump(),
            "router_mode": snapshot.router_mode,
            "router_model": snapshot.router_model,
            "router_availability": snapshot.router_availability,
            "router_fallback_used": snapshot.router_fallback_used,
            "router_error": snapshot.router_error,
            "function_trace": [item.model_dump() for item in snapshot.function_trace],
        }
        expires_at = time.time() + self._ttl_seconds
        with self._lock:
            self._data[request_id] = (payload, expires_at)

    def get_router_trace(self, request_id: str) -> RouterTraceSnapshot | None:
        now = time.time()
        with self._lock:
            item = self._data.get(request_id)
            if item is None:
                return None
            payload, expires_at = item
            if expires_at < now:
                self._data.pop(request_id, None)
                return None
        try:
            route = RouteDecision(**payload["route"])
            return RouterTraceSnapshot(
                route=route,
                router_mode=str(payload.get("router_mode", route.router_mode)),
                router_model=str(payload.get("router_model", route.router_model)),
                router_availability=str(payload.get("router_availability", "not_checked")),
                router_fallback_used=bool(payload.get("router_fallback_used", route.router_fallback_used)),
                router_error=payload.get("router_error"),
                function_trace=[FunctionTraceStep(**item) for item in payload.get("function_trace", [])],
            )
        except Exception:
            return None

    def clear_for_tests(self) -> None:
        with self._lock:
            self._data.clear()


qa_runtime_store = _QARuntimeStore()
