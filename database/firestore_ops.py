import firebase_admin
from firebase_admin import credentials, firestore
import datetime
from typing import Optional, Dict, Any, List
from config.firestore_config import FirestoreClient

# Initialize Firestore client
db = FirestoreClient().db

def get_existing_track_link(track_id: str, platform: str) -> Optional[Dict[str, Any]]:
    """
    Check if a track link exists for a given track ID from either platform.
    Returns the track link document if found, None otherwise.
    
    Args:
        track_id: The track ID to search for
        platform: 'spotify' or 'youtube'
    """
    track_links_ref = db.collection("track_links").document("spotify_youtube").collection("items")
    
    # Query based on the platform
    if platform == "spotify":
        query = track_links_ref.where("spotify_track_id", "==", track_id)
    else:  # youtube
        query = track_links_ref.where("youtube_track_id", "==", track_id)
    
    # Get the first matching document
    docs = query.limit(1).stream()
    for doc in docs:
        return doc.to_dict()
    return None

def store_user(user_id: str, spotify_id: str, youtube_id: str, email: str):
    """
    Store or update a user document.
    """
    doc_ref = db.collection("users").document(user_id)
    data = {
        "spotify_id": spotify_id,
        "youtube_id": youtube_id,
        "email": email,
        "created_at": firestore.SERVER_TIMESTAMP,
        "updated_at": firestore.SERVER_TIMESTAMP,
    }
    doc_ref.set(data, merge=True)

def store_track(track_id: str, platform: str, metadata: Dict[str, Any]):
    """
    Store or update a track document.
    platform: 'spotify' or 'youtube'
    """
    doc_ref = db.collection("tracks").document(platform).collection("items").document(track_id)
    data = {
        "metadata": metadata,
        "created_at": firestore.SERVER_TIMESTAMP,
        "updated_at": firestore.SERVER_TIMESTAMP,
    }
    doc_ref.set(data, merge=True)

def store_playlist(user_id: str, playlist_id: str, platform: str, metadata: Dict[str, Any], track_ids: List[str]):
    """
    Store or update a playlist document as a subcollection under the user.
    platform: 'spotify' or 'youtube'
    """
    # Store playlist metadata
    playlist_ref = db.collection("users").document(user_id).collection("playlists").document(playlist_id)
    playlist_data = {
        "platform": platform,
        "metadata": metadata,
        "track_count": len(track_ids),
        "created_at": firestore.SERVER_TIMESTAMP,
        "updated_at": firestore.SERVER_TIMESTAMP,
    }
    playlist_ref.set(playlist_data, merge=True)

    # Store track references in a subcollection
    tracks_ref = playlist_ref.collection("tracks")
    batch = db.batch()
    
    for track_id in track_ids:
        track_ref = tracks_ref.document(track_id)
        batch.set(track_ref, {
            "track_id": track_id,
            "added_at": firestore.SERVER_TIMESTAMP
        })
    
    batch.commit()

def store_track_link(spotify_track_id: str, youtube_track_id: str, is_remix: bool = False):
    """
    Store or update a track link document in a platform-based collection.
    """
    doc_id = f"{spotify_track_id}_{youtube_track_id}"
    doc_ref = db.collection("track_links").document("spotify_youtube").collection("items").document(doc_id)
    data = {
        "spotify_track_id": spotify_track_id,
        "youtube_track_id": youtube_track_id,
        "is_remix": is_remix,
        "created_at": firestore.SERVER_TIMESTAMP,
        "updated_at": firestore.SERVER_TIMESTAMP,
    }
    doc_ref.set(data, merge=True)

def get_user(user_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve a user document."""
    doc_ref = db.collection("users").document(user_id)
    doc = doc_ref.get()
    return doc.to_dict() if doc.exists else None

def get_track(track_id: str, platform: str) -> Optional[Dict[str, Any]]:
    """Retrieve a track document."""
    doc_ref = db.collection("tracks").document(platform).collection("items").document(track_id)
    doc = doc_ref.get()
    return doc.to_dict() if doc.exists else None

def get_playlist(user_id: str, playlist_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve a playlist document."""
    doc_ref = db.collection("users").document(user_id).collection("playlists").document(playlist_id)
    doc = doc_ref.get()
    return doc.to_dict() if doc.exists else None

def get_track_link(spotify_track_id: str, youtube_track_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve a track link document."""
    doc_id = f"{spotify_track_id}_{youtube_track_id}"
    doc_ref = db.collection("track_links").document("spotify_youtube").collection("items").document(doc_id)
    doc = doc_ref.get()
    return doc.to_dict() if doc.exists else None

def get_user_playlists(user_id: str, platform: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieve all playlists for a user, optionally filtered by platform."""
    query = db.collection("users").document(user_id).collection("playlists")
    if platform:
        query = query.where("platform", "==", platform)
    return [doc.to_dict() for doc in query.stream()]

def get_playlist_tracks(user_id: str, playlist_id: str) -> List[Dict[str, Any]]:
    """Retrieve all tracks for a playlist."""
    playlist = get_playlist(user_id, playlist_id)
    if not playlist:
        return []
    
    # Get track references
    tracks_ref = db.collection("users").document(user_id).collection("playlists").document(playlist_id).collection("tracks")
    track_refs = tracks_ref.stream()
    
    # Get track details
    tracks = []
    for track_ref in track_refs:
        track_data = track_ref.to_dict()
        platform = playlist["platform"]
        track = get_track(track_data["track_id"], platform)
        if track:
            tracks.append(track)
    
    return tracks

def get_all_tracks() -> List[Dict[str, Any]]:
    """
    Fetch all tracks from Firestore.
    
    WARNING: This function should be used sparingly and only for migration/backup purposes.
    It performs a full collection scan which can be expensive and slow for large datasets.
    For regular application use, prefer querying specific tracks or using pagination.
    
    Returns:
        List of track documents with their metadata
    """
    tracks = []
    users_ref = db.collection("users")
    
    for user_doc in users_ref.stream():
        playlists_ref = user_doc.reference.collection("playlists")
        
        for playlist_doc in playlists_ref.stream():
            playlist_data = playlist_doc.to_dict()
            platform = playlist_data.get("platform", "spotify")  # Default to spotify if not specified
            
            # Get tracks subcollection
            tracks_ref = playlist_doc.reference.collection("tracks")
            
            for track_ref in tracks_ref.stream():
                track_data = track_ref.to_dict()
                track_id = track_data.get("track_id")
                
                if not track_id:
                    continue
                
                # Get the actual track metadata from the tracks collection
                track_metadata = get_track(track_id, platform)
                if not track_metadata:
                    continue
                
                # Combine the data
                combined_data = {
                    "doc_id": track_ref.id,
                    "user_id": user_doc.id,
                    "playlist_id": playlist_doc.id,
                    "track_id": track_id,
                    "platform": platform,
                    "vector_indexed": track_data.get("vector_indexed", False),
                    "added_at": track_data.get("added_at"),
                    **track_metadata.get("metadata", {})  # Spread the track metadata
                }
                
                if not combined_data.get("vector_indexed", False):
                    tracks.append(combined_data)
    
    return tracks
