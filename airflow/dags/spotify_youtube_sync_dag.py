# spotify2youtube/airflow/dags/spotify_youtube_sync_dag.py
"""
Sync a user's Spotify playlists into Firestore and link each track to a
YouTube video id.

Auth design: no task returns a client. Airflow serializes task return values
into XCom, so a live spotipy.Spotify or googleapiclient service object cannot
be handed to a downstream task. Every task takes a plain user_id string,
builds its own Firestore, Spotify and YouTube clients at task start from the
token the web auth flow stored in Firestore, and drops them when it ends.
Credentials come from Airflow Variables rather than files mounted into the
worker. See s2y_clients for the Variable names.
"""

from datetime import datetime, timedelta

from airflow import DAG
from airflow.decorators import task
from airflow.utils.task_group import TaskGroup

from airflow.utils.log.logging_mixin import LoggingMixin
logger = LoggingMixin().log

# add repo to PYTHONPATH
import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).parents[1] / "spotify2youtube"))

# repo helpers
from core.youtube_client import search_youtube

# task-local auth and Firestore writes
from s2y_clients import (
    build_spotify_client,
    build_youtube_client,
    firestore_client,
    get_variable,
    load_spotify_token,
    load_youtube_token,
    store_playlist,
    store_track,
    store_track_link,
)

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
    tags=["spotify", "youtube", "firestore"],
) as dag:

    @task()
    def resolve_user() -> str:
        """
        Return the user id to sync as a plain string, which is XCom safe, and
        fail early if either token is missing instead of part way through the
        fan-out.
        """
        user_id = get_variable("s2y_sync_user_id", default=None)
        if not user_id:
            raise RuntimeError(
                "Airflow Variable 's2y_sync_user_id' is not set. It must hold the "
                "Spotify user id whose playlists this DAG syncs."
            )

        db = firestore_client()
        load_spotify_token(db, user_id)
        load_youtube_token(db, user_id)
        logger.info("Tokens present in Firestore for user %s", user_id)
        return user_id

    @task()
    def list_playlists(user_id: str):
        """Return [(playlist_id, name, owner_id)], all JSON serializable."""
        db = firestore_client()
        sp = build_spotify_client(db, user_id)
        items = sp.current_user_playlists(limit=50)["items"]
        return [
            (p["id"], p["name"], p["owner"]["id"])
            for p in items
        ]

    @task()
    def fetch_tracks(user_id: str, playlist_tuple):
        from core.spotify_client import get_playlist_tracks

        pid, pname, owner = playlist_tuple
        db = firestore_client()
        sp = build_spotify_client(db, user_id)

        tracks = get_playlist_tracks(sp, pid)
        usable = [t for t in tracks if t.get("track") and t["track"].get("id")]

        # store playlist meta
        store_playlist(
            db,
            user_id=owner,
            playlist_id=pid,
            platform="spotify",
            metadata={"name": pname},
            track_ids=[t["track"]["id"] for t in usable],
        )
        return [(owner, t["track"]) for t in usable]

    @task()
    def enrich_and_link(user_id: str, track_tuple):
        owner, track = track_tuple
        tid = track["id"]
        name = track["name"]
        artists = ", ".join(a["name"] for a in track.get("artists", []))

        db = firestore_client()
        # The YouTube client is built here, in the task that actually searches,
        # because it cannot be handed over from an upstream task.
        youtube = build_youtube_client(db, user_id)

        store_track(db, tid, "spotify", track)

        yt_id = search_youtube(youtube, f"{name} {artists}".strip())
        if yt_id:
            store_track_link(db, tid, yt_id)
        else:
            logger.warning("No YouTube match for %s by %s", name, artists)

    # --- DAG wiring ---
    user_id = resolve_user()
    playlist_list = list_playlists(user_id)

    with TaskGroup(group_id="playlist_processing") as process_group:
        # fan-out
        track_lists = fetch_tracks.partial(user_id=user_id).expand(
            playlist_tuple=playlist_list
        )
        _ = enrich_and_link.partial(user_id=user_id).expand(track_tuple=track_lists)

    user_id >> playlist_list >> process_group
