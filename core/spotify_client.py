import os
import spotipy
from dotenv import load_dotenv
from spotipy.oauth2 import SpotifyClientCredentials, SpotifyOAuth
from spotipy.exceptions import SpotifyException
from config.settings import SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET, SPOTIFY_REDIRECT_URI
from typing import Optional, Dict, Any, List
from utils.logger import setup_logger
from .secure_cache_handler import SecureCacheFileHandler

load_dotenv()

logger = setup_logger(__name__)

# Define cache paths
SPOTIFY_CACHE_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", ".spotify_cache")
SPOTIFY_TOKEN_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", ".spotify_token")

def get_spotify_client() -> spotipy.Spotify:
    """
    Get a Spotify client using client credentials flow.
    This is for app-level operations that don't require user authentication.
    """
    try:
        # Initialize the secure cache handler
        cache_handler = SecureCacheFileHandler(cache_path=SPOTIFY_CACHE_PATH)
        
        # Create client credentials manager
        auth_manager = SpotifyClientCredentials(
            client_id=SPOTIFY_CLIENT_ID,
            client_secret=SPOTIFY_CLIENT_SECRET,
            cache_handler=cache_handler
        )
        
        # Create and return the client
        client = spotipy.Spotify(auth_manager=auth_manager)
        
        # Test the connection
        client.current_user()  # This will raise an exception if not authenticated
        
        logger.info("Successfully created Spotify client with client credentials")
        return client
    except SpotifyException as e:
        logger.error(f"Failed to create Spotify client: {str(e)}")
        raise

def get_playlist_tracks(spotify: spotipy.Spotify, playlist_id: str) -> List[Dict[str, Any]]:
    """Get all tracks from a Spotify playlist."""
    try:
        results = spotify.playlist_tracks(playlist_id)
        tracks = results['items']
        
        while results['next']:
            results = spotify.next(results)
            tracks.extend(results['items'])
            
        return tracks
    except SpotifyException as e:
        logger.error(f"Failed to get playlist tracks: {str(e)}")
        raise

def get_spotify_oauth_client() -> spotipy.Spotify:
    """
    Get a Spotify client using OAuth flow.
    This is for user-specific operations that require user authentication.
    """
    try:
        # Initialize the secure cache handler
        cache_handler = SecureCacheFileHandler(cache_path=SPOTIFY_TOKEN_PATH)
        
        # Create OAuth manager
        auth_manager = SpotifyOAuth(
            client_id=SPOTIFY_CLIENT_ID,
            client_secret=SPOTIFY_CLIENT_SECRET,
            redirect_uri=SPOTIFY_REDIRECT_URI,
            cache_handler=cache_handler,
            scope=[
                "user-library-read",
                "playlist-read-private",
                "playlist-read-collaborative",
                "playlist-modify-public",
                "playlist-modify-private"
            ]
        )
        
        # Create and return the client
        client = spotipy.Spotify(auth_manager=auth_manager)
        
        # Test the connection
        client.current_user()  # This will raise an exception if not authenticated
        
        logger.info("Successfully created Spotify OAuth client")
        return client
    except SpotifyException as e:
        logger.error(f"Failed to create Spotify OAuth client: {str(e)}")
        raise

def create_spotify_playlist(
    spotify: spotipy.Spotify,
    user_id: str,
    name: str,
    description: str = "",
    public: bool = False
) -> Optional[str]:
    """Create a new Spotify playlist."""
    try:
        playlist = spotify.user_playlist_create(
            user_id,
            name=name,
            description=description,
            public=public
        )
        return playlist['id']
    except SpotifyException as e:
        logger.error(f"Failed to create Spotify playlist: {str(e)}")
        raise

def add_tracks_to_spotify_playlist(
    spotify: spotipy.Spotify,
    playlist_id: str,
    track_ids: List[str]
) -> bool:
    """Add tracks to a Spotify playlist."""
    try:
        # Spotify API has a limit of 100 tracks per request
        for i in range(0, len(track_ids), 100):
            batch = track_ids[i:i + 100]
            spotify.playlist_add_items(playlist_id, batch)
        return True
    except SpotifyException as e:
        logger.error(f"Failed to add tracks to Spotify playlist: {str(e)}")
        raise
