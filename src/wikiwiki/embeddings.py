from __future__ import annotations

import numpy as np


MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
_model = None


def model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer

        _model = SentenceTransformer(MODEL_NAME)
    return _model


def encode(texts: list[str]) -> list[bytes]:
    vectors = model().encode(texts, normalize_embeddings=True)
    return [np.asarray(vector, dtype=np.float32).tobytes() for vector in vectors]


def query(text: str) -> bytes:
    return encode([text])[0]


def cosine(blob: bytes, vector: bytes) -> float:
    left = np.frombuffer(blob, dtype=np.float32)
    right = np.frombuffer(vector, dtype=np.float32)
    return float(np.dot(left, right))

