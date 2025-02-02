import os
import time
import pickle
from googleapiclient.errors import HttpError
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from config.settings import YOUTUBE_SCOPES

def get_youtube_service_oauth():
    """
    Authenticates via OAuth using a local token.pickle if it exists.
    Otherwise, it prompts the user through a web browser flow.
    """
    credentials = None
    token_path = 'token.pickle'

    if os.path.exists(token_path):
        with open(token_path, 'rb') as token:
            credentials = pickle.load(token)

    if not credentials or not credentials.valid:
        if credentials and credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
        else:
            # Make sure client_secret.json is in config/ folder, or update path accordingly
            flow = InstalledAppFlow.from_client_secrets_file(
                'config/credentials.json',
                scopes=YOUTUBE_SCOPES
            )
            credentials = flow.run_local_server(port=8080)
        with open(token_path, 'wb') as token:
            pickle.dump(credentials, token)

    youtube = build('youtube', 'v3', credentials=credentials)
    return youtube

def search_youtube(youtube, query):
    """
    Searches YouTube for the given query and returns the first video's ID.
    """
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

def create_youtube_playlist(youtube, title, description, privacy_status="private"):
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
                raise

def get_youtube_service_oauth():
    """Returns an authenticated YouTube service using OAuth."""
    credentials = None
    token_path = "token.pickle"

    if os.path.exists(token_path):
        with open(token_path, "rb") as token:
            credentials = pickle.load(token)

    if not credentials or not credentials.valid:
        if credentials and credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                "config/credentials.json", scopes=YOUTUBE_SCOPES
            )
            credentials = flow.run_local_server(port=8080)
        with open(token_path, "wb") as token:
            pickle.dump(credentials, token)

    return build("youtube", "v3", credentials=credentials)

def get_youtube_playlist_items(youtube, playlist_id):
    """Fetches all video items from the given YouTube playlist."""
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
