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
├── app.py
├── requirements.txt
├── .gitignore
├── .env                      # environment variables
├── README.md
├── config/
│   ├── __init__.py
│   ├── credentials.json      # (if using OAuth for YouTube)
│   └── settings.py
├── core/
│   ├── __init__.py
│   ├── spotify_client.py     # handles Spotify logic
│   └── youtube_client.py     # handles YouTube logic
└── utils/
    ├── __init__.py
    └── helpers.py            # convenience functions
```