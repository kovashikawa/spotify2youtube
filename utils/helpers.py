import re
import difflib

def create_search_query(track: dict) -> str:
    """
    Constructs a search query for YouTube based on a Spotify track.
    Uses the track name and primary artist, and removes extraneous phrases.
    """
    track_name = track.get("name", "")
    artist_name = track.get("artists", [{}])[0].get("name", "")
    query = f"{track_name} {artist_name}"

    # Remove common extraneous phrases
    query = re.sub(
        r'\b(official video|official audio|lyric video|HD|HQ|remaster(ed)?)\b',
        '',
        query,
        flags=re.IGNORECASE
        )
    
    # Normalize whitespace
    query = " ".join(query.split())
    return query

def create_spotify_search_query(video_title: str) -> str:
    """
    Constructs a search query for Spotify based on a YouTube video title.
    Cleans up the title by removing common extraneous words.
    """

    query = video_title

    # Remove common extraneous words
    query = re.sub(
        r'\b(official video|official audio|lyric video|HD|HQ|remaster(ed)?)\b',
        '',
        query, 
        flags=re.IGNORECASE)

    query = " ".join(query.split())
    return query

def choose_best_track(tracks, query):
    """
    Chooses the best matching track from a list based on similarity with the query.
    Uses difflib.SequenceMatcher to compare the query with each track's name.
    """
    best_match = None
    best_ratio = 0.0
    for track in tracks:
        track_name = track.get("name", "").lower()
        ratio = difflib.SequenceMatcher(None, query.lower(), track_name).ratio()
        if ratio > best_ratio:
            best_ratio = ratio
            best_match = track
    return best_match
