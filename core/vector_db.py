# spotify2youtube/core/vector_db.py

import os
import uuid
import logging
from qdrant_client import QdrantClient
import time
from qdrant_client.models import (
    PointStruct, VectorParams, Distance, Filter, FieldCondition,
    HnswConfigDiff, OptimizersConfigDiff
)
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, validator, ValidationError

logger = logging.getLogger(__name__)

# Import metrics
try:
    from utils.metrics import track_vector_search, track_collection_size
except ImportError:
    # Fallback if metrics not available
    def track_vector_search(*args, **kwargs): pass
    def track_collection_size(*args, **kwargs): pass

# Import configuration
try:
    from config.vector_config import (
        COLLECTION_NAME,
        VECTOR_SIZE,
        DISTANCE_METRIC,
        HNSW_CONFIG,
        MIN_SIMILARITY_THRESHOLD,
        DEFAULT_TOP_K,
        INDEXING_THRESHOLD,
        MEMMAP_THRESHOLD,
        FULL_SCAN_THRESHOLD
    )
except ImportError:
    # Fallback defaults
    COLLECTION_NAME = "music-tracks"
    VECTOR_SIZE = 1536
    DISTANCE_METRIC = Distance.COSINE
    HNSW_CONFIG = {"m": 16, "ef_construct": 100}
    MIN_SIMILARITY_THRESHOLD = 0.85
    DEFAULT_TOP_K = 10
    INDEXING_THRESHOLD = 20000
    MEMMAP_THRESHOLD = 50000
    FULL_SCAN_THRESHOLD = 10000

# Lazy-loaded client
_qdrant_client = None


def get_qdrant_client() -> QdrantClient:
    """
    Get or create Qdrant client with connection error handling.

    Returns:
        QdrantClient instance

    Raises:
        ConnectionError: If unable to connect to Qdrant
    """
    global _qdrant_client

    if _qdrant_client is None:
        try:
            _qdrant_client = QdrantClient(
                host=os.getenv("QDRANT_HOST", "localhost"),
                port=int(os.getenv("QDRANT_PORT", "6333")),
                api_key=os.getenv("QDRANT_API_KEY"),
                prefer_grpc=False,
                timeout=10.0,
                https=False
            )
            # Test connection
            _qdrant_client.get_collections()
            logger.info("Successfully connected to Qdrant")
        except Exception as e:
            logger.error(f"Failed to connect to Qdrant: {e}")
            raise ConnectionError(f"Qdrant connection failed: {e}")

    return _qdrant_client


# Input validation models
class TrackDataValidator(BaseModel):
    """Pydantic model for validating track data."""
    platform: str
    track_id: str
    title: Optional[str] = None
    name: Optional[str] = None
    track_name: Optional[str] = None
    artist: Optional[Any] = None
    artists: Optional[Any] = None

    @validator('platform')
    def validate_platform(cls, v):
        if v not in ['spotify', 'youtube']:
            raise ValueError(f"Invalid platform: {v}. Must be 'spotify' or 'youtube'")
        return v

    @validator('track_id')
    def validate_track_id(cls, v):
        if not v or not str(v).strip():
            raise ValueError("track_id cannot be empty")
        return v

    class Config:
        extra = 'allow'  # Allow additional fields


def init_collection(
    collection_name: str = COLLECTION_NAME,
    vector_size: int = VECTOR_SIZE
) -> None:
    """
    Initialize or recreate a Qdrant collection with optimized HNSW parameters.

    Args:
        collection_name: Name of the collection
        vector_size: Dimension of vectors (default: 1536 for ada-002)
    """
    client = get_qdrant_client()

    try:
        client.recreate_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(
                size=vector_size,
                distance=DISTANCE_METRIC,
                hnsw_config=HnswConfigDiff(
                    m=HNSW_CONFIG["m"],
                    ef_construct=HNSW_CONFIG["ef_construct"],
                    full_scan_threshold=FULL_SCAN_THRESHOLD
                )
            ),
            optimizers_config=OptimizersConfigDiff(
                indexing_threshold=INDEXING_THRESHOLD,
                memmap_threshold=MEMMAP_THRESHOLD
            )
        )
        logger.info(f"Collection '{collection_name}' initialized with HNSW config: {HNSW_CONFIG}")
    except Exception as e:
        logger.error(f"Failed to initialize collection '{collection_name}': {e}")
        raise


