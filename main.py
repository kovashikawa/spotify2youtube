from fastapi import FastAPI
from routers import connection, playlist

app = FastAPI(
    title="Spotify and YouTube Playlist Converter",
    description="Convert playlists between Spotify and YouTube.",
    version="1.0.0"
)

app.include_router(connection.router, prefix="/api")
app.include_router(playlist.router, prefix="/api")
