from __future__ import annotations

import math
from abc import ABC, abstractmethod
from dataclasses import dataclass
from hashlib import sha256
from threading import Lock
from typing import Literal

import httpx

from app.core.config import get_settings

try:
    from sentence_transformers import SentenceTransformer
except Exception:  # noqa: BLE001
    SentenceTransformer = None  # type: ignore[assignment]


settings = get_settings()


@dataclass(frozen=True)
class EmbeddingRuntimeStatus:
    mode: str
    configured_backend: str
    provider: str
    model: str
    availability: Literal["available", "unavailable", "not_checked"]
    fallback_used: bool
    error: str | None


class _EmbeddingStatusStore:
    def __init__(self) -> None:
        self._lock = Lock()
        self._status = EmbeddingRuntimeStatus(
            mode=settings.embedding_mode,
            configured_backend=settings.local_embedding_backend,
            provider="deterministic-mock",
            model="deterministic-mock",
            availability="not_checked",
            fallback_used=False,
            error=None,
        )

    def update(self, status: EmbeddingRuntimeStatus) -> None:
        with self._lock:
            self._status = status

    def snapshot(self) -> EmbeddingRuntimeStatus:
        with self._lock:
            status = self._status
        if status.mode == settings.embedding_mode and status.configured_backend == settings.local_embedding_backend:
            return status
        return EmbeddingRuntimeStatus(
            mode=settings.embedding_mode,
            configured_backend=settings.local_embedding_backend,
            provider=status.provider if settings.embedding_mode == "local" else "deterministic-mock",
            model=status.model if settings.embedding_mode == "local" else "deterministic-mock",
            availability="not_checked",
            fallback_used=False,
            error=None,
        )


_embedding_status_store = _EmbeddingStatusStore()
_sentence_transformer_lock = Lock()
_sentence_transformer_models: dict[str, object] = {}


