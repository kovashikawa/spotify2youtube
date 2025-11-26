# spotify2youtube/airflow/dags/spotify_youtube_sync_dag.py
from datetime import datetime, timedelta
from airflow import DAG
from airflow.decorators import task
from airflow.utils.task_group import TaskGroup
from airflow.utils.log.logging_mixin import LoggingMixin
from qdrant_client.models import PointStruct
import uuid

logger = LoggingMixin().log

# add repo to PYTHONPATH
import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).parents[1] / "spotify2youtube"))

# repo helpers
from core.spotify_client import get_spotify_oauth_client, get_playlist_tracks
from core.youtube_client import search_youtube
from core.vector_db import upsert_vectors, search_similar, create_point_struct
from core.embeddings import get_track_embedding
from database.firestore_ops import (
    store_user, store_playlist, store_track, store_track_link,
    get_existing_track_link
)
from config.vector_config import COLLECTION_NAME

DEFAULT_ARGS = {
    "owner": "spotify2youtube",
    "retries": 1,
    "retry_delay": timedelta(seconds=15),
}

with DAG(
    dag_id="spotify_youtube_sync",
    schedule="0 */6 * * *",   # every 6 h
    start_date=datetime(2025, 5, 9),
    catchup=False,
    default_args=DEFAULT_ARGS,
    tags=["spotify", "youtube", "firestore", "vector"],
) as dag:

    @task()
    def authenticate():
        try:
            sp = get_spotify_oauth_client()
            logger.info("Authenticate task returned: %s", sp)
            return sp
        except Exception as e:
            logger.error("Authenticate task failed: %s", e, exc_info=True)
            raise

    @task()
    def list_playlists(sp):
        """Return [(playlist_id, name, owner_id)]"""
        items = sp.current_user_playlists(limit=50)["items"]
        return [
            (p["id"], p["name"], p["owner"]["id"])
            for p in items
        ]

    @task()
    def fetch_tracks(sp, playlist_tuple):
        pid, pname, owner = playlist_tuple
        tracks = get_playlist_tracks(sp, pid)
        # store playlist meta
        store_playlist(
            user_id=owner,
            playlist_id=pid,
            platform="spotify",
            metadata={"name": pname},
            track_ids=[t["track"]["id"] for t in tracks],
        )
        return [(owner, t["track"]) for t in tracks]

    @task()
    def enrich_and_link(track_tuple):
        """
        Process a Spotify track:
        1. Store in Firestore
        2. Generate embedding and store in Qdrant
        3. Find YouTube equivalent (Firestore cache -> Vector search -> API fallback)
        4. Store cross-platform link
        """
        owner, track = track_tuple
        tid = track["id"]
        name = track["name"]
        artists = ", ".join(a["name"] for a in track["artists"])

        # Store Spotify track in Firestore
        store_track(tid, "spotify", track)

        # Check Firestore cache first (fastest)
        cached_link = get_existing_track_link(tid, "spotify")
        if cached_link:
            yt_id = cached_link.get("youtube_track_id")
            logger.info(f"Cache hit for '{name}': YouTube ID {yt_id}")
            return  # Already linked

        # Prepare track data with platform info for create_point_struct
        track_data = {
            **track,
            "platform": "spotify",
            "track_id": tid,
            "user_id": owner
        }

        # Create point structure and upsert to Qdrant
        try:
            point = create_point_struct(track_data)
            upsert_vectors(COLLECTION_NAME, [point])
            logger.info(f"Stored Spotify track '{name}' in vector DB")
        except Exception as e:
            logger.error(f"Failed to store vector for '{name}': {e}")
            # Continue even if vector storage fails

        # Search for YouTube equivalent using vector similarity
        # Search the same unified collection but filter by platform='youtube'
        yt_id = None
        try:
            embedding = get_track_embedding(track_data)
            similar_tracks = search_similar(
                collection_name=COLLECTION_NAME,
                query_vector=embedding,
                platform="youtube",  # Filter to YouTube tracks only
                top_k=5,
                min_score=0.85  # Only high-confidence matches
            )

            if similar_tracks:
                # Use the most similar YouTube track
                best_match = similar_tracks[0]
                yt_id = best_match.payload.get("track_id")
                logger.info(
                    f"Vector match for '{name}': {best_match.payload.get('track_name')} "
                    f"(score: {best_match.score:.3f})"
                )
        except Exception as e:
            logger.warning(f"Vector search failed for '{name}': {e}")

        # Fallback to YouTube API search if no vector match
        if not yt_id:
            try:
                search_query = f"{name} {artists}"
                yt_results = search_youtube(search_query)
                if yt_results:
                    yt_id = yt_results[0] if isinstance(yt_results, list) else yt_results
                    logger.info(f"API search match for '{name}': {yt_id}")
            except Exception as e:
                logger.error(f"YouTube API search failed for '{name}': {e}")

        # Store the track link if YouTube match found
        if yt_id:
            try:
                store_track_link(tid, yt_id)
                logger.info(f"Linked Spotify:{tid} <-> YouTube:{yt_id}")
            except Exception as e:
                logger.error(f"Failed to store track link for '{name}': {e}")
        else:
            logger.warning(f"No YouTube match found for '{name}'")

    # — DAG wiring —
    sp_client = authenticate()
    playlist_list = list_playlists(sp_client)

    with TaskGroup(group_id="playlist_processing") as process_group:
        # fan-out
        track_lists = fetch_tracks.partial(sp=sp_client).expand(playlist_tuple=playlist_list)
        _ = enrich_and_link.expand(track_tuple=track_lists)

    sp_client >> playlist_list >> process_group
