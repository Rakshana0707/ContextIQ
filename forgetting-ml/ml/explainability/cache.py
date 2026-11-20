"""
cache.py

Thread-safe, version-aware LRU cache for prediction explanations (Phase 2.7).
Prevents redundant SHAP recalculations on repeated queries.

Keying:
SHA-256(model_name + model_version + explanation_version + feature_schema_version + normalized_features)
"""

from __future__ import annotations

import hashlib
import json
import threading
from collections import OrderedDict
from typing import Any, Dict, Optional, Tuple


class ExplanationCache:
    """Thread-safe bounded LRU cache for prediction explanations."""

    def __init__(self, max_size: int = 1024):
        self.max_size = max_size
        self._cache: OrderedDict[str, Dict[str, Any]] = OrderedDict()
        self._lock = threading.Lock()
        self._hits: int = 0
        self._misses: int = 0
        self._evictions: int = 0

    def compute_cache_key(
        self,
        model_name: str,
        model_version: str,
        explanation_version: str,
        raw_features: Dict[str, Any],
    ) -> str:
        """
        Generates deterministic SHA-256 hash key sensitive to model identity,
        explanation version, and exact input feature values.
        """
        # Normalize features into sorted key-value pairs
        normalized_pairs = []
        for k in sorted(raw_features.keys()):
            v = raw_features[k]
            if isinstance(v, float):
                v_repr = f"{v:.5f}"
            else:
                v_repr = str(v)
            normalized_pairs.append((k, v_repr))

        envelope = {
            "model_name": model_name,
            "model_version": model_version,
            "explanation_version": explanation_version,
            "features": normalized_pairs,
        }
        envelope_str = json.dumps(envelope, sort_keys=True)
        return hashlib.sha256(envelope_str.encode("utf-8")).hexdigest()

    def get(self, key: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            if key in self._cache:
                self._hits += 1
                self._cache.move_to_end(key)
                return self._cache[key]
            self._misses += 1
            return None

    def put(self, key: str, value: Dict[str, Any]) -> None:
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
                self._cache[key] = value
                return

            if len(self._cache) >= self.max_size:
                self._cache.popitem(last=False)  # Evict oldest LRU item
                self._evictions += 1

            self._cache[key] = value

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()
            self._hits = 0
            self._misses = 0
            self._evictions = 0

    @property
    def stats(self) -> Dict[str, Any]:
        with self._lock:
            total = self._hits + self._misses
            hit_rate = (self._hits / total) if total > 0 else 0.0
            return {
                "size": len(self._cache),
                "max_size": self.max_size,
                "hits": self._hits,
                "misses": self._misses,
                "evictions": self._evictions,
                "hit_rate": round(hit_rate, 4),
            }


# Process-wide global explanation cache singleton
GLOBAL_EXPLANATION_CACHE = ExplanationCache(max_size=2048)
