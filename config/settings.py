import os
from dotenv import load_dotenv

load_dotenv()  # Loads variables from .env

SPOTIFY_CLIENT_ID = os.getenv('SPOTIFY_CLIENT_ID')
SPOTIFY_CLIENT_SECRET = os.getenv('SPOTIFY_CLIENT_SECRET')

YOUTUBE_API_KEY = os.getenv('YOUTUBE_API_KEY')  # if using API key for search

# If using OAuth for YouTube, you'll have credentials.json in the same folder.
# Example SCOPES for YouTube:
YOUTUBE_SCOPES = ["https://www.googleapis.com/auth/youtube.force-ssl"]