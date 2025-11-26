"""Vector database configuration for Qdrant."""

import os
from qdrant_client.models import Distance

# Collection configuration
COLLECTION_NAME = os.getenv("QDRANT_COLLECTION", "music-tracks")
VECTOR_SIZE = 1536  # OpenAI text-embedding-ada-002 dimension

# Distance metric
DISTANCE_METRIC = Distance.COSINE

# HNSW Index configuration for optimal performance
HNSW_CONFIG = {
    "m": 16,  # Number of edges per node (higher = better recall, more memory)
    "ef_construct": 100,  # Construction quality (higher = better quality, slower indexing)
}

# Search configuration
MIN_SIMILARITY_THRESHOLD = float(os.getenv("VECTOR_MIN_SIMILARITY", "0.85"))
DEFAULT_TOP_K = int(os.getenv("VECTOR_TOP_K", "10"))

# Optimization thresholds
INDEXING_THRESHOLD = 20000  # Start using indexing after this many vectors
MEMMAP_THRESHOLD = 50000  # Use memory-mapped storage above this size
FULL_SCAN_THRESHOLD = 10000  # Use full scan below this size

# Embedding configuration
EMBEDDING_MODEL = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-ada-002")
EMBEDDING_BATCH_SIZE = int(os.getenv("EMBEDDING_BATCH_SIZE", "100"))

# Cache configuration
EMBEDDING_CACHE_SIZE = int(os.getenv("EMBEDDING_CACHE_SIZE", "1000"))
EMBEDDING_CACHE_TTL = int(os.getenv("EMBEDDING_CACHE_TTL", "86400"))  # 24 hours in seconds
