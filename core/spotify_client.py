import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from config.settings import SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET

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