import os
import pickle
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

def add_video_to_playlist(youtube, playlist_id, video_id):
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
    