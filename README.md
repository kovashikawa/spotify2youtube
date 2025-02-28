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
│   ├── spotify_client.py
│   └── youtube_client.py
├── database/
│   ├── __init__.py
│   └── firestore_ops.py
├── routers/
│   ├── __init__.py
│   ├── connection.py
│   └── playlist.py
├── utils/
│   ├── __init__.py
│   ├── helpers.py
│   └── logger.py
├── main.py
├── requirements.txt
├── .env
└── config/
    └── credentials.json
```