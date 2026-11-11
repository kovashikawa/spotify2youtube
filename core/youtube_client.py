import json
import time
from typing import Optional

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from config.settings import YOUTUBE_SCOPES
from config.firestore_config import FirestoreClient
from utils.logger import setup_logger

logger = setup_logger(__name__)


def _load_credentials(user_id: str) -> Optional[Credentials]:
    """Load YouTube credentials from Firestore for a given user."""
    db = FirestoreClient().db
    doc = db.collection("users").document(user_id).collection("tokens").document("youtube").get()
    if not doc.exists:
        return None
    token_json = doc.to_dict().get("token_json")
    if not token_json:
        return None
    info = json.loads(token_json)
    return Credentials.from_authorized_user_info(info, scopes=YOUTUBE_SCOPES)


def _save_credentials(user_id: str, credentials: Credentials) -> None:
    """Persist refreshed YouTube credentials back to Firestore."""
    db = FirestoreClient().db
    db.collection("users").document(user_id).collection("tokens").document("youtube").set(
        {"token_json": credentials.to_json()}, merge=True
    )


def get_youtube_service(user_id: str):
    """
    Return an authenticated YouTube Data API v3 service for user_id.
    Refreshes the token automatically if expired.
    Raises ValueError if the user has not completed the OAuth flow yet.
    """
    credentials = _load_credentials(user_id)
    if not credentials:
        raise ValueError(
            f"No YouTube token for user '{user_id}'. "
            "User must complete the OAuth flow at /auth/youtube first."
        )

    if credentials.expired and credentials.refresh_token:
        logger.info(f"YouTube token expired for user {user_id}, refreshing...")
        credentials.refresh(Request())
        _save_credentials(user_id, credentials)

    return build("youtube", "v3", credentials=credentials)


def search_youtube(youtube, query: str) -> Optional[str]:
    """Search YouTube for query and return the first video ID, or None."""
    try:
        response = youtube.search().list(
            q=query,
            part="id,snippet",
            type="video",
            maxResults=1,
        ).execute()
        items = response.get("items", [])
        if not items:
            return None
        return items[0]["id"]["videoId"]
    except HttpError as e:
        logger.error(f"YouTube search error: {e}")
        return None


def create_youtube_playlist(
    youtube, title: str, description: str, privacy_status: str = "private"
) -> Optional[str]:
    """Create a YouTube playlist and return its ID."""
    try:
        response = youtube.playlists().insert(
            part="snippet,status",
            body={
                "snippet": {"title": title, "description": description},
                "status": {"privacyStatus": privacy_status},
            },
        ).execute()
        return response["id"]
    except HttpError as e:
        logger.error(f"Failed to create YouTube playlist: {e}")
        return None


def add_video_to_playlist(
    youtube,
    playlist_id: str,
    video_id: str,
    max_retries: int = 2,
    initial_delay: float = 1.0,
) -> Optional[dict]:
    """
    Add a video to a YouTube playlist with exponential backoff on transient errors.
    Note: delay is applied only on retry, not before the first attempt.
    """
    delay = initial_delay
    for attempt in range(max_retries + 1):
        try:
            return youtube.playlistItems().insert(
                part="snippet",
                body={
                    "snippet": {
                        "playlistId": playlist_id,
                        "resourceId": {"kind": "youtube#video", "videoId": video_id},
                    }
                },
            ).execute()
        except HttpError as e:
            if attempt < max_retries and e.resp.status in [409, 500, 503]:
                logger.warning(
                    f"HTTP {e.resp.status} adding video {video_id}, "
                    f"retrying in {delay:.0f}s (attempt {attempt + 1}/{max_retries})"
                )
                time.sleep(delay)
                delay *= 2
            else:
                logger.error(f"Failed to add video {video_id} to playlist: {e}")
                return None
        except Exception as e:
            logger.error(f"Unexpected error adding video {video_id}: {e}")
            return None
    return None


def get_youtube_playlist_items(youtube, playlist_id: str) -> list:
    """Fetch all video items from a YouTube playlist (handles pagination)."""
    try:
        items = []
        request = youtube.playlistItems().list(
            part="snippet", playlistId=playlist_id, maxResults=50
        )
        while request:
            response = request.execute()
            items.extend(response.get("items", []))
            request = youtube.playlistItems().list_next(request, response)
        return items
    except HttpError as e:
        logger.error(f"Failed to fetch YouTube playlist items: {e}")
        return []
