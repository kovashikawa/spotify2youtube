# spotify2youtube
Transfer playlists from spotify to youtube with python

---

## how to use this:
create a `.env` file in the root of your project with the following variables:

```txt
SPOTIFY_CLIENT_ID=your-spotify-client-id
SPOTIFY_CLIENT_SECRET=your-spotify-client-secret
YOUTUBE_API_KEY=your-youtube-api-key
```

---

## folder structure:
```
spotify2youtube/
├── config/
│   ├── __init__.py
│   └── settings.py
├── core/
│   ├── __init__.py
│   ├── spotify_client.py       # Contains both client credentials and OAuth functions
│   └── youtube_client.py       # Contains YouTube OAuth and playlist functions
├── routers/
│   ├── __init__.py
│   ├── connection.py           # For testing connectivity
│   └── playlist.py             # Contains both conversion endpoints
├── utils/
│   ├── __init__.py
│   ├── logger.py
│   └── helpers.py              # Contains helper functions (like query builders)
├── main.py
├── requirements.txt
├── .env
└── config/
    └── credentials.json        # OAuth client secrets for YouTube
```