import os
import spotipy
from dotenv import load_dotenv
from spotipy.oauth2 import SpotifyClientCredentials, SpotifyOAuth
from spotipy.exceptions import SpotifyException
from config.settings import SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET, SPOTIFY_REDIRECT_URI

load_dotenv()

# Cache paths
SPOTIFY_TOKEN_CACHE = "config/.spotify_token"

def get_spotify_client():
    """
    Returns an authenticated Spotipy client using client credentials flow.
    Handles token refresh and error cases.
    """
    try:
        if not SPOTIFY_CLIENT_ID or not SPOTIFY_CLIENT_SECRET:
            raise ValueError("Spotify credentials not found in environment variables")

        client_credentials_manager = SpotifyClientCredentials(
            client_id=SPOTIFY_CLIENT_ID,
            client_secret=SPOTIFY_CLIENT_SECRET
        )
        
        # Test the connection
        client = spotipy.Spotify(client_credentials_manager=client_credentials_manager)
        # Test the connection with a simple API call
        client.search('test', limit=1)
        return client
    except Exception as e:
        print(f"Error initializing Spotify client: {e}")
        raise

def get_playlist_tracks(spotify, playlist_id):
    """
    Returns a list of track info from the given Spotify playlist.
    Handles pagination and error cases.
    """
    try:
        tracks = []
        results = spotify.playlist_items(playlist_id)
        tracks.extend(results['items'])

        # Pagination
        while results['next']:
            results = spotify.next(results)
            tracks.extend(results['items'])

        return tracks
    except SpotifyException as e:
        print(f"Error fetching playlist tracks: {e}")
        return []

def get_spotify_oauth_client():
    """
    Returns a Spotify client for user-specific operations using OAuth.
    Handles token refresh, expiration, and error cases.
    """
    try:
        if not SPOTIFY_CLIENT_ID or not SPOTIFY_CLIENT_SECRET or not SPOTIFY_REDIRECT_URI:
            raise ValueError("Spotify credentials or redirect URI not found in environment variables")

        sp_oauth = SpotifyOAuth(
            client_id=SPOTIFY_CLIENT_ID,
            client_secret=SPOTIFY_CLIENT_SECRET,
            redirect_uri=SPOTIFY_REDIRECT_URI,
            scope="playlist-modify-private playlist-modify-public",
            cache_path=SPOTIFY_TOKEN_CACHE
        )

        # Try to get cached token
        token_info = sp_oauth.get_cached_token()
        
        if token_info:
            # Check if token is expired
            if sp_oauth.is_token_expired(token_info):
                # Try to refresh the token
                try:
                    token_info = sp_oauth.refresh_access_token(token_info['refresh_token'])
                except Exception as e:
                    print(f"Error refreshing token: {e}")
                    # If refresh fails, clear cache and force new auth
                    if os.path.exists(SPOTIFY_TOKEN_CACHE):
                        os.remove(SPOTIFY_TOKEN_CACHE)
                    token_info = None

        # If no valid token, start new auth flow
        if not token_info:
            auth_url = sp_oauth.get_authorize_url()
            print(f"Please navigate here: {auth_url}")
            response = input("Paste the URL you were redirected to: ")
            code = sp_oauth.parse_response_code(response)
            token_info = sp_oauth.get_access_token(code)

        # Create client with token
        client = spotipy.Spotify(auth=token_info["access_token"])
        
        # Test the connection
        try:
            client.current_user()
        except SpotifyException as e:
            print(f"Error validating token: {e}")
            # If token is invalid, clear cache and try again
            if os.path.exists(SPOTIFY_TOKEN_CACHE):
                os.remove(SPOTIFY_TOKEN_CACHE)
            return get_spotify_oauth_client()
            
        return client

    except Exception as e:
        print(f"Error in OAuth flow: {e}")
        # If there's an error, clear the cache and try again
        if os.path.exists(SPOTIFY_TOKEN_CACHE):
            os.remove(SPOTIFY_TOKEN_CACHE)
        raise

def create_spotify_playlist(spotify, user_id, name, description):
    """Creates a new Spotify playlist and returns its ID."""
    try:
        playlist = spotify.user_playlist_create(
            user=user_id,
            name=name,
            public=False,
            description=description
        )
        return playlist.get("id")
    except SpotifyException as e:
        print(f"Error creating playlist: {e}")
        return None

def add_tracks_to_spotify_playlist(spotify, playlist_id, track_ids):
    """Adds a list of track IDs to a Spotify playlist."""
    try:
        spotify.user_playlist_add_tracks(
            user=spotify.current_user()["id"],
            playlist_id=playlist_id,
            tracks=track_ids
        )
        return True
    except SpotifyException as e:
        print(f"Error adding tracks to playlist: {e}")
        return False
