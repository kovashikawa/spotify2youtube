# Spotify2YouTube

A FastAPI application that converts playlists between Spotify and YouTube, with Firestore integration for persistent storage.

## Features

- Convert Spotify playlists to YouTube playlists
- Convert YouTube playlists to Spotify playlists
- Persistent storage of playlists and track information in Firestore
- Intelligent track matching between platforms
- User authentication and data management
- Efficient database structure for optimal performance

## Project Structure

```
spotify2youtube/
├── config/
│   ├── settings.py           # Application settings and environment variables
│   ├── firestore_config.py   # Firestore client configuration
│   └── firestore-credentials.json  # Firestore service account credentials
├── core/
│   ├── spotify_client.py     # Spotify API client implementation
│   └── youtube_client.py     # YouTube API client implementation
├── database/
│   └── firestore_ops.py      # Firestore database operations
├── routers/
│   └── playlist.py          # API endpoints for playlist conversion
├── utils/
│   ├── helpers.py           # Helper functions for track matching
│   └── logger.py            # Logging configuration
└── main.py                  # Application entry point
```

## Database Structure

The application uses Firestore with the following optimized structure:

### Collections

1. **users**
   - Document ID: User's unique ID
   - Fields:
     - spotify_id: Spotify user ID
     - youtube_id: YouTube user ID
     - email: User's email
     - created_at: Timestamp
     - updated_at: Timestamp
   - Subcollections:
     - playlists: User's playlists

2. **tracks**
   - Document ID: Platform name (spotify/youtube)
   - Subcollections:
     - items
       - Document ID: Track ID
       - Fields:
         - metadata: Platform-specific track information
         - created_at: Timestamp
         - updated_at: Timestamp

3. **track_links**
   - Document ID: Platform combination (spotify_youtube)
   - Subcollections:
     - items
       - Document ID: Combined track IDs
       - Fields:
         - spotify_track_id: Spotify track ID
         - youtube_track_id: YouTube track ID
         - is_remix: Boolean flag
         - created_at: Timestamp
         - updated_at: Timestamp

### Playlist Structure (Subcollection under users)
- Document ID: Playlist ID
- Fields:
  - platform: Platform name (spotify/youtube)
  - metadata: Platform-specific playlist information
  - track_count: Number of tracks
  - created_at: Timestamp
  - updated_at: Timestamp
- Subcollections:
  - tracks: Track references with timestamps

## Setup

1. Clone the repository:
```bash
git clone https://github.com/yourusername/spotify2youtube.git
cd spotify2youtube
```

2. Create a virtual environment and install dependencies:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

3. Set up environment variables in `.env`:
```env
SPOTIFY_CLIENT_ID=your_spotify_client_id
SPOTIFY_CLIENT_SECRET=your_spotify_client_secret
YOUTUBE_API_KEY=your_youtube_api_key
FIRESTORE_PROJECT_ID=your_firestore_project_id
```

4. Set up Firestore:
   - Create a new Firestore project in Google Cloud Console
   - Download the service account credentials JSON file
   - Place it in `config/firestore-credentials.json`

5. Run the application:
```bash
uvicorn main:app --reload
```

## API Endpoints

### Convert Spotify to YouTube
```http
POST /playlist/spotify-to-youtube
Content-Type: application/json

{
    "spotify_playlist_id": "your_spotify_playlist_id",
    "youtube_playlist_title": "Your Playlist Title",
    "youtube_playlist_description": "Optional description"
}
```

### Convert YouTube to Spotify
```http
POST /playlist/youtube-to-spotify
Content-Type: application/json

{
    "youtube_playlist_id": "your_youtube_playlist_id",
    "spotify_playlist_name": "Your Playlist Name",
    "spotify_playlist_description": "Optional description"
}
```

## Database Operations

The application provides efficient database operations for:
- Storing and retrieving user information
- Managing playlists and their tracks
- Storing track metadata from both platforms
- Maintaining track links between platforms
- Optimized querying using Firestore's hierarchical structure

## Performance Considerations

The database structure is optimized for:
- Efficient querying using subcollections
- Reduced read/write operations
- Better data locality
- Improved scalability
- Platform-specific data separation

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details. 