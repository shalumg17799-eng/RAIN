"""The embedder interface, and a deterministic fake for tests and offline use.

A real embedding model plugs in behind `Embedder` later (a local model, or a gateway purpose). The
fake hashes words and word pairs into a fixed-size vector: it measures vocabulary overlap, not
meaning, but it is stable across runs and machines, which is what tests need.
"""

import hashlib
import math
from collections.abc import Sequence
from itertools import pairwise
from typing import Protocol

from insights.catalog.text import stems


class Embedder(Protocol):
    name: str
    dim: int

    def embed(self, texts: Sequence[str]) -> list[list[float]]: ...


class HashingEmbedder:
    name = "hashing-fake-1"

    def __init__(self, dim: int = 256) -> None:
        self.dim = dim

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        return [self._one(text) for text in texts]

    def _one(self, text: str) -> list[float]:
        words = stems(text)
        features = [*words, *(f"{a}_{b}" for a, b in pairwise(words))]
        vector = [0.0] * self.dim
        for feature in features:
            digest = hashlib.blake2b(feature.encode("utf-8"), digest_size=8).digest()
            bucket = int.from_bytes(digest[:4], "big") % self.dim
            sign = 1.0 if digest[4] & 1 else -1.0
            vector[bucket] += sign
        norm = math.sqrt(sum(x * x for x in vector))
        return [x / norm for x in vector] if norm else vector


def cosine(a: Sequence[float], b: Sequence[float]) -> float:
    """Cosine of two unit-or-zero vectors; zero when either is empty."""
    return sum(x * y for x, y in zip(a, b, strict=True))
