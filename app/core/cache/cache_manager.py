"""
Cache manager for handling cache piplines and operations.

User Query
    ↓
Cache Manager
    ↓
Exact Cache
    │
    ├── HIT → Response
    │
    └── MISS
          ↓
    Semantic Cache
          │
          ├── HIT → Response
          │
          └── MISS
                ↓
             RAG / LLM
             
Central cache manager.

Cache lookup order:
    1. Exact Cache
    2. Semantic Cache
    3. Cache Miss
             
"""

from app.core.cache.exact_cache import exact_cache
from app.core.cache.semantic_cache import semantic_cache
from app.core.monitoring.metrics import metrics
from app.core.monitoring.logging import get_logger

from langsmith import traceable

logger = get_logger(__name__)


class CacheManager:
    """Coordinates exact and semantic caching."""

    def __init__(self) -> None:
        self.exact_cache = exact_cache
        self.semantic_cache = semantic_cache

    """
    In this CacheManager we need to integrate the metrics:
    
    1- CACHE_REQUESTS_TOTAL
    this metric will be incremented every time a cache request is made, regardless of whether it is a hit or a miss. and it will add tags which are cache_type and result
    the cache_type will be either exact or semantic depending on which cache is being accessed, and the result will be either hit or miss depending on whether the cache returned a response or not.
    
    2- CACHE_LATENCY
    this metric will be used to measure the latency of the cache requests, in addition to operation whether it is a lookup or a store operation, and it will be a histogram metric that will record the time taken for each cache request, and it will also add tags which are cache_type
    
    3- CACHE_ERRORS_TOTAL
    this metric will be incremented every time a cache request fails due to an error, and it will add tags operation whcih could be lookup or store and which error_type, the error_type will be the type of the exception that was raised during the cache request.
    """

    @traceable
    async def get(self, query: str) -> tuple[bool, str, str | None, str | None]:
        """
        Look for a cached response.

        Returns:
            (is_cache, query, response, cache_type)
        """

        # 1. Try exact cache
        try:
            with metrics.track_cache_latency(cache_type="exact", operation="lookup"):
                response = await self.exact_cache.get(query)

            try:
                metrics.record_cache_result(
                    cache_type="exact",
                    result="hit" if response is not None else "miss",
                )
            except Exception:
                logger.exception(
                    "Failed to record cache result metric for exact cache"
                )
        except Exception as exe:
            try:
                metrics.record_cache_error(
                    operation="lookup", error_type=type(exe).__name__)
            except Exception:
                logger.exception(
                    "Failed to record cache error metric for exact cache"
                )
            raise

        if response is not None:
            return True, query, response, "exact"

        # 2. Try semantic cache
        try:
            with metrics.track_cache_latency(cache_type="semantic", operation="lookup"):
                response = await self.semantic_cache.get(query)

            try:
                metrics.record_cache_result(
                    cache_type="semantic",
                    result="hit" if response is not None else "miss",
                )
            except Exception:
                logger.exception(
                    "Failed to record cache result metric for semantic cache"
                )
        except Exception as exe:

            try:
                metrics.record_cache_error(
                    operation="lookup", error_type=type(exe).__name__)
            except Exception:
                logger.exception(
                    "Failed to record cache error metric for semantic cache"
                )
            raise

        if response is not None:
            return True, query, response, "semantic"

        # 3. Cache miss
        return False, query, None, None

    @traceable
    async def set(self, query: str, response: str) -> None:
        """
        Store the response in both caches.
        """
        try:
            with metrics.track_cache_latency(cache_type="exact", operation="store"):
                await self.exact_cache.set(query, response)
            with metrics.track_cache_latency(cache_type="semantic", operation="store"):
                await self.semantic_cache.set(query, response)
        except Exception as exe:
            try:
                metrics.record_cache_error(
                    operation="store", error_type=type(exe).__name__)
            except Exception:
                logger.exception(
                    "Failed to record cache error metric for store operation"
                )
            raise

    @property
    def stats(self) -> dict:
        """Return statistics for both caches."""

        return {
            "exact": self.exact_cache.stats,
            "semantic": self.semantic_cache.stats,
        }


"""
Then your LangSmith trace can conceptually become: 

API Request
│
├── security_check_input
│
├── cache_lookup
│   ├── exact cache
│   └── semantic cache
│
├── RAG retrieval
│
├── LLM call
│
├── cache_store
│
└── security_check_output
"""
