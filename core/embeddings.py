# spotify2youtube/core/embeddings.py

import os
from openai import OpenAI

from dotenv import load_dotenv
load_dotenv()

client = OpenAI()
from typing import List, Dict, Any
import logging

logger = logging.getLogger(__name__)

# Initialize OpenAI client

def get_embedding(text: str, model: str = "text-embedding-ada-002") -> List[float]:
    """
    Get embedding for a text using OpenAI's embedding model.
    
    Args:
        text: Text to embed
        model: OpenAI embedding model to use
    
    Returns:
        List of floats representing the embedding
    """
    try:
        response = client.embeddings.create(model=model,
        input=text)
        return response.data[0].embedding
    except Exception as e:
        logger.error(f"Error getting embedding: {e}")
        raise

def get_track_embedding(track_data: Dict[str, Any]) -> List[float]:
    """
    Get embedding for a track by combining its metadata.
    
    Args:
        track_data: Dictionary containing track metadata
    
    Returns:
        List of floats representing the embedding
    """
    # Combine track metadata into a single text
    text = f"{track_data.get('title', '')} - {track_data.get('artist', '')}"

    # Add album if available
    if 'album' in track_data:
        text += f" ({track_data['album']})"

    # Add any additional metadata that might be useful
    if 'genres' in track_data:
        text += f" Genres: {', '.join(track_data['genres'])}"

    return get_embedding(text)

def batch_get_embeddings(texts: List[str], batch_size: int = 100) -> List[List[float]]:
    """
    Get embeddings for multiple texts in batches.
    
    Args:
        texts: List of texts to embed
        batch_size: Number of texts to process in each batch
    
    Returns:
        List of embeddings
    """
    embeddings = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        try:
            response = client.embeddings.create(model="text-embedding-ada-002",
            input=batch)
            batch_embeddings = [item["embedding"] for item in response.data]
            embeddings.extend(batch_embeddings)
        except Exception as e:
            logger.error(f"Error getting batch embeddings: {e}")
            raise

    return embeddings 