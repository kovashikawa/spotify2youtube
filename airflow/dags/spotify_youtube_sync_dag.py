# spotify2youtube/airflow/dags/spotify_youtube_sync_dag.py
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
from core.spotify_client import get_spotify_oauth_client, get_playlist_tracks
from core.youtube_client import search_youtube
from database.firestore_ops import (
    store_user, store_playlist, store_track, store_track_link
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
        owner, track = track_tuple
        tid = track["id"]
        name = track["name"]
        artists = ", ".join(a["name"] for a in track["artists"])

        store_track(tid, "spotify", track)

        # naive YT search → first hit
        yt_id = search_youtube(name + " " + artists)
        if yt_id:
            store_track_link(tid, yt_id)

    # — DAG wiring —
    sp_client = authenticate()
    playlist_list = list_playlists(sp_client)

    with TaskGroup(group_id="playlist_processing") as process_group:
        # fan-out
        track_lists = fetch_tracks.partial(sp=sp_client).expand(playlist_tuple=playlist_list)
        _ = enrich_and_link.expand(track_tuple=track_lists)

    sp_client >> playlist_list >> process_group 