import json
from fastapi import APIRouter, HTTPException, Query

import spotipy
from google.oauth2.credentials import Credentials

from config.settings import YOUTUBE_SCOPES
from config.firestore_config import FirestoreClient
from utils.logger import setup_logger

logger = setup_logger(__name__)
router = APIRouter(tags=["connection"])


@router.get("/connect", summary="Check auth status for a user")
async def check_connection(user_id: str = Query(..., description="Spotify user ID")):
    """
    Validates that valid (non-expired) tokens exist in Firestore for this user.
    Does not trigger any new OAuth flows.
    """
    db = FirestoreClient().db
    result = {"user_id": user_id, "spotify": False, "youtube": False}

    # Check Spotify
    try:
        doc = db.collection("users").document(user_id).collection("tokens").document("spotify").get()
        if doc.exists:
            raw = doc.to_dict().get("token_info")
            if raw:
                from spotipy.oauth2 import SpotifyOAuth
                from config.settings import SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET, SPOTIFY_REDIRECT_URI
                token_info = json.loads(raw)
                auth_manager = SpotifyOAuth(
                    client_id=SPOTIFY_CLIENT_ID,
                    client_secret=SPOTIFY_CLIENT_SECRET,
                    redirect_uri=SPOTIFY_REDIRECT_URI,
                    open_browser=False,
                )
                result["spotify"] = not auth_manager.is_token_expired(token_info)
    except Exception as e:
        logger.warning(f"Spotify token check failed for {user_id}: {e}")

    # Check YouTube
    try:
        doc = db.collection("users").document(user_id).collection("tokens").document("youtube").get()
        if doc.exists:
            token_json = doc.to_dict().get("token_json")
            if token_json:
                creds = Credentials.from_authorized_user_info(
                    json.loads(token_json), scopes=YOUTUBE_SCOPES
                )
                result["youtube"] = creds.valid and not creds.expired
    except Exception as e:
        logger.warning(f"YouTube token check failed for {user_id}: {e}")

    return result
