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

from core.vector_db import init_collection, upsert_vectors, create_point_struct
from database.firestore_ops import get_all_tracks

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants
COLLECTION_NAME = "music-tracks"  # Changed to be platform-agnostic
BATCH_SIZE = 10

def get_firestore_client():
    """Get Firestore client with proper credentials."""
    # Try to find credentials in different locations
    credential_paths = [
        os.path.join(project_root, "credentials", "service_account.json"),  # Local development
        "/opt/airflow/credentials/service_account.json",  # Airflow container
        os.getenv("GOOGLE_APPLICATION_CREDENTIALS")  # Environment variable
    ]
    
    for path in credential_paths:
        if path and os.path.exists(path):
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = path
            return firestore.Client()
    
    raise FileNotFoundError(
        "Firestore credentials not found. Please ensure service_account.json exists in one of these locations:\n" +
        "\n".join(f"- {path}" for path in credential_paths if path)
    )

def mark_as_indexed(doc_id: str) -> None:
    """Mark a document as indexed in Firestore."""
    db = get_firestore_client()
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
                        mark_as_indexed(point.payload["original_track_id"])
                    
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
                mark_as_indexed(point.payload["original_track_id"])
        
        logger.info("Migration completed successfully!")
    
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
