import json
from fastapi import APIRouter, Query

from google.oauth2.credentials import Credentials

from config.settings import YOUTUBE_SCOPES
from config.firestore_config import FirestoreClient
from core.spotify_client import build_spotify_oauth
from utils.logger import setup_logger

logger = setup_logger(__name__)
router = APIRouter(tags=["connection"])


@router.get("/connect", summary="Check auth status for a user")
async def check_connection(user_id: str = Query(..., description="Spotify user ID")):
    """
    Validates that usable tokens exist in Firestore for this user.
    Does not trigger any new OAuth flows.

    A token that is expired but carries a refresh token still counts as
    connected, because the clients refresh it automatically on next use.
    Only a missing token, or an expired one with no refresh token, means
    the user has to run the OAuth flow again.
    """
    db = FirestoreClient().db
    result = {"user_id": user_id, "spotify": False, "youtube": False}

    # Check Spotify
    try:
        doc = db.collection("users").document(user_id).collection("tokens").document("spotify").get()
        if doc.exists:
            raw = doc.to_dict().get("token_info")
            if raw:
                token_info = json.loads(raw)
                auth_manager = build_spotify_oauth()
                result["spotify"] = (
                    not auth_manager.is_token_expired(token_info)
                    or bool(token_info.get("refresh_token"))
                )
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
                result["youtube"] = creds.valid or bool(creds.refresh_token)
    except Exception as e:
        logger.warning(f"YouTube token check failed for {user_id}: {e}")

    return result
