# spotify2youtube/core/vector_db.py

from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct, VectorParams, Distance
import os
from typing import List, Optional, Dict, Any

# Initialize client
QDRANT = QdrantClient(
    url=os.getenv("QDRANT_URL", "http://localhost:6333"),
    api_key=os.getenv("QDRANT_API_KEY")
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
    filter: Optional[Dict] = None
) -> List[Dict[str, Any]]:
    """
    Search for similar vectors in the collection.
    
    Args:
        collection_name: Name of the collection
        query_vector: Vector to search for
        top_k: Number of results to return
        filter: Optional filter for the search
    
    Returns:
        List of search results with scores and payloads
    """
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
