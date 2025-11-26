from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, ConfigDict

from utils.helpers import create_search_query, create_spotify_search_query, choose_best_track
from utils.logger import setup_logger
from database.firestore_ops import (
    store_user, store_track, store_playlist, store_track_link,
    get_user, get_track, get_playlist, get_track_link,
    get_existing_track_link
)

logger = setup_logger(__name__)

# Import functions for Spotify2YouTube conversion
from core.spotify_client import (
    get_spotify_oauth_client,
    get_playlist_tracks,
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

router = APIRouter()

# --- Endpoint: Spotify2YouTube Conversion
class SpotifyToYouTubeConversionRequest(BaseModel):
    spotify_playlist_id: str = Field(..., example="2uzV2b2iL7mEccikj405EM")
    youtube_playlist_title: str = Field(..., example="Liked from Radio (spotify)")
    youtube_playlist_description: str = Field(
        "Created by Spotify2YouTube",
        example="Created by Spotify2YouTube"
    )
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "spotify_playlist_id": "2uzV2b2iL7mEccikj405EM",
                "youtube_playlist_title": "Liked from Radio (spotify)",
                "youtube_playlist_description": "Created by Spotify2YouTube"
            }
        }
    )

@router.post("/playlist/spotify-to-youtube", summary="Convert a Spotify playlist to a YouTube playlist")
async def convert_spotify_to_youtube(request: SpotifyToYouTubeConversionRequest):
    try:
        logger.info("Starting Spotify to YouTube conversion")
        cache_hits = 0
        api_calls = 0

        # Initialize clients with OAuth
        spotify = get_spotify_oauth_client()
        youtube = get_youtube_service_oauth()
        
        # Get user information
        spotify_user = spotify.current_user()
        youtube_user = youtube.channels().list(part="id,snippet", mine=True).execute()["items"][0]
        
        # Store or update user information
        store_user(
            user_id=spotify_user["id"],
            spotify_id=spotify_user["id"],
            youtube_id=youtube_user["id"],
            email=spotify_user.get("email", "")
        )

        # Retrieve Spotify tracks
        spotify_tracks = get_playlist_tracks(spotify, request.spotify_playlist_id)
        if not spotify_tracks:
            raise HTTPException(status_code=404, detail="Spotify playlist not found or empty.")

        logger.info(f"Found {len(spotify_tracks)} tracks in Spotify playlist")

        # Create YouTube playlist
        youtube_playlist_id = create_youtube_playlist(
            youtube,
            title=request.youtube_playlist_title,
            description=request.youtube_playlist_description
        )
        if not youtube_playlist_id:
            raise HTTPException(status_code=500, detail="Failed to create YouTube playlist.")

        added_videos = []
        spotify_track_ids = []
        
        for item in spotify_tracks:
            if item.get("track") is None:
                continue
            track = item["track"]
            
            # Store Spotify track
            store_track(
                track_id=track["id"],
                platform="spotify",
                metadata={
                    "name": track["name"],
                    "artist": track["artists"][0]["name"],
                    "album": track["album"]["name"],
                    "duration_ms": track["duration_ms"],
                    "popularity": track.get("popularity", 0)
                }
            )
            spotify_track_ids.append(track["id"])

            # Check for existing track link
            existing_link = get_existing_track_link(track["id"], "spotify")
            if existing_link:
                cache_hits += 1
                logger.info(f"Cache hit: Found existing track link for Spotify track '{track['name']}' by {track['artists'][0]['name']}")
                video_id = existing_link["youtube_track_id"]
                add_video_to_playlist(youtube, youtube_playlist_id, video_id)
                added_videos.append({
                    "track": track.get("name"),
                    "artist": track.get("artists", [{}])[0].get("name", ""),
                    "video_id": video_id,
                    "source": "cache"
                })
                continue

            # Build improved search query for YouTube
            query = create_search_query(track)            
            api_calls += 1
            logger.info(f"Cache miss: Searching YouTube for '{track['name']}' by {track['artists'][0]['name']}")
            video_id = search_youtube(youtube, query)

            if video_id:
                add_video_to_playlist(youtube, youtube_playlist_id, video_id)
                
                # Store YouTube track
                store_track(
                    track_id=video_id,
                    platform="youtube",
                    metadata={
                        "title": track["name"],
                        "artist": track["artists"][0]["name"],
                        "channelTitle": youtube_user["snippet"]["title"]
                    }
                )
                
                # Store track link
                store_track_link(track["id"], video_id, False)
                
                added_videos.append({
                    "track": track.get("name"),
                    "artist": track.get("artists", [{}])[0].get("name", ""),
                    "video_id": video_id,
                    "source": "api"
                })

                logger.info(f"Added video {video_id} for track {track.get('name')}")

            else:
                logger.warning(f"No match found for '{track['name']}' by {track['artists'][0]['name']}")

        # Store playlists
        store_playlist(
            user_id=spotify_user["id"],
            playlist_id=request.spotify_playlist_id,
            platform="spotify",
            metadata={
                "name": request.youtube_playlist_title,
                "description": request.youtube_playlist_description
            },
            track_ids=spotify_track_ids
        )

        store_playlist(
            user_id=spotify_user["id"],
            playlist_id=youtube_playlist_id,
            platform="youtube",
            metadata={
                "title": request.youtube_playlist_title,
                "description": request.youtube_playlist_description
            },
            track_ids=[video["video_id"] for video in added_videos]
        )

        # Log performance metrics
        total_tracks = len(spotify_track_ids)
        cache_hit_rate = (cache_hits / total_tracks * 100) if total_tracks > 0 else 0
        logger.info(f"Conversion completed. Performance metrics:")
        logger.info(f"- Total tracks: {total_tracks}")
        logger.info(f"- Cache hits: {cache_hits}")
        logger.info(f"- API calls: {api_calls}")
        logger.info(f"- Cache hit rate: {cache_hit_rate:.1f}%")
        logger.info(f"- API calls saved: {cache_hits}")

        return {
            "youtube_playlist_id": youtube_playlist_id,
            "added_videos": added_videos,
            "message": "Spotify to YouTube conversion successful",
            "performance": {
                "total_tracks": total_tracks,
                "cache_hits": cache_hits,
                "api_calls": api_calls,
                "cache_hit_rate": f"{cache_hit_rate:.1f}%",
                "api_calls_saved": cache_hits
            }
        }
    except Exception as e:
        logger.error("Error converting Spotify playlist", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

# --- Endpoint: YouTube → Spotify Conversion
class YouTubeToSpotifyConversionRequest(BaseModel):
    youtube_playlist_id: str = Field(..., example="PLxxxxxxxx")
    spotify_playlist_name: str = Field(..., example="YouTube Playlist")
    spotify_playlist_description: str = Field(
        "Created by Spotify2YouTube",
        example="Created by Spotify2YouTube"
    )
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "youtube_playlist_id": "PLxxxxxxxx",
                "spotify_playlist_name": "YouTube Playlist",
                "spotify_playlist_description": "Created by Spotify2YouTube"
            }
        }
    )

