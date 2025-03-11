import firebase_admin
from firebase_admin import credentials, firestore
import datetime

if not firebase_admin._apps:
    cred = credentials.Certificate("config/keyFirestoreDB.json")
    firebase_admin.initialize_app(cred)

db = firestore.client()

def batch_store_playlist(playlist_collection: str, playlist_id: str, owner_id: str, tracks: list):
    """
    Store or update a playlist document in a single batch write.
    
    Args:
        playlist_collection (str): Collection name ("spotify_playlists" or "youtube_playlists").
        playlist_id (str): The primary key of the playlist.
        owner_id (str): The owner ID (spotify_owner_id or youtube_owner_id).
        tracks (list): List of track objects (each with IDs and other minimal metadata).
        
    This function writes the playlist document with all tracks embedded, minimizing separate calls.
    """
    batch = db.batch()
    doc_ref = db.collection(playlist_collection).document(playlist_id)
    data = {
        f"{playlist_collection.split('_')[0]}_owner_id": owner_id,
        "tracks": tracks,  # Assuming tracks is a list of embedded objects.
        "updated_at": firestore.SERVER_TIMESTAMP,
    }
    # If the document doesn't exist, we set created_at as well.
    data["created_at"] = firestore.SERVER_TIMESTAMP
    batch.set(doc_ref, data, merge=True)
    batch.commit()
    
def store_track_link(youtube_track_id: str, spotify_track_id: str, is_remix: bool):
    """
    Store or update a track link document.
    
    Combines both IDs into a composite document ID to avoid duplicates.
    """
    doc_id = f"{youtube_track_id}_{spotify_track_id}"
    doc_ref = db.collection("track_links").document(doc_id)
    data = {
        "youtube_track_id": youtube_track_id,
        "spotify_track_id": spotify_track_id,
        "is_remix": is_remix,
        "created_at": firestore.SERVER_TIMESTAMP,
        "updated_at": firestore.SERVER_TIMESTAMP,
    }
    doc_ref.set(data, merge=True)

def store_artist_link(youtube_artist_id: str, spotify_artist_id: str):
    """
    Store or update an artist link document.
    """
    doc_id = f"{youtube_artist_id}_{spotify_artist_id}"
    doc_ref = db.collection("artist_links").document(doc_id)
    data = {
        "youtube_artist_id": youtube_artist_id,
        "spotify_artist_id": spotify_artist_id,
        "created_at": firestore.SERVER_TIMESTAMP,
        "updated_at": firestore.SERVER_TIMESTAMP,
    }
    doc_ref.set(data, merge=True)

def get_track_link(youtube_track_id: str, spotify_track_id: str):
    """
    Retrieve a track link document from Firestore.
    """
    doc_id = f"{youtube_track_id}_{spotify_track_id}"
    doc_ref = db.collection("track_links").document(doc_id)
    doc = doc_ref.get()
    return doc.to_dict() if doc.exists else None
