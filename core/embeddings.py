# spotify2youtube/core/embeddings.py

import os
import re
from functools import lru_cache
from openai import OpenAI
from dotenv import load_dotenv
from typing import List, Dict, Any
import logging

load_dotenv()

client = OpenAI()
logger = logging.getLogger(__name__)

# Import configuration
try:
    from config.vector_config import (
        EMBEDDING_MODEL,
        EMBEDDING_CACHE_SIZE,
        EMBEDDING_BATCH_SIZE
    )
except ImportError:
    # Fallback defaults if config not available
    EMBEDDING_MODEL = "text-embedding-ada-002"
    EMBEDDING_CACHE_SIZE = 1000
    EMBEDDING_BATCH_SIZE = 100


def normalize_text(text: str) -> str:
    """
    Normalize text for consistent embeddings.

    Args:
        text: Text to normalize

    Returns:
        Normalized text
    """
    if not text:
        return ""

    # Convert to lowercase
    text = text.lower()

    # Remove extra whitespace
    text = re.sub(r'\s+', ' ', text.strip())

    # Remove special characters but keep alphanumeric, spaces, and hyphens
    text = re.sub(r'[^a-z0-9\s\-]', '', text)

    return text


@lru_cache(maxsize=EMBEDDING_CACHE_SIZE)
def get_embedding_cached(text: str, model: str = EMBEDDING_MODEL) -> tuple:
    """
    Get embedding with LRU caching. Returns tuple for hashability.

    Args:
        text: Text to embed
        model: OpenAI embedding model to use

    Returns:
        Tuple of floats representing the embedding
    """
    try:
        response = client.embeddings.create(model=model, input=text)
        embedding = response.data[0].embedding
        logger.debug(f"Generated embedding for text: {text[:50]}...")
        return tuple(embedding)  # Convert to tuple for caching
    except Exception as e:
        logger.error(f"Error getting embedding: {e}")
        raise


def get_embedding(text: str, model: str = EMBEDDING_MODEL) -> List[float]:
    """
    Get embedding for a text using OpenAI's embedding model with caching.

    Args:
        text: Text to embed
        model: OpenAI embedding model to use

    Returns:
        List of floats representing the embedding
    """
    # Normalize text before caching to maximize cache hits
    normalized_text = normalize_text(text)

    if not normalized_text:
        logger.warning("Empty text after normalization, returning zero vector")
        return [0.0] * 1536

    # Get cached embedding and convert back to list
    embedding_tuple = get_embedding_cached(normalized_text, model)
    return list(embedding_tuple)


def get_track_embedding(track_data: Dict[str, Any]) -> List[float]:
    """
    Get embedding for a track by combining its metadata with improved normalization.

    Args:
        track_data: Dictionary containing track metadata

    Returns:
        List of floats representing the embedding
    """
    # Get fields with fallbacks and handle different platform schemas
    title = (
        track_data.get('title') or
        track_data.get('name') or
        track_data.get('track_name') or
        'Unknown Track'
    )

    # Handle artist field variations
    artist_data = track_data.get('artists') or track_data.get('artist')
    if isinstance(artist_data, list):
        # Spotify format: [{"name": "Artist"}]
        artist = artist_data[0].get('name') if artist_data else 'Unknown Artist'
    elif isinstance(artist_data, str):
        artist = artist_data
    else:
        artist = 'Unknown Artist'

    # Handle album field variations
    album_data = track_data.get('album')
    if isinstance(album_data, dict):
        # Spotify format: {"name": "Album"}
        album = album_data.get('name')
    elif isinstance(album_data, str):
        album = album_data
    else:
        album = None

    # Normalize all fields
    title = normalize_text(title)
    artist = normalize_text(artist)

    # Build text for embedding
    text = f"{title} - {artist}"

    if album:
        album = normalize_text(album)
        text += f" ({album})"

    # Add genres if available
    if genres := track_data.get('genres'):
        if isinstance(genres, list) and genres:
            normalized_genres = [normalize_text(g) for g in genres if g]
            if normalized_genres:
                text += f" genres {' '.join(normalized_genres)}"

    logger.debug(f"Track embedding text: {text}")
    return get_embedding(text)


def batch_get_embeddings(texts: List[str], batch_size: int = EMBEDDING_BATCH_SIZE) -> List[List[float]]:
    """
    Get embeddings for multiple texts in batches with normalization.

    Args:
        texts: List of texts to embed
        batch_size: Number of texts to process in each batch

    Returns:
        List of embeddings
    """
    # Normalize all texts first
    normalized_texts = [normalize_text(text) for text in texts]

    embeddings = []
    for i in range(0, len(normalized_texts), batch_size):
        batch = normalized_texts[i:i + batch_size]
        try:
            response = client.embeddings.create(
                model=EMBEDDING_MODEL,
                input=batch
            )
            batch_embeddings = [item.embedding for item in response.data]
            embeddings.extend(batch_embeddings)
            logger.debug(f"Processed batch {i//batch_size + 1}, total: {len(embeddings)}")
        except Exception as e:
            logger.error(f"Error getting batch embeddings: {e}")
            raise

    return embeddings
