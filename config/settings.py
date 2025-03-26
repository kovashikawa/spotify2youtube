import os
from dotenv import load_dotenv

load_dotenv()  # Loads variables from .env

# Spotify Configuration
SPOTIFY_CLIENT_ID = os.getenv('SPOTIFY_CLIENT_ID')
SPOTIFY_CLIENT_SECRET = os.getenv('SPOTIFY_CLIENT_SECRET')

# YouTube Configuration
YOUTUBE_API_KEY = os.getenv('YOUTUBE_API_KEY')  # if using API key for search
YOUTUBE_SCOPES = ["https://www.googleapis.com/auth/youtube.force-ssl"]

# Firestore Configuration
FIRESTORE_PROJECT_ID = os.getenv('FIRESTORE_PROJECT_ID', 'spotify2youtube-449516')
FIRESTORE_CREDENTIALS_PATH = os.path.join(os.path.dirname(__file__), 'firestore-credentials.json')

# Collection Names
COLLECTION_USERS = 'users'
COLLECTION_PLAYLISTS = 'playlists'
COLLECTION_TRACKS = 'tracks'
COLLECTION_CONVERSIONS = 'conversions'

# Environment
ENVIRONMENT = os.getenv('ENVIRONMENT', 'development')
DEBUG = ENVIRONMENT == 'development'
