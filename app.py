from core.spotify_client import get_spotify_client, get_playlist_tracks
from core.youtube_client import (
    get_youtube_service_oauth,
    create_youtube_playlist,
    add_video_to_playlist
)
from utils.helpers import create_search_query

def main():
    # 1. Spotify
    spotify = get_spotify_client()
    playlist_id = "2uzV2b2iL7mEccikj405EM"  # or pass via argument
    spotify_tracks = get_playlist_tracks(spotify, playlist_id)

    # 2. YouTube (choose API key or OAuth approach)

    ### If only searching:
    # youtube = get_youtube_service_api_key()
    # for each track, search for the track. 
    # (You wouldn't be able to create a playlist on a user’s channel with just an API key.)

    ### If creating a playlist on your own channel:
    youtube = get_youtube_service_oauth()
    youtube_playlist_id = create_youtube_playlist(
        youtube,
        title="My Spotify2YouTube Playlist",
        description="Auto-created playlist",
        privacy_status="private"  # or "public", "unlisted"
    )

    # 3. Loop tracks, search, and add
    for item in spotify_tracks:
        if item['track'] is None:
            continue
        query = create_search_query(item['track'])
        
        # If using an API key for searching:
        # video_id = search_youtube(youtube_api_key_service, query)
        
        # If using same OAuth-based service to search:
        video_id = search_youtube(youtube, query)
        
        if video_id:
            add_video_to_playlist(youtube, youtube_playlist_id, video_id)
            print(f"Added to playlist: {query} (Video ID: {video_id})")
        else:
            print(f"No YouTube match for: {query}")

if __name__ == "__main__":
    main()
    