import json
from fastapi import APIRouter, HTTPException
from fastapi.responses import RedirectResponse
from spotipy.oauth2 import SpotifyOAuth
from google_auth_oauthlib.flow import Flow

from config.settings import (
    SPOTIFY_CLIENT_ID,
    SPOTIFY_CLIENT_SECRET,
    SPOTIFY_REDIRECT_URI,
    YOUTUBE_REDIRECT_URI,
    YOUTUBE_SCOPES,
)
from config.firestore_config import FirestoreClient
from utils.logger import setup_logger

logger = setup_logger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])

SPOTIFY_SCOPES = [
    "user-library-read",
    "playlist-read-private",
    "playlist-read-collaborative",
    "playlist-modify-public",
    "playlist-modify-private",
]

# --- Spotify ---

@router.get("/spotify", summary="Start Spotify OAuth flow")
async def spotify_login():
    auth_manager = SpotifyOAuth(
        client_id=SPOTIFY_CLIENT_ID,
        client_secret=SPOTIFY_CLIENT_SECRET,
        redirect_uri=SPOTIFY_REDIRECT_URI,
        scope=" ".join(SPOTIFY_SCOPES),
        open_browser=False,
    )
    auth_url = auth_manager.get_authorize_url()
    return RedirectResponse(url=auth_url)


@router.get("/spotify/callback", summary="Spotify OAuth callback")
async def spotify_callback(code: str, state: str = None, error: str = None):
    if error:
        raise HTTPException(status_code=400, detail=f"Spotify auth error: {error}")

    auth_manager = SpotifyOAuth(
        client_id=SPOTIFY_CLIENT_ID,
        client_secret=SPOTIFY_CLIENT_SECRET,
        redirect_uri=SPOTIFY_REDIRECT_URI,
        scope=" ".join(SPOTIFY_SCOPES),
        open_browser=False,
    )

    token_info = auth_manager.get_access_token(code, as_dict=True, check_cache=False)
    if not token_info:
        raise HTTPException(status_code=400, detail="Failed to exchange Spotify auth code")

    import spotipy
    sp = spotipy.Spotify(auth=token_info["access_token"])
    user = sp.current_user()
    user_id = user["id"]

    db = FirestoreClient().db
    db.collection("users").document(user_id).collection("tokens").document("spotify").set(
        {"token_info": json.dumps(token_info)},
        merge=True,
    )

    logger.info(f"Spotify token stored for user {user_id}")
    return {"status": "ok", "user_id": user_id, "display_name": user.get("display_name")}


# --- YouTube ---

@router.get("/youtube", summary="Start YouTube OAuth flow")
async def youtube_login(user_id: str):
    """
    user_id is the Spotify user ID — used to associate the YouTube token
    with the correct account after the callback.
    """
    flow = Flow.from_client_secrets_file(
        "config/credentials.json",
        scopes=YOUTUBE_SCOPES,
        redirect_uri=YOUTUBE_REDIRECT_URI,
    )
    auth_url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        state=user_id,
        prompt="consent",
    )
    return RedirectResponse(url=auth_url)


@router.get("/youtube/callback", summary="YouTube OAuth callback")
async def youtube_callback(code: str, state: str = None, error: str = None):
    if error:
        raise HTTPException(status_code=400, detail=f"YouTube auth error: {error}")

    user_id = state
    if not user_id:
        raise HTTPException(status_code=400, detail="Missing state (user_id) in callback")

    flow = Flow.from_client_secrets_file(
        "config/credentials.json",
        scopes=YOUTUBE_SCOPES,
        redirect_uri=YOUTUBE_REDIRECT_URI,
        state=user_id,
    )
    flow.fetch_token(code=code)
    credentials = flow.credentials

    db = FirestoreClient().db
    db.collection("users").document(user_id).collection("tokens").document("youtube").set(
        {"token_json": credentials.to_json()},
        merge=True,
    )

    logger.info(f"YouTube token stored for user {user_id}")
    return {"status": "ok", "user_id": user_id}
