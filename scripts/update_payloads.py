#!/usr/bin/env python3
# spotify2youtube/scripts/update_payloads.py

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

from core.vector_db import update_payloads, create_point_struct
from database.firestore_ops import get_all_tracks
from config.vector_config import COLLECTION_NAME

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants
BATCH_SIZE = 10

def get_firestore_client() -> firestore.Client:
    """Get Firestore client with proper credentials."""
    credential_paths = [
        os.path.join(project_root, "config", "firestore-credentials.json"),  # Local development
        "/opt/airflow/config/firestore-credentials.json",                   # Airflow container
        os.getenv("GOOGLE_APPLICATION_CREDENTIALS")                        # Environment variable
    ]
    
    for path in credential_paths:
        if os.path.exists(path):
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = path
            return firestore.Client()
    
    raise FileNotFoundError(
        "Firestore credentials not found. Please ensure service_account.json exists in one of these locations:\n" +
        "\n".join(f"- {path}" for path in credential_paths if path)
    )

def main():
    """Main function to update payloads without affecting vectors."""
    try:
        # Initialize Firestore client
        db = get_firestore_client()
        
        # Fetch all tracks
        logger.info("Fetching tracks from Firestore...")
        tracks: List[Dict[str, Any]] = get_all_tracks()
        logger.info(f"Found {len(tracks)} tracks to update")
        
        # Process in batches
        batch: List[PointStruct] = []
        for i, track in enumerate(tracks, start=1):
            try:
                # Build PointStruct (payload only matters for update; vector will be ignored)
                point = create_point_struct(track)
                batch.append(point)
                
                if len(batch) >= BATCH_SIZE:
                    logger.info(f"Updating payloads for batch of {len(batch)} tracks...")
                    update_payloads(COLLECTION_NAME, batch)
                    batch.clear()
                    logger.info(f"Processed {i}/{len(tracks)} tracks")
            
            except Exception as e:
                logger.error(f"Error processing track {track.get('track_name') or track.get('title')}: {e}")
                continue
        
        # Process any remaining tracks
        if batch:
            logger.info(f"Updating payloads for final batch of {len(batch)} tracks...")
            update_payloads(COLLECTION_NAME, batch)
        
        logger.info("Payload update completed successfully!")
    
    except Exception as e:
        logger.error(f"Payload update failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()