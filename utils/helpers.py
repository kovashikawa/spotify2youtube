def create_search_query(track):
    """
    Given a Spotify track item (dictionary), return a string you can use to search on YouTube.
    Example: "Bohemian Rhapsody Queen"
    """
    track_name = track['name']
    # track['artists'] is usually a list; we’ll just take the first one
    artist_name = track['artists'][0]['name'] if track['artists'] else ''
    return f"{track_name} {artist_name}"
    