class BaseEmbeddingProvider(ABC):
    @property
    @abstractmethod
    def provider_name(self) -> str:
        raise NotImplementedError

    @property
    @abstractmethod
    def model_name(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def embed(self, text: str, dimensions: int) -> list[float]:
        raise NotImplementedError


class DeterministicMockEmbeddingProvider(BaseEmbeddingProvider):
    @property
    def provider_name(self) -> str:
        return "deterministic-mock"

    @property
    def model_name(self) -> str:
        return "deterministic-mock"

    def embed(self, text: str, dimensions: int) -> list[float]:
        return _deterministic_mock_embed(text, dimensions)


class OllamaEmbeddingProvider(BaseEmbeddingProvider):
    @property
    def provider_name(self) -> str:
        return "ollama-local"

    @property
    def model_name(self) -> str:
        return settings.local_embedding_model

    def embed(self, text: str, dimensions: int) -> list[float]:
        if not text.strip():
            return [0.0] * dimensions

        payload = {"model": settings.local_embedding_model, "prompt": text}
        base_url = settings.local_embedding_base_url.rstrip("/")
        headers = {"Content-Type": "application/json"}
        with httpx.Client(timeout=settings.local_embedding_timeout_seconds) as client:
            try:
                response = client.post(f"{base_url}/api/embeddings", json=payload, headers=headers)
                response.raise_for_status()
                data = response.json()
            except Exception:
                response = client.post(f"{base_url}/api/embed", json={"model": settings.local_embedding_model, "input": text}, headers=headers)
                response.raise_for_status()
                data = response.json()

        vector = _extract_ollama_embedding(data)
        return _project_and_normalize(vector, dimensions)


class SentenceTransformersEmbeddingProvider(BaseEmbeddingProvider):
    @property
    def provider_name(self) -> str:
        return "sentence-transformers-local"

    @property
    def model_name(self) -> str:
        return settings.local_embedding_model

    def _load_model(self):
        if SentenceTransformer is None:
            raise RuntimeError("sentence_transformers_not_installed")
        with _sentence_transformer_lock:
            model = _sentence_transformer_models.get(settings.local_embedding_model)
            if model is not None:
                return model
            loaded = SentenceTransformer(settings.local_embedding_model)
            _sentence_transformer_models[settings.local_embedding_model] = loaded
            return loaded

    def embed(self, text: str, dimensions: int) -> list[float]:
        if not text.strip():
            return [0.0] * dimensions
        model = self._load_model()
        vector = model.encode([text], normalize_embeddings=True, convert_to_numpy=True)[0]
        values = [float(item) for item in vector.tolist()]
        return _project_and_normalize(values, dimensions)


def _safe_embedding_error(exc: Exception) -> str:
    if isinstance(exc, httpx.TimeoutException):
        return "embedding_timeout"
    if isinstance(exc, httpx.HTTPStatusError):
        return "embedding_http_error"
    if isinstance(exc, httpx.HTTPError):
        return "embedding_network_error"
    if isinstance(exc, RuntimeError):
        return str(exc)
    return "embedding_error"


def _extract_ollama_embedding(payload: dict) -> list[float]:
    if isinstance(payload.get("embedding"), list):
        return [float(item) for item in payload.get("embedding", [])]
    if isinstance(payload.get("embeddings"), list):
        rows = payload.get("embeddings", [])
        if rows and isinstance(rows[0], list):
            return [float(item) for item in rows[0]]
    raise ValueError("invalid_ollama_embedding_response")


def _project_and_normalize(values: list[float], dimensions: int) -> list[float]:
    if dimensions <= 0:
        raise ValueError("embedding dimension must be positive")
    if not values:
        return [0.0] * dimensions

    if len(values) == dimensions:
        projected = [float(item) for item in values]
    elif len(values) > dimensions:
        projected = [0.0] * dimensions
        for index, value in enumerate(values):
            projected[index % dimensions] += float(value)
    else:
        projected = [float(item) for item in values] + [0.0] * (dimensions - len(values))

    norm = math.sqrt(sum(item * item for item in projected))
    if norm == 0:
        return [0.0] * dimensions
    return [item / norm for item in projected]


def _deterministic_mock_embed(text: str, dimensions: int) -> list[float]:
    if dimensions <= 0:
        raise ValueError("embedding dimension must be positive")

    source = text.strip().encode("utf-8")
    if not source:
        return [0.0] * dimensions

    values: list[float] = []
    nonce = 0
    while len(values) < dimensions:
        block = sha256(source + nonce.to_bytes(4, "big", signed=False)).digest()
        for index in range(0, len(block), 4):
            piece = block[index : index + 4]
            if len(piece) < 4:
                continue
            number = int.from_bytes(piece, "big", signed=False)
            values.append((number / 4294967295.0) * 2.0 - 1.0)
            if len(values) >= dimensions:
                break
        nonce += 1
    return _project_and_normalize(values, dimensions)


def _local_provider() -> BaseEmbeddingProvider:
    if settings.local_embedding_backend == "sentence-transformers":
        return SentenceTransformersEmbeddingProvider()
    if settings.local_embedding_backend == "ollama":
        return OllamaEmbeddingProvider()
    raise RuntimeError("unsupported_local_embedding_backend")


def get_embedding_status() -> EmbeddingRuntimeStatus:
    return _embedding_status_store.snapshot()


def embed_text(text: str, dimensions: int | None = None) -> list[float]:
    target_dim = dimensions or settings.embedding_dimensions
    mock_provider = DeterministicMockEmbeddingProvider()
    if settings.embedding_mode == "mock":
        vector = mock_provider.embed(text, target_dim)
        _embedding_status_store.update(
            EmbeddingRuntimeStatus(
                mode="mock",
                configured_backend=settings.local_embedding_backend,
                provider=mock_provider.provider_name,
                model=mock_provider.model_name,
                availability="available",
                fallback_used=False,
                error=None,
            )
        )
        return vector

    try:
        provider = _local_provider()
        vector = provider.embed(text, target_dim)
        _embedding_status_store.update(
            EmbeddingRuntimeStatus(
                mode="local",
                configured_backend=settings.local_embedding_backend,
                provider=provider.provider_name,
                model=provider.model_name,
                availability="available",
                fallback_used=False,
                error=None,
            )
        )
        return vector
    except Exception as exc:
        vector = mock_provider.embed(text, target_dim)
        _embedding_status_store.update(
            EmbeddingRuntimeStatus(
                mode="local",
                configured_backend=settings.local_embedding_backend,
                provider=f"{mock_provider.provider_name}-fallback",
                model=mock_provider.model_name,
                availability="unavailable",
                fallback_used=True,
                error=_safe_embedding_error(exc),
            )
        )
        return vector


def cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    length = min(len(vec_a), len(vec_b))
    if length == 0:
        return 0.0
    return sum(vec_a[index] * vec_b[index] for index in range(length))

