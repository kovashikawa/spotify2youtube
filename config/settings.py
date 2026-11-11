import os
from dotenv import load_dotenv

load_dotenv()  # Loads variables from .env

_CONFIG_DIR = os.path.dirname(__file__)

# Spotify Configuration
SPOTIFY_CLIENT_ID = os.getenv('SPOTIFY_CLIENT_ID')
SPOTIFY_CLIENT_SECRET = os.getenv('SPOTIFY_CLIENT_SECRET')
# Must match the route registered in routers/auth.py, which is mounted under /api.
SPOTIFY_REDIRECT_URI = os.getenv('SPOTIFY_REDIRECT_URI', 'http://localhost:8000/api/auth/spotify/callback')

# YouTube Configuration
YOUTUBE_API_KEY = os.getenv('YOUTUBE_API_KEY')  # if using API key for search
YOUTUBE_SCOPES = ["https://www.googleapis.com/auth/youtube.force-ssl"]
YOUTUBE_REDIRECT_URI = os.getenv('YOUTUBE_REDIRECT_URI', 'http://localhost:8000/api/auth/youtube/callback')
# Google OAuth client secrets file. Absolute so the flow does not depend on the
# working directory uvicorn was launched from.
YOUTUBE_CLIENT_SECRETS_PATH = os.getenv(
    'YOUTUBE_CLIENT_SECRETS_PATH',
    os.path.join(_CONFIG_DIR, 'credentials.json'),
)

# Firestore Configuration
FIRESTORE_PROJECT_ID = os.getenv('FIRESTORE_PROJECT_ID', 'spotify2youtube-449516')
FIRESTORE_CREDENTIALS_PATH = os.path.join(_CONFIG_DIR, 'firestore-credentials.json')

# Collection Names
COLLECTION_USERS = 'users'
COLLECTION_PLAYLISTS = 'playlists'
COLLECTION_TRACKS = 'tracks'
COLLECTION_CONVERSIONS = 'conversions'

# Environment
ENVIRONMENT = os.getenv('ENVIRONMENT', 'development')
DEBUG = ENVIRONMENT == 'development'
