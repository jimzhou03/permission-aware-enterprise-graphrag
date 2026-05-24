from __future__ import annotations

import math
from hashlib import sha256

from app.core.config import get_settings


settings = get_settings()


def embed_text(text: str, dimensions: int | None = None) -> list[float]:
    dim = dimensions or settings.embedding_dimensions
    if dim <= 0:
        raise ValueError("embedding dimension must be positive")

    source = text.strip().encode("utf-8")
    if not source:
        return [0.0] * dim

    values: list[float] = []
    nonce = 0
    while len(values) < dim:
        block = sha256(source + nonce.to_bytes(4, "big", signed=False)).digest()
        for idx in range(0, len(block), 4):
            piece = block[idx : idx + 4]
            if len(piece) < 4:
                continue
            number = int.from_bytes(piece, "big", signed=False)
            values.append((number / 4294967295.0) * 2.0 - 1.0)
            if len(values) >= dim:
                break
        nonce += 1

    norm = math.sqrt(sum(item * item for item in values))
    if norm == 0:
        return [0.0] * dim
    return [item / norm for item in values]


def cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    length = min(len(vec_a), len(vec_b))
    if length == 0:
        return 0.0
    return sum(vec_a[idx] * vec_b[idx] for idx in range(length))

