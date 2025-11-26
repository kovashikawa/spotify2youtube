# Spotify2YouTube

A FastAPI application that converts playlists between Spotify and YouTube.

## Features

- Convert Spotify playlists to YouTube playlists
- Convert YouTube playlists to Spotify playlists
- Caching system to reduce API calls
- Detailed logging and performance metrics
- Docker support for easy deployment

## Prerequisites

- Python 3.11 or higher
- Docker and Docker Compose (for containerized deployment)
- Spotify Developer Account
- YouTube API Credentials
- Firebase/Firestore Project

## Environment Setup

1. Copy the environment template:
   ```bash
   cp .env.example .env
   ```

2. Fill in your credentials in the `.env` file:
   - Spotify Client ID and Secret
   - YouTube API Key
   - Firestore Project ID

## Local Development Setup

1. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Run the application:
   ```bash
   uvicorn main:app --reload
   ```

## Docker Setup

1. Build and start the containers:
   ```bash
   docker-compose up --build
   ```

2. The application will be available at `http://localhost:8000`

3. To stop the containers:
   ```bash
   docker-compose down
   ```

## Airflow Integration

The project now includes Apache Airflow integration for automated playlist synchronization. This setup ensures your Firestore database is always populated with fresh user playlists, tracks, and cross-links.

### Airflow Setup

1. The Airflow stack is configured in `docker-compose.yml` and includes:
   - Airflow webserver and scheduler
   - PostgreSQL database
   - Mounted volumes for DAGs and credentials

2. Credential Management:
   - Place your credentials in the `credentials/` directory:
     - `service_account.json` (GCP service account)
     - `.youtube_token` (YouTube OAuth pickle)
   - Environment variables in `.env` (Spotify and Firebase configs)

3. Starting Airflow:
   ```bash
   docker-compose up --build
   ```
   - Access the Airflow UI at `http://localhost:8080` (admin/admin)
   - Unpause the `spotify_youtube_sync` DAG to start synchronization

### DAG Details

The `spotify_youtube_sync` DAG:
- Runs every 6 hours
- Authenticates with Spotify
- Fetches user playlists
- Processes tracks and creates YouTube links
- Stores everything in Firestore

### Important Considerations

1. Rate Limits:
   - Spotify: 10,000 requests/day
   - YouTube: 10,000 units/day
   - Consider adjusting the schedule or implementing throttling

2. Firestore Costs:
   - Each track requires a write operation
   - Consider partitioning old data to GCS for cost optimization

3. YouTube Matching:
   - Current implementation uses basic first-hit search
   - Future improvements could include fuzzy matching or YouTube Music API

4. Multi-User Support:
   - Currently configured for single user
   - Can be extended using Airflow Variables/Secrets for multiple users

5. Development Notes:
   - The repo is mounted directly into the Airflow container
   - Future improvement: Package as pip-installable module

## API Documentation

Once the application is running, you can access:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Project Structure

```
spotify2youtube/
├── config/
│   ├── settings.py
│   └── firestore_config.py
├── core/
│   ├── spotify_client.py
│   └── youtube_client.py
├── database/
│   └── firestore_ops.py
├── routers/
│   └── playlist.py
├── utils/
│   ├── helpers.py
│   └── logger.py
├── main.py
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── .env.example
└── README.md
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details. 