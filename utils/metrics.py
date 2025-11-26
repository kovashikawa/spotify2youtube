"""
Metrics and monitoring utilities for vector database operations.

This module provides simple counters and timers for tracking:
- Vector search performance
- Cache hit rates
- Embedding generation costs
- Collection sizes
"""

import time
import logging
from functools import wraps
from typing import Dict, Any, Optional
from collections import defaultdict

logger = logging.getLogger(__name__)


class Metrics:
    """Simple metrics collector for vector DB operations."""

    def __init__(self):
        self.counters = defaultdict(int)
        self.timers = defaultdict(list)
        self.gauges = {}

    def increment(self, metric_name: str, value: int = 1) -> None:
        """Increment a counter metric."""
        self.counters[metric_name] += value
        logger.debug(f"Metric {metric_name}: {self.counters[metric_name]}")

    def record_time(self, metric_name: str, duration: float) -> None:
        """Record a timing measurement in seconds."""
        self.timers[metric_name].append(duration)
        logger.debug(f"Timing {metric_name}: {duration:.3f}s")

    def set_gauge(self, metric_name: str, value: Any) -> None:
        """Set a gauge value."""
        self.gauges[metric_name] = value
        logger.debug(f"Gauge {metric_name}: {value}")

    def get_summary(self) -> Dict[str, Any]:
        """Get summary of all metrics."""
        summary = {
            "counters": dict(self.counters),
            "gauges": dict(self.gauges),
            "timers": {}
        }

        # Calculate timer statistics
        for name, times in self.timers.items():
            if times:
                summary["timers"][name] = {
                    "count": len(times),
                    "total": sum(times),
                    "avg": sum(times) / len(times),
                    "min": min(times),
                    "max": max(times)
                }

        return summary

    def log_summary(self) -> None:
        """Log a summary of all metrics."""
        summary = self.get_summary()

        logger.info("=== Metrics Summary ===")
        logger.info(f"Counters: {summary['counters']}")
        logger.info(f"Gauges: {summary['gauges']}")

        for timer_name, stats in summary['timers'].items():
            logger.info(
                f"Timer {timer_name}: "
                f"count={stats['count']}, "
                f"avg={stats['avg']:.3f}s, "
                f"min={stats['min']:.3f}s, "
                f"max={stats['max']:.3f}s"
            )

    def reset(self) -> None:
        """Reset all metrics."""
        self.counters.clear()
        self.timers.clear()
        self.gauges.clear()
        logger.info("Metrics reset")


# Global metrics instance
_metrics = Metrics()


def get_metrics() -> Metrics:
    """Get the global metrics instance."""
    return _metrics


def timer(metric_name: str):
    """
    Decorator to time function execution and record to metrics.

    Usage:
        @timer("embedding_generation")
        def get_embedding(text):
            ...
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                duration = time.time() - start_time
                _metrics.record_time(metric_name, duration)
        return wrapper
    return decorator


def count(metric_name: str, value: int = 1):
    """
    Decorator to count function calls.

    Usage:
        @count("vector_search_total")
        def search_similar(...):
            ...
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            _metrics.increment(metric_name, value)
            return func(*args, **kwargs)
        return wrapper
    return decorator


# Specific metrics tracking functions
def track_vector_search(
    total_results: int,
    filtered_results: int,
    threshold: float,
    duration: float
) -> None:
    """Track vector search metrics."""
    _metrics.increment("vector_search_total")
    _metrics.increment("vector_search_results", total_results)
    _metrics.increment("vector_search_filtered", filtered_results)
    _metrics.record_time("vector_search_duration", duration)

    if filtered_results > 0:
        _metrics.increment("vector_search_hits")

    logger.info(
        f"Vector search: {filtered_results}/{total_results} "
        f"above threshold {threshold} in {duration:.3f}s"
    )


def track_cache_access(hit: bool) -> None:
    """Track cache hit/miss."""
    if hit:
        _metrics.increment("cache_hits")
    else:
        _metrics.increment("cache_misses")

    total = _metrics.counters["cache_hits"] + _metrics.counters["cache_misses"]
    if total > 0:
        hit_rate = _metrics.counters["cache_hits"] / total
        _metrics.set_gauge("cache_hit_rate", hit_rate)


def track_embedding_generation(text_length: int, duration: float, cached: bool) -> None:
    """Track embedding generation metrics."""
    if cached:
        _metrics.increment("embedding_cache_hits")
    else:
        _metrics.increment("embedding_api_calls")
        _metrics.increment("embedding_tokens_estimated", text_length // 4)  # Rough estimate

    _metrics.record_time("embedding_generation", duration)


def track_collection_size(collection_name: str, size: int) -> None:
    """Track vector collection size."""
    metric_name = f"collection_size_{collection_name}"
    _metrics.set_gauge(metric_name, size)
    logger.info(f"Collection '{collection_name}' size: {size} vectors")


def get_cache_statistics() -> Dict[str, Any]:
    """Get cache performance statistics."""
    hits = _metrics.counters.get("cache_hits", 0)
    misses = _metrics.counters.get("cache_misses", 0)
    total = hits + misses

    return {
        "hits": hits,
        "misses": misses,
        "total": total,
        "hit_rate": hits / total if total > 0 else 0.0
    }


def get_embedding_statistics() -> Dict[str, Any]:
    """Get embedding generation statistics."""
    api_calls = _metrics.counters.get("embedding_api_calls", 0)
    cache_hits = _metrics.counters.get("embedding_cache_hits", 0)
    total = api_calls + cache_hits
    tokens = _metrics.counters.get("embedding_tokens_estimated", 0)

    return {
        "api_calls": api_calls,
        "cache_hits": cache_hits,
        "total": total,
        "cache_hit_rate": cache_hits / total if total > 0 else 0.0,
        "estimated_tokens": tokens,
        "estimated_cost_usd": tokens * 0.0001 / 1000  # $0.0001 per 1K tokens
    }


def get_vector_search_statistics() -> Dict[str, Any]:
    """Get vector search statistics."""
    total_searches = _metrics.counters.get("vector_search_total", 0)
    total_hits = _metrics.counters.get("vector_search_hits", 0)
    total_results = _metrics.counters.get("vector_search_results", 0)
    filtered_results = _metrics.counters.get("vector_search_filtered", 0)

    durations = _metrics.timers.get("vector_search_duration", [])
    avg_duration = sum(durations) / len(durations) if durations else 0.0

    return {
        "total_searches": total_searches,
        "searches_with_results": total_hits,
        "hit_rate": total_hits / total_searches if total_searches > 0 else 0.0,
        "total_results_returned": total_results,
        "results_above_threshold": filtered_results,
        "avg_duration_seconds": avg_duration
    }
