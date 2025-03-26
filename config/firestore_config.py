from google.cloud import firestore
from google.oauth2 import service_account
import os
from typing import Optional, Dict, Any
from config.settings import FIRESTORE_PROJECT_ID

class FirestoreClient:
    _instance: Optional['FirestoreClient'] = None
    _db: Optional[firestore.Client] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(FirestoreClient, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if self._db is None:
            # Get the path to the service account key file
            credentials_path = os.path.join(os.path.dirname(__file__), 'firestore-credentials.json')
            
            # Initialize credentials
            credentials = service_account.Credentials.from_service_account_file(
                credentials_path
            )
            
            # Initialize Firestore client with project and database
            self._db = firestore.Client(
                credentials=credentials,
                project=FIRESTORE_PROJECT_ID,
                database="spotify2youtube"
            )

    @property
    def db(self) -> firestore.Client:
        return self._db

    def get_collection(self, collection_name: str) -> firestore.CollectionReference:
        """Get a reference to a Firestore collection."""
        return self.db.collection(collection_name)

    def get_document(self, collection_name: str, document_id: str) -> firestore.DocumentReference:
        """Get a reference to a specific document in a collection."""
        return self.get_collection(collection_name).document(document_id)

    def create_document(self, collection_name: str, document_id: str, data: Dict[str, Any]) -> None:
        """Create a new document in a collection."""
        doc_ref = self.get_document(collection_name, document_id)
        doc_ref.set(data)

    def update_document(self, collection_name: str, document_id: str, data: Dict[str, Any]) -> None:
        """Update an existing document in a collection."""
        doc_ref = self.get_document(collection_name, document_id)
        doc_ref.update(data)

    def delete_document(self, collection_name: str, document_id: str) -> None:
        """Delete a document from a collection."""
        doc_ref = self.get_document(collection_name, document_id)
        doc_ref.delete()

    def get_document_data(self, collection_name: str, document_id: str) -> Optional[Dict[str, Any]]:
        """Get the data of a specific document."""
        doc_ref = self.get_document(collection_name, document_id)
        doc = doc_ref.get()
        return doc.to_dict() if doc.exists else None

    def query_collection(self, collection_name: str, **filters) -> list:
        """Query a collection with filters."""
        collection = self.get_collection(collection_name)
        query = collection
        
        for field, value in filters.items():
            query = query.where(field, "==", value)
        
        return [doc.to_dict() for doc in query.stream()] 