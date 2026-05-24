from __future__ import annotations

import json
import time
from dataclasses import dataclass
from hashlib import sha256
from threading import Lock
from typing import Any

from app.core.config import get_settings

try:
    import redis
    from redis import Redis
    from redis.exceptions import RedisError
except Exception:  # noqa: BLE001
    redis = None
    Redis = Any  # type: ignore[misc,assignment]
    RedisError = Exception  # type: ignore[misc,assignment]


settings = get_settings()


@dataclass(frozen=True)
class CacheKeyParts:
    user_id: str
    role: str
    department: str
    permission_scope_hash: str
    kb_version_hash: str
    question_hash: str
    mode: str
    model_profile_hash: str
    prompt_version: str

    def as_key(self, prefix: str) -> str:
        return (
            f"{prefix}:qa:v1:{self.user_id}:{self.role}:{self.department}:"
            f"{self.permission_scope_hash}:{self.kb_version_hash}:{self.question_hash}:"
            f"{self.mode}:{self.model_profile_hash}:{self.prompt_version}"
        )


def _hash_text(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()[:16]


def build_cache_key_parts(
    *,
    user_id: str,
    role: str,
    department: str | None,
    permission_scope_items: list[str],
    kb_versions: list[str],
    question: str,
    mode: str,
    model_profile: str,
    prompt_version: str,
) -> CacheKeyParts:
    normalized_question = " ".join(question.strip().lower().split())
    permission_scope_hash = _hash_text("|".join(sorted(permission_scope_items)))
    kb_version_hash = _hash_text("|".join(sorted(kb_versions)))
    question_hash = _hash_text(normalized_question)
    model_profile_hash = _hash_text(model_profile)
    return CacheKeyParts(
        user_id=user_id,
        role=role or "unknown",
        department=department or "none",
        permission_scope_hash=permission_scope_hash,
        kb_version_hash=kb_version_hash,
        question_hash=question_hash,
        mode=mode,
        model_profile_hash=model_profile_hash,
        prompt_version=prompt_version,
    )


class InMemoryCacheBackend:
    def __init__(self) -> None:
        self._data: dict[str, tuple[str, float]] = {}
        self._lock = Lock()

    def get(self, key: str) -> str | None:
        now = time.time()
        with self._lock:
            value = self._data.get(key)
            if value is None:
                return None
            payload, expires_at = value
            if expires_at < now:
                self._data.pop(key, None)
                return None
            return payload

    def set(self, key: str, value: str, ttl_seconds: int) -> None:
        expires_at = time.time() + ttl_seconds
        with self._lock:
            self._data[key] = (value, expires_at)

    def clear(self) -> None:
        with self._lock:
            self._data.clear()


class RedisCacheBackend:
    def __init__(self, redis_url: str) -> None:
        if redis is None:
            raise RuntimeError("redis package is not available")
        self._client: Redis = redis.from_url(
            redis_url,
            decode_responses=True,
            socket_connect_timeout=0.5,
            socket_timeout=0.5,
        )

    def get(self, key: str) -> str | None:
        try:
            return self._client.get(key)
        except RedisError:
            return None

    def set(self, key: str, value: str, ttl_seconds: int) -> None:
        try:
            self._client.set(key, value, ex=ttl_seconds)
        except RedisError:
            return


class CacheService:
    def __init__(self) -> None:
        self.prefix = settings.redis_key_prefix
        self._memory_backend = InMemoryCacheBackend()
        self._backend = self._build_backend()

    def _build_backend(self):
        if settings.redis_url.startswith("memory://"):
            return self._memory_backend
        try:
            return RedisCacheBackend(settings.redis_url)
        except Exception:  # noqa: BLE001
            return self._memory_backend

    def get_payload(self, key_parts: CacheKeyParts) -> dict[str, Any] | None:
        key = key_parts.as_key(self.prefix)
        payload = self._backend.get(key)
        if payload is None and self._backend is not self._memory_backend:
            payload = self._memory_backend.get(key)
        if not payload:
            return None
        try:
            data = json.loads(payload)
            if isinstance(data, dict):
                return data
            return None
        except json.JSONDecodeError:
            return None

    def set_payload(self, key_parts: CacheKeyParts, payload: dict[str, Any], ttl_seconds: int) -> None:
        key = key_parts.as_key(self.prefix)
        serialized = json.dumps(payload, ensure_ascii=True)
        self._backend.set(key, serialized, ttl_seconds)
        if self._backend is not self._memory_backend:
            self._memory_backend.set(key, serialized, ttl_seconds)

    def clear_for_tests(self) -> None:
        self._memory_backend.clear()


cache_service = CacheService()
