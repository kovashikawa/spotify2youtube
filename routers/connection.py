from fastapi import APIRouter, HTTPException
from core.spotify_client import get_spotify_client
from core.youtube_client import get_youtube_service_oauth

router = APIRouter()

@router.get("/connect", summary="Test connection to Spotify and YouTube APIs")
async def test_connection():
    try:
        # Initialize the Spotify client
        spotify = get_spotify_client()
        if not spotify:
            raise Exception("Spotify client initialization failed.")

        # Initialize the YouTube client (this may trigger the OAuth flow)
        youtube = get_youtube_service_oauth()
        if not youtube:
            raise Exception("YouTube client initialization failed.")

        return {"status": "Connected to both Spotify and YouTube successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    