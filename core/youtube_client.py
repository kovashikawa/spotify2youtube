import os
import time
import pickle
from googleapiclient.errors import HttpError
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from config.settings import YOUTUBE_SCOPES

# Cache paths
YOUTUBE_TOKEN_PATH = "config/.youtube_token"

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
        except Exception as e:
            print(f"Error loading YouTube credentials: {e}")
            if os.path.exists(YOUTUBE_TOKEN_PATH):
                os.remove(YOUTUBE_TOKEN_PATH)
            credentials = None

    # If no credentials or they are invalid, try to refresh them
    if not credentials or not credentials.valid:
        if credentials and credentials.expired and credentials.refresh_token:
            try:
                credentials.refresh(Request())
            except Exception as e:
                print(f"Error refreshing YouTube token: {e}")
                # If refresh fails, delete the token file and force a new OAuth flow
                if os.path.exists(YOUTUBE_TOKEN_PATH):
                    os.remove(YOUTUBE_TOKEN_PATH)
                credentials = None

        # If we still have no valid credentials, run the OAuth flow
        if not credentials or not credentials.valid:
            try:
                flow = InstalledAppFlow.from_client_secrets_file(
                    "config/credentials.json", scopes=YOUTUBE_SCOPES
                )
                credentials = flow.run_local_server(port=8080)
            except Exception as e:
                print(f"Error in YouTube OAuth flow: {e}")
                raise

        # Save the new credentials for future use
        try:
            with open(YOUTUBE_TOKEN_PATH, "wb") as token:
                pickle.dump(credentials, token)
        except Exception as e:
            print(f"Error saving YouTube credentials: {e}")

    try:
        youtube = build("youtube", "v3", credentials=credentials)
        # Test the connection
        youtube.channels().list(part="id", mine=True).execute()
        return youtube
    except Exception as e:
        print(f"Error building YouTube service: {e}")
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
        print(f"Error searching YouTube: {e}")
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
        print(f"Error creating YouTube playlist: {e}")
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
                print(f"Error {e.resp.status} adding video {video_id}. Retrying in {delay} seconds...")
                time.sleep(delay)
                retries += 1
                delay *= 2  # exponential backoff
            else:
                print(f"Error adding video to playlist: {e}")
                return None
        except Exception as e:
            print(f"Unexpected error adding video to playlist: {e}")
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
        print(f"Error fetching YouTube playlist items: {e}")
        return []