def upsert_vectors(
    collection_name: str,
    points: List[PointStruct],
    batch_size: int = 100
) -> None:
    """
    Upsert vectors and their metadata into Qdrant with batching.

    Args:
        collection_name: Name of the collection
        points: List of PointStruct objects containing id, vector, and payload
        batch_size: Number of points to upsert per batch
    """
    client = get_qdrant_client()

    try:
        # Process in batches for large uploads
        for i in range(0, len(points), batch_size):
            batch = points[i:i + batch_size]
            client.upsert(
                collection_name=collection_name,
                points=batch
            )
            logger.debug(f"Upserted batch {i//batch_size + 1}: {len(batch)} points")

        logger.info(f"Successfully upserted {len(points)} vectors to '{collection_name}'")
    except Exception as e:
        logger.error(f"Failed to upsert vectors to '{collection_name}': {e}")
        raise


def search_similar(
    collection_name: str,
    query_vector: List[float],
    top_k: int = DEFAULT_TOP_K,
    platform: Optional[str] = None,
    filter: Optional[Filter] = None,
    min_score: float = MIN_SIMILARITY_THRESHOLD
) -> List[Dict[str, Any]]:
    """
    Search for similar vectors in the collection with score threshold filtering.

    Args:
        collection_name: Name of the collection
        query_vector: Vector to search for
        top_k: Number of results to return
        platform: Optional platform filter ('spotify' or 'youtube')
        filter: Optional additional filter for the search
        min_score: Minimum similarity score threshold (0.0-1.0)

    Returns:
        List of search results with scores and payloads above threshold
    """
    client = get_qdrant_client()

    # Create platform filter if specified
    if platform:
        platform_filter = Filter(
            must=[
                FieldCondition(
                    key="platform",
                    match={"value": platform}
                )
            ]
        )
        # Combine with existing filter if any
        if filter:
            filter = Filter(
                must=[
                    platform_filter.must[0],
                    *filter.must
                ]
            )
        else:
            filter = platform_filter

    try:
        results = client.search(
            collection_name=collection_name,
            query_vector=query_vector,
            limit=top_k,
            query_filter=filter
        )

        # Filter by minimum score
        filtered_results = [r for r in results if r.score >= min_score]

        # Log statistics
        logger.info(
            f"Vector search in '{collection_name}': "
            f"{len(filtered_results)}/{len(results)} results above threshold {min_score}"
        )

        return filtered_results

    except Exception as e:
        logger.error(f"Vector search failed in '{collection_name}': {e}")
        raise


def get_collection_info(collection_name: str) -> Dict[str, Any]:
    """
    Get information about a collection.

    Args:
        collection_name: Name of the collection

    Returns:
        Collection metadata
    """
    client = get_qdrant_client()
    try:
        info = client.get_collection(collection_name=collection_name)
        logger.debug(f"Retrieved info for collection '{collection_name}'")
        return info
    except Exception as e:
        logger.error(f"Failed to get collection info for '{collection_name}': {e}")
        raise


def delete_collection(collection_name: str) -> None:
    """
    Delete a collection.

    Args:
        collection_name: Name of the collection to delete
    """
    client = get_qdrant_client()
    try:
        client.delete_collection(collection_name=collection_name)
        logger.info(f"Deleted collection '{collection_name}'")
    except Exception as e:
        logger.error(f"Failed to delete collection '{collection_name}': {e}")
        raise


