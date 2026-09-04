from __future__ import annotations

import math
from functools import lru_cache
from typing import Iterable


class EmbeddingUnavailable(RuntimeError):
    pass


@lru_cache(maxsize=2)
def _load_model(model_name: str):
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:
        raise EmbeddingUnavailable(
            "sentence-transformers is not installed. Install requirements-ml.txt or disable semantic embeddings."
        ) from exc
    return SentenceTransformer(model_name)


def embed_texts(texts: list[str], model_name: str) -> list[list[float]]:
    if not texts:
        return []
    model = _load_model(model_name)
    vectors = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
    return [[float(value) for value in vector] for vector in vectors]


def cosine_similarity(a: Iterable[float], b: Iterable[float]) -> float:
    av = [float(x) for x in a]
    bv = [float(x) for x in b]
    if len(av) != len(bv) or not av:
        return -1.0
    dot = sum(x * y for x, y in zip(av, bv))
    an = math.sqrt(sum(x * x for x in av))
    bn = math.sqrt(sum(y * y for y in bv))
    if an == 0.0 or bn == 0.0:
        return -1.0
    return dot / (an * bn)
