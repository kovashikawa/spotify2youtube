import json
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from spotipy.exceptions import SpotifyException
from typing import Optional, Dict, Any, List

from config.settings import SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET, SPOTIFY_REDIRECT_URI
from config.firestore_config import FirestoreClient
from utils.logger import setup_logger

logger = setup_logger(__name__)

SPOTIFY_SCOPES = [
    "user-library-read",
    "playlist-read-private",
    "playlist-read-collaborative",
    "playlist-modify-public",
    "playlist-modify-private",
]


def _load_token(user_id: str) -> Optional[dict]:
    """Load Spotify token_info from Firestore for a given user."""
    db = FirestoreClient().db
    doc = db.collection("users").document(user_id).collection("tokens").document("spotify").get()
    if not doc.exists:
        return None
    raw = doc.to_dict().get("token_info")
    return json.loads(raw) if raw else None


def _save_token(user_id: str, token_info: dict) -> None:
    """Persist a refreshed Spotify token back to Firestore."""
    db = FirestoreClient().db
    db.collection("users").document(user_id).collection("tokens").document("spotify").set(
        {"token_info": json.dumps(token_info)}, merge=True
    )


def get_spotify_client(user_id: str) -> spotipy.Spotify:
    """
    Return an authenticated Spotify client for user_id.
    Refreshes the token automatically if expired.
    Raises ValueError if the user has not completed the OAuth flow yet.
    """
    token_info = _load_token(user_id)
    if not token_info:
        raise ValueError(
            f"No Spotify token for user '{user_id}'. "
            "User must complete the OAuth flow at /auth/spotify first."
        )

    auth_manager = SpotifyOAuth(
        client_id=SPOTIFY_CLIENT_ID,
        client_secret=SPOTIFY_CLIENT_SECRET,
        redirect_uri=SPOTIFY_REDIRECT_URI,
        scope=" ".join(SPOTIFY_SCOPES),
        open_browser=False,
    )

    if auth_manager.is_token_expired(token_info):
        logger.info(f"Spotify token expired for user {user_id}, refreshing...")
        token_info = auth_manager.refresh_access_token(token_info["refresh_token"])
        _save_token(user_id, token_info)

    return spotipy.Spotify(auth=token_info["access_token"])


def get_playlist_tracks(spotify: spotipy.Spotify, playlist_id: str) -> List[Dict[str, Any]]:
    """Get all tracks from a Spotify playlist (handles pagination)."""
    try:
        results = spotify.playlist_tracks(playlist_id)
        if not results:
            return []
        tracks = results["items"]
        while results["next"]:
            results = spotify.next(results)
            if not results:
                break
            tracks.extend(results["items"])
        return tracks
    except SpotifyException as e:
        logger.error(f"Failed to get playlist tracks: {e}")
        raise


def create_spotify_playlist(
    spotify: spotipy.Spotify,
    user_id: str,
    name: str,
    description: str = "",
    public: bool = False,
) -> Optional[str]:
    """Create a new Spotify playlist and return its ID."""
    try:
        playlist = spotify.user_playlist_create(
            user_id, name=name, description=description, public=public
        )
        return playlist["id"]
    except SpotifyException as e:
        logger.error(f"Failed to create Spotify playlist: {e}")
        raise


def add_tracks_to_spotify_playlist(
    spotify: spotipy.Spotify,
    playlist_id: str,
    track_ids: List[str],
) -> bool:
    """Add tracks to a Spotify playlist (max 100 per request)."""
    try:
        for i in range(0, len(track_ids), 100):
            batch = track_ids[i : i + 100]
            spotify.playlist_add_items(playlist_id, batch)
        return True
    except SpotifyException as e:
        logger.error(f"Failed to add tracks to Spotify playlist: {e}")
        raise