def create_point_struct(track_data: Dict[str, Any]) -> PointStruct:
    """
    Create a Qdrant point structure from track data with validation.

    Args:
        track_data: Dictionary containing track metadata

    Returns:
        PointStruct with UUID id, embedding vector, and payload metadata

    Raises:
        ValidationError: If track_data is invalid
        ValueError: If platform is unsupported
    """
    # Validate input
    try:
        validated_data = TrackDataValidator(**track_data)
    except ValidationError as e:
        logger.error(f"Track data validation failed: {e}")
        raise

    platform = validated_data.platform

    # Ensure we have a track_id
    track_id = validated_data.track_id
    if not track_id:
        raise ValueError("track_id is required")

    # Generate a UUID v5 based on platform and track_id for consistent IDs
    unique_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{platform}_{track_id}"))

    # Get or generate embedding
    from core.embeddings import get_track_embedding
    vector = track_data.get("embedding")
    if not isinstance(vector, list):
        try:
            vector = get_track_embedding(track_data)
        except Exception as e:
            logger.error(f"Failed to generate embedding for track {track_id}: {e}")
            raise

    # Extract track data based on platform
    if platform == "spotify":
        # Spotify track data structure
        track_name = track_data.get("name") or track_data.get("track_name")
        artist = track_data.get("artists", [{}])[0].get("name") if isinstance(track_data.get("artists"), list) else track_data.get("artist")
        album = track_data.get("album", {}).get("name") if isinstance(track_data.get("album"), dict) else track_data.get("album")
        duration_ms = track_data.get("duration_ms")
        popularity = track_data.get("popularity")
        uri = track_data.get("uri")
        external_urls = track_data.get("external_urls", {})
        preview_url = track_data.get("preview_url")

        # Base payload with common fields
        payload = {
            "platform": platform,
            "track_id": track_id,
            "track_name": track_name,
            "artist": artist,
            "album": album,
            "genres": track_data.get("genres", []),
            "duration_ms": duration_ms,
            "popularity": popularity,
            "user_id": track_data.get("user_id"),
            "playlist_id": track_data.get("playlist_id"),
            "original_track_id": track_id,
            "spotify_uri": uri,
            "spotify_url": external_urls.get("spotify"),
            "spotify_preview_url": preview_url
        }

    elif platform == "youtube":
        # YouTube track data structure
        track_name = track_data.get("title") or track_data.get("track_name")
        artist = track_data.get("channel_title") or track_data.get("artist")
        duration_ms = track_data.get("duration_ms") or track_data.get("duration")
        view_count = track_data.get("view_count")

        # Base payload with common fields
        payload = {
            "platform": platform,
            "track_id": track_id,
            "track_name": track_name,
            "artist": artist,
            "album": None,  # YouTube doesn't have album concept
            "genres": [],   # YouTube doesn't have genres
            "duration_ms": duration_ms,
            "popularity": view_count,  # Use view count as popularity metric
            "user_id": track_data.get("user_id"),
            "playlist_id": track_data.get("playlist_id"),
            "original_track_id": track_id,
            "youtube_url": f"https://youtube.com/watch?v={track_id}",
            "youtube_channel": track_data.get("channel_title"),
            "youtube_views": view_count
        }

    else:
        raise ValueError(f"Unsupported platform: {platform}")

    # Clean up payload by removing None values
    payload = {k: v for k, v in payload.items() if v is not None}

    logger.debug(f"Created point struct for {platform} track: {track_name}")

    return PointStruct(
        id=unique_id,
        vector=vector,
        payload=payload
    )


def update_payloads(collection_name: str, points: List[PointStruct]) -> None:
    """
    Update only the payload data for existing points without modifying their vectors.

    Args:
        collection_name: Name of the collection
        points: List of PointStruct objects containing id and updated payload
    """
    client = get_qdrant_client()

    try:
        # Extract just the IDs and payloads for the update
        for point in points:
            client.set_payload(
                collection_name=collection_name,
                payload=point.payload,
                points=[point.id]
            )

        logger.info(f"Successfully updated {len(points)} payloads in '{collection_name}'")
    except Exception as e:
        logger.error(f"Failed to update payloads in '{collection_name}': {e}")
        raise
