from googleapiclient.discovery import build
from config.settings import YOUTUBE_API_KEY

def get_youtube_service_api_key():
    """
    Creates a YouTube service object with the provided API key.
    This allows searching or limited read operations.
    """
    youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)
    return youtube

def search_youtube(youtube, query):
    """
    Returns the first video ID matching the query, or None if no match is found.
    """
    request = youtube.search().list(
        part='snippet',
        q=query,
        maxResults=1,
        type='video'
    )
    response = request.execute()
    items = response.get('items', [])
    if not items:
        return None
    return items[0]['id']['videoId']
    