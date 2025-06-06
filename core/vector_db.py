# spotify2youtube/core/vector_db.py

import os
import uuid
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct, VectorParams, Distance, Filter, FieldCondition
from typing import List, Optional, Dict, Any
from core.embeddings import get_track_embedding

# Initialize Qdrant client
QDRANT = QdrantClient(
    host=os.getenv("QDRANT_HOST", "localhost"),
    port=int(os.getenv("QDRANT_PORT", "6333")),
    api_key=os.getenv("QDRANT_API_KEY"),
    prefer_grpc=False,  # Use HTTP instead of gRPC
    timeout=10.0,  # Add timeout
    https=False  # Force HTTP protocol
)

def init_collection(collection_name: str, vector_size: int = 1536) -> None:
    """Initialize or recreate a Qdrant collection with the specified vector size."""
    QDRANT.recreate_collection(
        collection_name=collection_name,
        vectors_config=VectorParams(
            size=vector_size,
            distance=Distance.COSINE
        )
    )

def upsert_vectors(collection_name: str, points: List[PointStruct]) -> None:
    """
    Upsert vectors and their metadata into Qdrant.
    
    Args:
        collection_name: Name of the collection
        points: List of PointStruct objects containing id, vector, and payload
    """
    QDRANT.upsert(
        collection_name=collection_name,
        points=points
    )

def search_similar(
    collection_name: str,
    query_vector: List[float],
    top_k: int = 10,
    platform: Optional[str] = None,
    filter: Optional[Filter] = None
) -> List[Dict[str, Any]]:
    """
    Search for similar vectors in the collection.
    
    Args:
        collection_name: Name of the collection
        query_vector: Vector to search for
        top_k: Number of results to return
        platform: Optional platform filter ('spotify' or 'youtube')
        filter: Optional additional filter for the search
    
    Returns:
        List of search results with scores and payloads
    """
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

    return QDRANT.search(
        collection_name=collection_name,
        query_vector=query_vector,
        limit=top_k,
        query_filter=filter
    )

def get_collection_info(collection_name: str) -> Dict[str, Any]:
    """Get information about a collection."""
    return QDRANT.get_collection(collection_name=collection_name)

def delete_collection(collection_name: str) -> None:
    """Delete a collection."""
    QDRANT.delete_collection(collection_name=collection_name)

def create_point_struct(track_data: Dict[str, Any]) -> PointStruct:
    """
    Create a Qdrant point structure from track data.
    
    Args:
        track_data: Dictionary containing track metadata
    
    Returns:
        PointStruct with UUID id, embedding vector, and payload metadata
    """
    platform = track_data.get("platform", "spotify")
    
    # Generate a UUID v5 based on platform and track_id for consistent IDs
    unique_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{platform}_{track_data['track_id']}"))
    
    # Get or generate embedding
    vector = track_data.get("embedding")
    if not isinstance(vector, list):
        vector = get_track_embedding(track_data)
    
    # Base payload with common fields
    payload = {
        "platform": platform,
        "track_id": track_data.get("track_id"),
        "track_name": track_data.get("track_name"),
        "artist": track_data.get("artist"),
        "album": track_data.get("album"),
        "genres": track_data.get("genres", []),
        "duration_ms": track_data.get("duration_ms"),
        "popularity": track_data.get("popularity"),
        "user_id": track_data.get("user_id"),
        "playlist_id": track_data.get("playlist_id"),
        "original_track_id": track_data.get("track_id")  # Store original ID for reference
    }
    
    # Add platform-specific fields
    if platform == "spotify":
        payload.update({
            "spotify_uri": track_data.get("uri"),
            "spotify_url": track_data.get("external_urls", {}).get("spotify"),
            "spotify_preview_url": track_data.get("preview_url")
        })
    elif platform == "youtube":
        payload.update({
            "youtube_url": f"https://youtube.com/watch?v={track_data.get('track_id')}",
            "youtube_channel": track_data.get("channel_title"),
            "youtube_views": track_data.get("view_count")
        })
    
    return PointStruct(
        id=unique_id,
        vector=vector,
        payload=payload
    )
