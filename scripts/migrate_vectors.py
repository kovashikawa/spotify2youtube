# spotify2youtube/scripts/migrate_vectors.py

import os
import sys
from pathlib import Path
import logging
from typing import List, Dict, Any
from google.cloud import firestore
from qdrant_client.models import PointStruct

# Add project root to Python path
project_root = str(Path(__file__).parent.parent)
sys.path.append(project_root)

from core.vector_db import init_collection, upsert_vectors
from core.embeddings import get_track_embedding
from database.firestore_ops import get_all_tracks

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants
COLLECTION_NAME = "spotify-tracks"
BATCH_SIZE = 500


def create_point_struct(track_data: Dict[str, Any]) -> PointStruct:
    """Create a Qdrant point structure from track data."""
    embedding = get_track_embedding(track_data)
    
    return PointStruct(
        id=track_data["doc_id"],
        vector=embedding,
        payload={
            "spotify_id": track_data.get("spotify_id"),
            "track_name": track_data.get("track_name"),
            "artist": track_data.get("artist"),
            "album": track_data.get("album"),
            "genres": track_data.get("genres", []),
            "duration_ms": track_data.get("duration_ms"),
            "popularity": track_data.get("popularity"),
            "user_id": track_data.get("user_id"),
            "playlist_id": track_data.get("playlist_id")
        }
    )

def mark_as_indexed(doc_id: str) -> None:
    """Mark a document as indexed in Firestore."""
    db = firestore.Client()
    doc_ref = db.collection("tracks").document(doc_id)
    doc_ref.update({"vector_indexed": True})

def main():
    """Main migration function."""
    try:
        # Initialize collection
        logger.info("Initializing Qdrant collection...")
        init_collection(COLLECTION_NAME)
        
        # Get unindexed tracks
        logger.info("Fetching unindexed tracks from Firestore...")
        tracks = get_all_tracks()
        logger.info(f"Found {len(tracks)} tracks to index")
        
        # Process in batches
        batch = []
        for i, track in enumerate(tracks, 1):
            try:
                point = create_point_struct(track)
                batch.append(point)
                
                # Process batch when it reaches BATCH_SIZE
                if len(batch) >= BATCH_SIZE:
                    logger.info(f"Processing batch of {len(batch)} tracks...")
                    upsert_vectors(COLLECTION_NAME, batch)
                    
                    # Mark documents as indexed
                    for point in batch:
                        mark_as_indexed(point.id)
                    
                    batch = []
                    logger.info(f"Processed {i}/{len(tracks)} tracks")
            
            except Exception as e:
                logger.error(f"Error processing track {track.get('track_name')}: {e}")
                continue
        
        # Process remaining tracks
        if batch:
            logger.info(f"Processing final batch of {len(batch)} tracks...")
            upsert_vectors(COLLECTION_NAME, batch)
            
            # Mark documents as indexed
            for point in batch:
                mark_as_indexed(point.id)
        
        logger.info("Migration completed successfully!")
    
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
