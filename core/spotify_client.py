
import os
import spotipy
from dotenv import load_dotenv
from spotipy.oauth2 import SpotifyClientCredentials, SpotifyOAuth
from config.settings import SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET

load_dotenv()

def get_spotify_client():
    """
    Returns an authenticated Spotipy client using client credentials flow.
    """

    client_credentials_manager = SpotifyClientCredentials(
        client_id=SPOTIFY_CLIENT_ID,
        client_secret=SPOTIFY_CLIENT_SECRET
    )

    return spotipy.Spotify(client_credentials_manager=client_credentials_manager)

def get_playlist_tracks(spotify, playlist_id):
    """
    Returns a list of track info (name, artist, etc.) from the given Spotify playlist.
    """
    tracks = []
    results = spotify.playlist_items(playlist_id)

    tracks.extend(results['items'])

    # Pagination
    while results['next']:
        results = spotify.next(results)
        tracks.extend(results['items'])

    return tracks

def get_spotify_oauth_client():
    """Returns a Spotify client for user-specific operations (e.g. playlist creation) using OAuth."""

    sp_oauth = SpotifyOAuth(
        client_id=os.getenv("SPOTIFY_CLIENT_ID"),
        client_secret=os.getenv("SPOTIFY_CLIENT_SECRET"),
        redirect_uri=os.getenv("SPOTIFY_REDIRECT_URI"),
        scope="playlist-modify-private playlist-modify-public",
        cache_path="config/.cache-spotify"
    )

    token_info = sp_oauth.get_cached_token()
    if not token_info:
        auth_url = sp_oauth.get_authorize_url()
        print(f"Please navigate here: {auth_url}")
        response = input("Paste the URL you were redirected to: ")
        # Extract code from the URL (a naive extraction – adjust as needed)
        code = response.split("code=")[-1]
        token_info = sp_oauth.get_access_token(code)

    return spotipy.Spotify(auth=token_info["access_token"])

def create_spotify_playlist(spotify, user_id, name, description):
    """Creates a new Spotify playlist and returns its ID."""

    playlist = spotify.user_playlist_create(
        user=user_id,
        name=name,
        public=False,
        description=description
        )

    return playlist.get("id")

def add_tracks_to_spotify_playlist(spotify, playlist_id, track_ids):
    """Adds a list of track IDs to a Spotify playlist."""

    spotify.user_playlist_add_tracks(
        user=spotify.current_user()["id"],
        playlist_id=playlist_id,
        tracks=track_ids
        )
