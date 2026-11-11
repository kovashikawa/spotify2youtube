# spotify2youtube/airflow/dags/s2y_clients.py
"""
Per-task client construction for the spotify_youtube_sync DAG.

Airflow passes task return values through XCom, which serializes them. A live
spotipy.Spotify or googleapiclient service object cannot survive that, so no
client is ever returned from a task. Instead every task calls one of the
builders here at task start, reads the user's OAuth token out of Firestore, and
gets its own local client that lives and dies inside that task.

Credentials come from Airflow Variables rather than files mounted into the
container, so nothing secret has to sit on the worker filesystem:

  s2y_gcp_service_account   service account key, as a JSON string
  s2y_firestore_project     GCP project id
  s2y_firestore_database    Firestore database id (optional)
  s2y_spotify_client_id     Spotify app client id
  s2y_spotify_client_secret Spotify app client secret
  s2y_spotify_redirect_uri  Spotify redirect URI (optional)

If s2y_gcp_service_account is unset, the Google libraries fall back to
Application Default Credentials, which is what a worker running on GCP with a
bound service account should use.
"""

from __future__ import annotations

import json
from typing import Any, Dict, Optional

YOUTUBE_SCOPES = ["https://www.googleapis.com/auth/youtube.force-ssl"]

SPOTIFY_SCOPES = [
    "user-library-read",
    "playlist-read-private",
    "playlist-read-collaborative",
    "playlist-modify-public",
    "playlist-modify-private",
]

DEFAULT_FIRESTORE_DATABASE = "spotify2youtube"


def get_variable(key: str, default: Optional[str] = None) -> Optional[str]:
    """
    Read an Airflow Variable. Imported lazily so this module can be imported
    (and unit tested) without an Airflow metadata database behind it.
    """
    from airflow.models import Variable

    return Variable.get(key, default_var=default)


def _gcp_credentials():
    """
    Build GCP credentials from the s2y_gcp_service_account Variable.
    Returns None to let the client fall back to Application Default
    Credentials when the Variable is not set.
    """
    raw = get_variable("s2y_gcp_service_account", default=None)
    if not raw:
        return None

    from google.oauth2 import service_account

    return service_account.Credentials.from_service_account_info(json.loads(raw))


def firestore_client():
    """Build a Firestore client for this task."""
    from google.cloud import firestore

    project = get_variable("s2y_firestore_project", default=None)
    database = get_variable("s2y_firestore_database", default=DEFAULT_FIRESTORE_DATABASE)

    kwargs: Dict[str, Any] = {}
    credentials = _gcp_credentials()
    if credentials is not None:
        kwargs["credentials"] = credentials
    if project:
        kwargs["project"] = project
    if database:
        kwargs["database"] = database

    return firestore.Client(**kwargs)


def _token_document(db, user_id: str, platform: str):
    """Token layout written by the web auth flow: users/{uid}/tokens/{platform}."""
    return (
        db.collection("users")
        .document(user_id)
        .collection("tokens")
        .document(platform)
    )


def load_spotify_token(db, user_id: str) -> Dict[str, Any]:
    """Read a Spotify token_info dict out of Firestore."""
    doc = _token_document(db, user_id, "spotify").get()
    if not doc.exists:
        raise RuntimeError(
            f"No Spotify token in Firestore for user '{user_id}'. "
            "The user has to complete the web auth flow first."
        )
    raw = (doc.to_dict() or {}).get("token_info")
    if not raw:
        raise RuntimeError(f"Spotify token document for user '{user_id}' has no token_info.")
    return json.loads(raw) if isinstance(raw, str) else raw


def load_youtube_token(db, user_id: str) -> Dict[str, Any]:
    """Read a YouTube authorized-user JSON blob out of Firestore."""
    doc = _token_document(db, user_id, "youtube").get()
    if not doc.exists:
        raise RuntimeError(
            f"No YouTube token in Firestore for user '{user_id}'. "
            "The user has to complete the web auth flow first."
        )
    raw = (doc.to_dict() or {}).get("token_json")
    if not raw:
        raise RuntimeError(f"YouTube token document for user '{user_id}' has no token_json.")
    return json.loads(raw) if isinstance(raw, str) else raw


def build_spotify_client(db, user_id: str):
    """
    Build a spotipy client for user_id from the token held in Firestore,
    refreshing it first if it has expired.
    """
    import spotipy
    from spotipy.cache_handler import MemoryCacheHandler
    from spotipy.oauth2 import SpotifyOAuth

    token_info = load_spotify_token(db, user_id)

    auth_manager = SpotifyOAuth(
        client_id=get_variable("s2y_spotify_client_id", default=None),
        client_secret=get_variable("s2y_spotify_client_secret", default=None),
        redirect_uri=get_variable(
            "s2y_spotify_redirect_uri",
            default="http://localhost:8000/api/auth/spotify/callback",
        ),
        scope=" ".join(SPOTIFY_SCOPES),
        open_browser=False,
        # spotipy would otherwise write a single shared ".cache" file in the
        # worker's working directory, which is not keyed by user.
        cache_handler=MemoryCacheHandler(),
    )

    if auth_manager.is_token_expired(token_info):
        token_info = auth_manager.refresh_access_token(token_info["refresh_token"])
        _token_document(db, user_id, "spotify").set(
            {"token_info": json.dumps(token_info)}, merge=True
        )

    return spotipy.Spotify(auth=token_info["access_token"])


def build_youtube_client(db, user_id: str):
    """
    Build a YouTube Data API v3 service for user_id from the token held in
    Firestore, refreshing it first if it has expired.
    """
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    info = load_youtube_token(db, user_id)
    credentials = Credentials.from_authorized_user_info(info, scopes=YOUTUBE_SCOPES)

    if credentials.expired and credentials.refresh_token:
        credentials.refresh(Request())
        _token_document(db, user_id, "youtube").set(
            {"token_json": credentials.to_json()}, merge=True
        )

    return build("youtube", "v3", credentials=credentials, cache_discovery=False)


# --- Firestore writes -------------------------------------------------------
# The repo's database/firestore_ops module builds its client at import time from
# a mounted service account file, which would make this DAG unparseable without
# that file. These writes use the task-local client instead and keep the same
# document layout.


def store_playlist(db, user_id: str, playlist_id: str, platform: str,
                   metadata: Dict[str, Any], track_ids: list) -> None:
    db.collection("users").document(user_id).collection("playlists").document(
        playlist_id
    ).set(
        {
            "platform": platform,
            "metadata": metadata,
            "track_ids": track_ids,
        },
        merge=True,
    )


def store_track(db, track_id: str, platform: str, metadata: Dict[str, Any]) -> None:
    db.collection("tracks").document(platform).collection("items").document(
        track_id
    ).set({"metadata": metadata}, merge=True)


def store_track_link(db, spotify_track_id: str, youtube_track_id: str,
                     is_remix: bool = False) -> None:
    doc_id = f"{spotify_track_id}_{youtube_track_id}"
    db.collection("track_links").document("spotify_youtube").collection(
        "items"
    ).document(doc_id).set(
        {
            "spotify_track_id": spotify_track_id,
            "youtube_track_id": youtube_track_id,
            "is_remix": is_remix,
        },
        merge=True,
    )
