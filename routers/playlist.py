from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import logging

# Import functions for Spotify → YouTube conversion
from core.spotify_client import (
    get_spotify_client,
    get_playlist_tracks,
    get_spotify_oauth_client, 
    create_spotify_playlist,
    add_tracks_to_spotify_playlist
    )
from core.youtube_client import (
    get_youtube_service_oauth,
    create_youtube_playlist,
    add_video_to_playlist,
    search_youtube,
    get_youtube_playlist_items
)

from utils.helpers import create_search_query, create_spotify_search_query, choose_best_track

router = APIRouter()

# --- Endpoint: Spotify → YouTube Conversion ---
class SpotifyToYouTubeConversionRequest(BaseModel):
    spotify_playlist_id: str
    youtube_playlist_title: str
    youtube_playlist_description: str = "Created by Spotify2YouTube"

@router.post("/playlist/spotify-to-youtube", summary="Convert a Spotify playlist to a YouTube playlist")
async def convert_spotify_to_youtube(request: SpotifyToYouTubeConversionRequest):
    try:
        # Retrieve Spotify tracks
        spotify = get_spotify_client()
        spotify_tracks = get_playlist_tracks(spotify, request.spotify_playlist_id)
        if not spotify_tracks:
            raise HTTPException(status_code=404, detail="Spotify playlist not found or empty.")

        # Create YouTube playlist
        youtube = get_youtube_service_oauth()
        youtube_playlist_id = create_youtube_playlist(
            youtube,
            title=request.youtube_playlist_title,
            description=request.youtube_playlist_description
        )
        if not youtube_playlist_id:
            raise HTTPException(status_code=500, detail="Failed to create YouTube playlist.")

        added_videos = []
        for item in spotify_tracks:
            if item.get("track") is None:
                continue
            track = item["track"]
            # Build improved search query for YouTube
            query = create_search_query(track)
            video_id = search_youtube(youtube, query)
            if video_id:
                add_video_to_playlist(youtube, youtube_playlist_id, video_id)
                added_videos.append({
                    "track": track.get("name"),
                    "artist": track.get("artists", [{}])[0].get("name", ""),
                    "video_id": video_id
                })
            else:
                logging.warning(f"Video not found for query: {query}")

        return {
            "youtube_playlist_id": youtube_playlist_id,
            "added_videos": added_videos,
            "message": "Spotify to YouTube conversion successful"
        }
    except Exception as e:
        logging.error("Error converting Spotify playlist", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

# --- Endpoint: YouTube → Spotify Conversion ---
class YouTubeToSpotifyConversionRequest(BaseModel):
    youtube_playlist_id: str
    spotify_playlist_name: str
    spotify_playlist_description: str = "Created by YouTube2Spotify conversion"

@router.post("/playlist/youtube-to-spotify", summary="Convert a YouTube playlist to a Spotify playlist")
async def convert_youtube_to_spotify(request: YouTubeToSpotifyConversionRequest):
    try:
        # Initialize YouTube client and fetch playlist items
        youtube = get_youtube_service_oauth()
        youtube_items = get_youtube_playlist_items(youtube, request.youtube_playlist_id)
        if not youtube_items:
            raise HTTPException(status_code=404, detail="YouTube playlist not found or empty.")

        # Initialize Spotify OAuth client for user-specific operations
        spotify = get_spotify_oauth_client()
        user_id = spotify.current_user()["id"]

        track_ids = []
        for item in youtube_items:
            snippet = item.get("snippet", {})
            video_title = snippet.get("title")
            if not video_title:
                continue
            # Build an improved search query for Spotify
            query = create_spotify_search_query(video_title)
            results = spotify.search(q=query, type="track", limit=3)
            tracks = results.get("tracks", {}).get("items", [])
            if tracks:
                best_track = choose_best_track(tracks, query)
                if best_track:
                    track_ids.append(best_track["id"])
                else:
                    logging.warning(f"No best match found for query: {query}")
            else:
                logging.warning(f"Spotify track not found for query: {query}")

        if not track_ids:
            raise HTTPException(status_code=404, detail="No matching Spotify tracks found for the YouTube playlist.")

        # Create a new Spotify playlist and add the found tracks
        playlist_id = create_spotify_playlist(spotify, user_id, request.spotify_playlist_name, request.spotify_playlist_description)
        add_tracks_to_spotify_playlist(spotify, playlist_id, track_ids)

        return {
            "spotify_playlist_id": playlist_id,
            "added_tracks": len(track_ids),
            "message": "YouTube to Spotify conversion successful"
        }
    except Exception as e:
        logging.error("Error converting YouTube playlist to Spotify", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    