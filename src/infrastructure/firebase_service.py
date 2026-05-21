import json
import os
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import firebase_admin
from firebase_admin import credentials, auth, firestore
from flask import current_app
import logging

logger = logging.getLogger(__name__)

# Mock database for development with file persistence
_MOCK_DB_FILE = 'mock_database.json'

def load_mock_database():
    try:
        if os.path.exists(_MOCK_DB_FILE):
            with open(_MOCK_DB_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data
        else:
            return {}
    except Exception as e:
        logger.error(f"Failed to load mock database: {str(e)}")
        return {}

def save_mock_database(data):
    try:
        with open(_MOCK_DB_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, default=str, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Failed to save mock database: {str(e)}")

_mock_database = load_mock_database()

def _ensure_collection(collection: str):
    global _mock_database
    if not _mock_database:
        _mock_database = load_mock_database()
    if collection not in _mock_database:
        _mock_database[collection] = []


class FirebaseService:
    """Firebase service for authentication and database operations"""

    def __init__(self):
        self.app = None
        self.auth_client = None
        self.firestore_client = None
        self._initialized = False

    def initialize(self, credentials_path: str = None, project_id: str = None):
        if self._initialized:
            return
        try:
            # Force mock mode for local development regardless of environment
            if True or os.environ.get('USE_MOCK_FIREBASE', 'true').lower() == 'true':
                logger.info("Using mock Firebase service for development")
                self._mock_mode = True
                self._initialized = True
                return

            if credentials_path and os.path.exists(credentials_path):
                cred = credentials.Certificate(credentials_path)
            else:
                firebase_config = os.environ.get('FIREBASE_CONFIG')
                if firebase_config:
                    cred_dict = json.loads(firebase_config)
                    cred = credentials.Certificate(cred_dict)
                else:
                    raise ValueError("Firebase credentials not found")

            if project_id:
                self.app = firebase_admin.initialize_app(cred, {
                    'projectId': project_id
                })
            else:
                self.app = firebase_admin.initialize_app(cred)

            self.auth_client = auth
            self.firestore_client = firestore.client()
            self._mock_mode = False
            self._initialized = True
            logger.info("Firebase Admin SDK initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize Firebase: {str(e)}")
            if os.environ.get('USE_MOCK_FIREBASE', 'true').lower() == 'false':
                logger.error("USE_MOCK_FIREBASE=false but Firebase credentials could not be loaded.")
                logger.error("Place your Firebase service account JSON at: firebase-dev.json")
                logger.error("See: https://console.firebase.google.com/ → Project Settings → Service Accounts")
                raise
            logger.info("Falling back to mock Firebase service")
            self._mock_mode = True
            self._initialized = True

    def create_user(self, email: str, password: str, display_name: str = None,
                   phone_number: str = None, custom_claims: Dict[str, Any] = None) -> str:
        if not self._initialized:
            self.initialize()
        if self.is_mock():
            import uuid
            return str(uuid.uuid4())
        try:
            user_properties = {'email': email, 'password': password, 'email_verified': False}
            if display_name:
                user_properties['display_name'] = display_name
            if phone_number:
                user_properties['phone_number'] = phone_number
            user = self.auth_client.create_user(**user_properties)
            if custom_claims:
                self.auth_client.set_custom_user_claims(user.uid, custom_claims)
            return user.uid
        except Exception as e:
            logger.error(f"Failed to create Firebase user: {str(e)}")
            raise

    def set_custom_claims(self, uid: str, claims: Dict[str, Any]) -> bool:
        if not self._initialized:
            self.initialize()
        if self.is_mock():
            return True
        try:
            self.auth_client.set_custom_user_claims(uid, claims)
            return True
        except Exception as e:
            logger.error(f"Failed to set custom claims: {str(e)}")
            return False

    def is_mock(self) -> bool:
        return hasattr(self, '_mock_mode') and self._mock_mode

    # ── GENERIC MOCK PERSISTENCE ──

    def create_document(self, collection: str, data: Dict[str, Any],
                      document_id: str = None) -> str:
        if not self._initialized:
            self.initialize()
        if self.is_mock():
            global _mock_database
            _ensure_collection(collection)
            doc_data = data.copy()
            if document_id is None:
                import uuid
                document_id = str(uuid.uuid4())
            doc_data['id'] = document_id
            doc_data.setdefault('created_at', datetime.utcnow().isoformat())
            doc_data.setdefault('updated_at', datetime.utcnow().isoformat())
            _mock_database[collection].append(doc_data)
            save_mock_database(_mock_database)
            logger.info(f"MOCK: Created doc in {collection}: {document_id}")
            return document_id

        try:
            doc_ref = self.firestore_client.collection(collection)
            if document_id:
                doc_ref = doc_ref.document(document_id)
                doc_ref.set(data)
                return document_id
            else:
                doc_ref = doc_ref.add(data)
                return doc_ref[1].id
        except Exception as e:
            logger.error(f"Failed to create document in {collection}: {str(e)}")
            raise

    def get_document(self, collection: str, document_id: str) -> Optional[Dict[str, Any]]:
        if not self._initialized:
            self.initialize()
        if self.is_mock():
            global _mock_database
            _ensure_collection(collection)
            for doc in _mock_database.get(collection, []):
                if doc.get('id') == document_id:
                    return doc
            return None

        try:
            doc_ref = self.firestore_client.collection(collection).document(document_id)
            doc = doc_ref.get()
            return doc.to_dict() if doc.exists else None
        except Exception as e:
            logger.error(f"Failed to get document from {collection}: {str(e)}")
            return None

    def update_document(self, collection: str, document_id: str,
                       data: Dict[str, Any]) -> bool:
        if not self._initialized:
            self.initialize()
        if self.is_mock():
            global _mock_database
            _ensure_collection(collection)
            for i, doc in enumerate(_mock_database.get(collection, [])):
                if doc.get('id') == document_id:
                    _mock_database[collection][i].update(data)
                    _mock_database[collection][i]['updated_at'] = datetime.utcnow().isoformat()
                    save_mock_database(_mock_database)
                    return True
            return False

        try:
            self.firestore_client.collection(collection).document(document_id).update(data)
            return True
        except Exception as e:
            logger.error(f"Failed to update document in {collection}: {str(e)}")
            return False

    def delete_document(self, collection: str, document_id: str) -> bool:
        if not self._initialized:
            self.initialize()
        if self.is_mock():
            global _mock_database
            _ensure_collection(collection)
            before = len(_mock_database.get(collection, []))
            _mock_database[collection] = [
                d for d in _mock_database.get(collection, [])
                if d.get('id') != document_id
            ]
            if len(_mock_database[collection]) < before:
                save_mock_database(_mock_database)
                return True
            return False

        try:
            self.firestore_client.collection(collection).document(document_id).delete()
            return True
        except Exception as e:
            logger.error(f"Failed to delete document from {collection}: {str(e)}")
            return False

    def query_documents(self, collection: str, filters: List[Dict[str, Any]] = None,
                       limit: int = None, order_by: str = None) -> List[Dict[str, Any]]:
        if not self._initialized:
            self.initialize()
        if self.is_mock():
            global _mock_database
            _ensure_collection(collection)
            result = list(_mock_database.get(collection, []))

            if filters:
                for f in filters:
                    field = f.get('field')
                    value = f.get('value')
                    if field is not None:
                        result = [d for d in result if d.get(field) == value]

            if order_by:
                reverse = False
                if order_by.startswith('-'):
                    order_by = order_by[1:]
                    reverse = True
                result.sort(key=lambda d: d.get(order_by, ''), reverse=reverse)

            if limit:
                result = result[:limit]

            return result

        try:
            q = self.firestore_client.collection(collection)
            if filters:
                for f in filters:
                    q = q.where(f.get('field'), '==', f.get('value'))
            if order_by:
                q = q.order_by(order_by)
            if limit:
                q = q.limit(limit)
            return [doc.to_dict() for doc in q.stream()]
        except Exception as e:
            logger.error(f"Failed to query {collection}: {str(e)}")
            return []


# Global Firebase service instance
firebase_service = FirebaseService()