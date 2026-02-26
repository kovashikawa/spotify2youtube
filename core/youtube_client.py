import os
import time
import pickle
import socket
from googleapiclient.errors import HttpError
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from config.settings import YOUTUBE_SCOPES
from utils.logger import setup_logger

logger = setup_logger(__name__)

# Cache paths
YOUTUBE_TOKEN_PATH = "config/.youtube_token"

def is_port_available(port):
    """Check if a port is available for binding."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(('localhost', port))
            return True
        except OSError:
            return False

def find_available_port(start_port=8080, max_attempts=10):
    """Find an available port starting from start_port."""
    for i in range(max_attempts):
        port = start_port + i
        if is_port_available(port):
            return port
    # If no port found, let OS assign one (port=0)
    logger.warning(f"No available port found in range {start_port}-{start_port + max_attempts - 1}, using OS-assigned port")
    return 0

def get_youtube_service_oauth():
    """
    Returns an authenticated YouTube service using OAuth.
    If the cached token is expired or revoked, it refreshes or triggers a new OAuth flow.
    """
    credentials = None

    # Attempt to load existing credentials
    if os.path.exists(YOUTUBE_TOKEN_PATH):
        try:
            with open(YOUTUBE_TOKEN_PATH, "rb") as token:
                credentials = pickle.load(token)
            logger.debug("Loaded existing YouTube credentials from cache")
        except Exception as e:
            logger.warning(f"Error loading YouTube credentials: {e}")
            if os.path.exists(YOUTUBE_TOKEN_PATH):
                os.remove(YOUTUBE_TOKEN_PATH)
            credentials = None

    # If no credentials or they are invalid, try to refresh them
    if not credentials or not credentials.valid:
        if credentials and credentials.expired and credentials.refresh_token:
            try:
                logger.info("Refreshing expired YouTube credentials...")
                credentials.refresh(Request())
                logger.info("Successfully refreshed YouTube credentials")
            except Exception as e:
                logger.warning(f"Error refreshing YouTube token: {e}")
                # If refresh fails, delete the token file and force a new OAuth flow
                if os.path.exists(YOUTUBE_TOKEN_PATH):
                    os.remove(YOUTUBE_TOKEN_PATH)
                credentials = None

        # If we still have no valid credentials, run the OAuth flow
        if not credentials or not credentials.valid:
            try:
                # Get OAuth port from environment or use default
                oauth_port = int(os.getenv('YOUTUBE_OAUTH_PORT', '8080'))
                
                # Check if port is available, if not find an available one
                if not is_port_available(oauth_port):
                    logger.warning(f"Port {oauth_port} is already in use, searching for available port...")
                    oauth_port = find_available_port(oauth_port)
                    if oauth_port != 0:
                        logger.info(f"Using port {oauth_port} for OAuth flow")
                
                flow = InstalledAppFlow.from_client_secrets_file(
                    "config/credentials.json", scopes=YOUTUBE_SCOPES
                )
                credentials = flow.run_local_server(port=oauth_port)
                logger.info("Successfully completed YouTube OAuth flow")
            except OSError as e:
                error_msg = f"Error in YouTube OAuth flow: {e}"
                logger.error(error_msg)
                if "Address already in use" in str(e) or e.errno == 48:
                    logger.error(f"Port {oauth_port} is already in use. Try:")
                    logger.error("1. Kill the process using the port: lsof -ti:8080 | xargs kill -9")
                    logger.error("2. Set YOUTUBE_OAUTH_PORT environment variable to a different port")
                    logger.error("3. Wait for the previous OAuth flow to complete")
                raise Exception(error_msg) from e
            except Exception as e:
                error_msg = f"Error in YouTube OAuth flow: {e}"
                logger.error(error_msg)
                raise Exception(error_msg) from e

        # Save the new credentials for future use
        try:
            with open(YOUTUBE_TOKEN_PATH, "wb") as token:
                pickle.dump(credentials, token)
            logger.info("Saved YouTube credentials to cache")
        except Exception as e:
            logger.error(f"Error saving YouTube credentials: {e}")

    try:
        youtube = build("youtube", "v3", credentials=credentials)
        # Test the connection
        youtube.channels().list(part="id", mine=True).execute()
        logger.info("Successfully built and tested YouTube service")
        return youtube
    except Exception as e:
        logger.error(f"Error building YouTube service: {e}")
        if os.path.exists(YOUTUBE_TOKEN_PATH):
            os.remove(YOUTUBE_TOKEN_PATH)
        return get_youtube_service_oauth()

def search_youtube(youtube, query):
    """
    Searches YouTube for the given query and returns the first video's ID.
    """
    try:
        request = youtube.search().list(
            q=query,
            part="id,snippet",
            type="video",
            maxResults=1
        )
        response = request.execute()
        items = response.get("items", [])
        if not items:
            return None
        return items[0]["id"]["videoId"]
    except Exception as e:
        logger.error(f"Error searching YouTube: {e}")
        return None

def create_youtube_playlist(youtube, title, description, privacy_status="private"):
    """Creates a new YouTube playlist and returns its ID."""
    try:
        request = youtube.playlists().insert(
            part="snippet,status",
            body={
                "snippet": {
                    "title": title,
                    "description": description
                },
                "status": {
                    "privacyStatus": privacy_status
                }
            }
        )
        response = request.execute()
        return response["id"]
    except Exception as e:
        logger.error(f"Error creating YouTube playlist: {e}")
        return None

def add_video_to_playlist(youtube, playlist_id, video_id, max_retries=2, initial_delay=5):
    """
    Adds a video to a YouTube playlist with retries for transient errors.
    """
    retries = 0
    delay = initial_delay
    while retries <= max_retries:
        try:
            time.sleep(delay)
            request = youtube.playlistItems().insert(
                part="snippet",
                body={
                    "snippet": {
                        "playlistId": playlist_id,
                        "resourceId": {
                            "kind": "youtube#video",
                            "videoId": video_id
                        }
                    }
                }
            )
            return request.execute()
        except HttpError as e:
            if retries < max_retries and e.resp.status in [409, 500, 503]:
                logger.warning(f"Error {e.resp.status} adding video {video_id}. Retrying in {delay} seconds...")
                time.sleep(delay)
                retries += 1
                delay *= 2  # exponential backoff
            else:
                logger.error(f"Error adding video to playlist: {e}")
                return None
        except Exception as e:
            logger.error(f"Unexpected error adding video to playlist: {e}")
            return None

def get_youtube_playlist_items(youtube, playlist_id):
    """Fetches all video items from the given YouTube playlist."""
    try:
        items = []
        request = youtube.playlistItems().list(
            part="snippet",
            playlistId=playlist_id,
            maxResults=50
        )
        response = request.execute()
        items.extend(response.get("items", []))
        while "nextPageToken" in response:
            request = youtube.playlistItems().list(
                part="snippet",
                playlistId=playlist_id,
                maxResults=50,
                pageToken=response["nextPageToken"]
            )
            response = request.execute()
            items.extend(response.get("items", []))
        return items
    except Exception as e:
        logger.error(f"Error fetching YouTube playlist items: {e}")
        return []