@router.post("/playlist/youtube-to-spotify", summary="Convert a YouTube playlist to a Spotify playlist")
async def convert_youtube_to_spotify(request: YouTubeToSpotifyConversionRequest):
    try:
        logger.info("Starting YouTube to Spotify conversion")
        cache_hits = 0
        api_calls = 0

        # Initialize clients with OAuth
        spotify = get_spotify_oauth_client()
        youtube = get_youtube_service_oauth()
        
        # Get user information
        spotify_user = spotify.current_user()
        youtube_user = youtube.channels().list(part="id,snippet", mine=True).execute()["items"][0]
        
        # Store or update user information
        store_user(
            user_id=spotify_user["id"],
            spotify_id=spotify_user["id"],
            youtube_id=youtube_user["id"],
            email=spotify_user.get("email", "")
        )

        # Retrieve YouTube playlist items
        youtube_tracks = get_youtube_playlist_items(youtube, request.youtube_playlist_id)
        if not youtube_tracks:
            raise HTTPException(status_code=404, detail="YouTube playlist not found or empty.")

        logger.info(f"Found {len(youtube_tracks)} tracks in YouTube playlist")

        track_ids = []
        youtube_track_ids = []
        added_tracks = []
        
        for item in youtube_tracks:
            video_id = item["snippet"]["resourceId"]["videoId"]
            video_title = item["snippet"]["title"]
            
            # Store YouTube track
            store_track(
                track_id=video_id,
                platform="youtube",
                metadata={
                    "title": video_title,
                    "channelTitle": item["snippet"]["channelTitle"]
                }
            )
            youtube_track_ids.append(video_id)

            # Check for existing track link
            existing_link = get_existing_track_link(video_id, "youtube")
            if existing_link:
                cache_hits += 1
                logger.info(f"Cache hit: Found existing track link for YouTube video '{video_title}'")
                spotify_track_id = existing_link["spotify_track_id"]
                track_ids.append(spotify_track_id)
                added_tracks.append({
                    "id": spotify_track_id,
                    "name": video_title,
                    "source": "cache"
                })
                continue

            # Search for the track on Spotify
            query = create_spotify_search_query(video_title)
            api_calls += 1
            logger.info(f"Cache miss: Searching Spotify for '{video_title}'")
            tracks = spotify.search(q=query, type="track", limit=5)["tracks"]["items"]
            
            if tracks:
                best_track = choose_best_track(tracks, query)
                logger.info(f"Selected track {best_track['name']} for query: {query}")

                if best_track:
                    track_ids.append(best_track["id"])
                    # Store Spotify track
                    store_track(
                        track_id=best_track["id"],
                        platform="spotify",
                        metadata={
                            "name": best_track["name"],
                            "artist": best_track["artists"][0]["name"],
                            "album": best_track["album"]["name"],
                            "duration_ms": best_track["duration_ms"],
                            "popularity": best_track.get("popularity", 0)
                        }
                    )
                    # Store track link
                    store_track_link(best_track["id"], video_id, False)
                    added_tracks.append({
                        "id": best_track["id"],
                        "name": best_track["name"],
                        "artist": best_track["artists"][0]["name"],
                        "album": best_track["album"]["name"],
                        "source": "api"
                    })
                else:
                    logger.warning(f"No best match found for query: {query}")
            else:
                logger.warning(f"Spotify track not found for query: {query}")

        if not track_ids:
            raise HTTPException(status_code=404, detail="No matching Spotify tracks found for the YouTube playlist.")

        # Create a new Spotify playlist and add the found tracks
        playlist_id = create_spotify_playlist(spotify, spotify_user["id"], request.spotify_playlist_name, request.spotify_playlist_description)
        add_tracks_to_spotify_playlist(spotify, playlist_id, track_ids)

        # Store playlists
        store_playlist(
            user_id=spotify_user["id"],
            playlist_id=request.youtube_playlist_id,
            platform="youtube",
            metadata={
                "title": request.spotify_playlist_name,
                "description": request.spotify_playlist_description
            },
            track_ids=youtube_track_ids
        )

        store_playlist(
            user_id=spotify_user["id"],
            playlist_id=playlist_id,
            platform="spotify",
            metadata={
                "name": request.spotify_playlist_name,
                "description": request.spotify_playlist_description
            },
            track_ids=[track["id"] for track in added_tracks]
        )

        # Log performance metrics
        total_tracks = len(youtube_track_ids)
        cache_hit_rate = (cache_hits / total_tracks * 100) if total_tracks > 0 else 0
        logger.info(f"Conversion completed. Performance metrics:")
        logger.info(f"- Total tracks: {total_tracks}")
        logger.info(f"- Cache hits: {cache_hits}")
        logger.info(f"- API calls: {api_calls}")
        logger.info(f"- Cache hit rate: {cache_hit_rate:.1f}%")
        logger.info(f"- API calls saved: {cache_hits}")

        return {
            "spotify_playlist_id": playlist_id,
            "added_tracks": added_tracks,
            "message": "YouTube to Spotify conversion successful",
            "performance": {
                "total_tracks": total_tracks,
                "cache_hits": cache_hits,
                "api_calls": api_calls,
                "cache_hit_rate": f"{cache_hit_rate:.1f}%",
                "api_calls_saved": cache_hits
            }
        }
    except Exception as e:
        logger.error("Error converting YouTube playlist to Spotify", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    