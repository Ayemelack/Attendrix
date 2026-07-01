import json
import os
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timedelta
import firebase_admin
from firebase_admin import credentials, auth, firestore
from flask import current_app
import logging

logger = logging.getLogger(__name__)

# Collections that require institution-scoped access for multi-tenant isolation
REQUIRES_INSTITUTION_SCOPING = {
    'users', 'user_profiles', 'attendance_records', 'attendance_sessions',
    'courses', 'course_enrollments', 'departments', 'schedules',
    'class_sessions', 'notifications', 'vouchers', 'activity_logs',
    'security_logs', 'audit_logs', 'network_nodes', 'broker_status',
    'p2p_peers', 'p2p_status', 'compliance_exam', 'compliance_audit',
    'compliance_reports', 'ups_status', 'isp_status', 'generator_status',
    'mobile_money_providers', 'payment_transactions', 'offline_sync_queue',
    'offline_queue', 'biometric_enrollments', 'device_fingerprints',
    'face_descriptors', 'sms_queue', 'mail_queue', 'leave_requests',
    'activity_log', 'security_alerts', 'payments', 'sessions',
    'attendance', 'enrollments', 'feedback', 'demo_bookings',
    'network_presence', 'network_presence_config',
}

# Collections exempt from institution scoping (global/system-level)
EXEMPT_FROM_SCOPING = {
    'institutions', 'system_configurations', 'persistent_sessions',
}

# Collections that must be owned by a specific user (per-user documents)
PER_USER_COLLECTIONS = {
    'users', 'user_profiles', 'notifications', 'device_fingerprints',
    'biometric_enrollments', 'face_descriptors', 'persistent_sessions'
}

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

        # Read USE_MOCK_FIREBASE from Flask app config first, then env var
        try:
            from flask import current_app
            use_mock_raw = current_app.config.get('USE_MOCK_FIREBASE', os.environ.get('USE_MOCK_FIREBASE', 'true'))
        except (RuntimeError, ImportError):
            use_mock_raw = os.environ.get('USE_MOCK_FIREBASE', 'true')

        mock_env = str(use_mock_raw).lower()

        # Production guard: refuse mock mode entirely when ENVIRONMENT=production
        env = os.environ.get('ENVIRONMENT', os.environ.get('FLASK_ENV', 'production'))
        if env == 'production' and mock_env == 'true':
            logger.error(
                "USE_MOCK_FIREBASE=true in production environment. "
                "Set USE_MOCK_FIREBASE=false and configure real Firebase credentials."
            )
            raise RuntimeError(
                "Refusing to run with mock Firebase in production. "
                "Set USE_MOCK_FIREBASE=false and configure Firestore credentials."
            )

        if mock_env == 'true':
            logger.info("Using mock Firebase service (USE_MOCK_FIREBASE=true)")
            self._mock_mode = True
            self._initialized = True
            return

        try:
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
            if env == 'production':
                raise RuntimeError("Firebase initialization failed in production") from e
            if os.environ.get('USE_MOCK_FIREBASE', 'true').lower() == 'false':
                logger.error("USE_MOCK_FIREBASE=false but Firebase credentials could not be loaded.")
                logger.error("Place your Firebase service account JSON at: firebase-dev.json")
                logger.error("See: https://console.firebase.google.com/ → Project Settings → Service Accounts")
                raise
            logger.warning("Falling back to mock Firebase service")
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

    # ── AUTHORIZATION ENFORCEMENT ──

    @staticmethod
    def _get_current_user() -> Optional[Dict[str, Any]]:
        """Get current authenticated user from request context if available.
        Returns None outside of request context (background tasks, tests, bootstrap)."""
        try:
            from flask import request as _flask_request
            if hasattr(_flask_request, 'current_user') and _flask_request.current_user:
                return _flask_request.current_user
        except (RuntimeError, ImportError, Exception):
            logger.debug("No Flask request context — skipping current_user lookup")
            return None

    @staticmethod
    def _enforce_query_filters(collection: str, filters: Optional[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
        """Enforce multi-tenant isolation by validating query filters.
        Logs a security warning when a non-scoped query is detected so developers can fix it.
        Does NOT auto-inject filters to avoid breaking records that lack institution_id."""
        if collection in EXEMPT_FROM_SCOPING:
            return filters or []

        if collection not in REQUIRES_INSTITUTION_SCOPING:
            return filters or []

        user = FirebaseService._get_current_user()
        if not user:
            return filters or []

        role = user.get('role', '')
        if role == 'super_admin':
            return filters or []

        institution_id = user.get('institution_id')
        if not institution_id:
            return filters or []

        safe_filters = list(filters) if filters else []

        has_institution_filter = any(
            f.get('field') == 'institution_id'
            for f in safe_filters
        )

        # If the query is missing an institution filter for a collection that
        # requires scoping, auto-inject the user's institution_id to prevent
        # accidental cross-tenant reads. Log the augmentation for auditing.
        if not has_institution_filter:
            logger.warning(
                f"SECURITY: Non-scoped query on {collection} by "
                f"user={user.get('user_id', 'unknown')} role={role} "
                f"inst={institution_id}. Injecting institution_id filter to enforce scoping."
            )
            safe_filters.append({'field': 'institution_id', 'value': institution_id})

        return safe_filters

    @staticmethod
    def _enforce_document_read_access(document: Optional[Dict[str, Any]], collection: str) -> Optional[Dict[str, Any]]:
        """After fetching a document, verify the user has access.
        Returns None if access is denied."""
        if not document:
            return None

        if collection in EXEMPT_FROM_SCOPING:
            return document

        user = FirebaseService._get_current_user()
        if not user:
            return document

        role = user.get('role', '')
        if role == 'super_admin':
            return document

        # Check institution_id on document
        doc_inst_id = document.get('institution_id')
        user_inst_id = user.get('institution_id')

        if doc_inst_id and user_inst_id and str(doc_inst_id) != str(user_inst_id):
            logger.warning(
                f"Cross-institution read blocked: doc={document.get('id', 'unknown')} "
                f"in {collection} inst={doc_inst_id} != user inst={user_inst_id} "
                f"(user={user.get('user_id', 'unknown')})"
            )
            return None

        # For student role, enforce strict user-level isolation on personal collections
        if role == 'student':
            doc_owner_id = document.get('user_id') or document.get('uid') or document.get('student_id')
            user_id = user.get('user_id') or user.get('uid')
            if doc_owner_id and user_id and str(doc_owner_id) != str(user_id):
                sensitive_collections = {'notifications', 'device_fingerprints', 'biometric_enrollments'}
                if collection in sensitive_collections:
                    logger.warning(
                        f"Student cross-user read blocked: doc owner={doc_owner_id} "
                        f"!= user={user_id} in {collection}"
                    )
                    return None

        return document

    @staticmethod
    def _enforce_write_access(collection: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Enforce authorization on write operations.
        Auto-injects institution_id and created_by/updated_by if missing."""
        if collection in EXEMPT_FROM_SCOPING:
            return data

        user = FirebaseService._get_current_user()
        # If no authenticated user context is available (background job or misused admin SDK),
        # require explicit `institution_id` for institution-scoped collections to avoid blind writes.
        if not user:
            if collection in REQUIRES_INSTITUTION_SCOPING and 'institution_id' not in data:
                if collection not in ('security_logs', 'audit_logs'):
                    logger.error(f"SECURITY: Attempted write to {collection} without user context or institution_id")
                    raise PermissionError("Writes to institution-scoped collections require institution_id when no authenticated user context is present")
            # If write is to a per-user collection, require explicit owner field
            if collection in PER_USER_COLLECTIONS:
                if not any(k in data for k in ('user_id', 'uid', 'student_id')):
                    logger.error(f"SECURITY: Per-user write to {collection} missing owner field and no user context")
                    raise PermissionError("Per-user documents must include an owner identifier when no authenticated user is present")
            return data

        role = user.get('role', '')
        if role == 'super_admin':
            return data

        user_inst_id = user.get('institution_id')
        user_id = user.get('user_id') or user.get('uid')

        # Verify existing institution_id matches user's institution
        if 'institution_id' in data and user_inst_id:
            if str(data['institution_id']) != str(user_inst_id):
                logger.warning(
                    f"Cross-institution write blocked: data inst={data['institution_id']} "
                    f"!= user inst={user_inst_id} in {collection} "
                    f"(user={user_id or 'unknown'})"
                )
                raise PermissionError("Cross-institution write denied")

        # Auto-inject institution_id if missing and user has one
        if 'institution_id' not in data and user_inst_id and collection in REQUIRES_INSTITUTION_SCOPING:
            data['institution_id'] = user_inst_id

        # Add ownership tracking metadata
        if user_id:
            if 'updated_by' not in data:
                data['updated_by'] = user_id
            if 'created_by' not in data:
                data['created_by'] = user_id
            if 'created_by_role' not in data and role:
                data['created_by_role'] = role

        # For per-user collections, ensure an owner identifier exists and matches the authenticated user
        if collection in PER_USER_COLLECTIONS:
            owner_keys = ('user_id', 'uid', 'student_id')
            has_owner = any(k in data for k in owner_keys)
            if not has_owner and user_id:
                # Prefer `user_id` as canonical owner field
                data['user_id'] = user_id
            elif has_owner and user_id:
                # Verify owner matches authenticated user for strict per-user collections
                owner_val = next((data.get(k) for k in owner_keys if k in data), None)
                if owner_val and str(owner_val) != str(user_id) and role != 'super_admin':
                    logger.error(f"SECURITY: Attempted per-user write to {collection} for owner={owner_val} by user={user_id}")
                    raise PermissionError("Cannot create or modify per-user documents for another user")

        return data

    # ── GENERIC MOCK PERSISTENCE ──

    def create_document(self, collection: str, data: Dict[str, Any],
                      document_id: str = None) -> str:
        if not self._initialized:
            self.initialize()

        # Enforce write access: validate + auto-inject ownership fields
        data = self._enforce_write_access(collection, data.copy())

        if self.is_mock():
            global _mock_database
            fresh = load_mock_database()
            if fresh:
                _mock_database = fresh
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
            fresh = load_mock_database()
            if fresh:
                _mock_database = fresh
            _ensure_collection(collection)
            for doc in _mock_database.get(collection, []):
                if doc.get('id') == document_id:
                    # Enforce multi-tenant isolation on document read
                    return self._enforce_document_read_access(doc, collection)
            return None

        try:
            doc_ref = self.firestore_client.collection(collection).document(document_id)
            doc = doc_ref.get()
            result = doc.to_dict() if doc.exists else None
            # Enforce multi-tenant isolation on document read
            return self._enforce_document_read_access(result, collection)
        except Exception as e:
            logger.error(f"Failed to get document from {collection}: {str(e)}")
            return None

    def update_document(self, collection: str, document_id: str,
                       data: Dict[str, Any]) -> bool:
        if not self._initialized:
            self.initialize()

        # Retrieve existing document to preserve/verify institution and owner context
        existing_doc = self.get_document(collection, document_id)
        if existing_doc:
            if 'institution_id' in existing_doc:
                data.setdefault('institution_id', existing_doc['institution_id'])
            if collection in PER_USER_COLLECTIONS:
                owner_id = existing_doc.get('user_id') or existing_doc.get('uid') or existing_doc.get('student_id') or existing_doc.get('id')
                if owner_id:
                    data.setdefault('user_id', owner_id)
                for k in ('user_id', 'uid', 'student_id'):
                    if k in existing_doc:
                        data.setdefault(k, existing_doc[k])

        # Enforce write access on updates
        data = self._enforce_write_access(collection, data.copy())

        if self.is_mock():
            global _mock_database
            fresh = load_mock_database()
            if fresh:
                _mock_database = fresh
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

        # Enforce access: verify user can access before deletion
        doc = self.get_document(collection, document_id)
        if doc is None:
            return False

        if self.is_mock():
            global _mock_database
            fresh = load_mock_database()
            if fresh:
                _mock_database = fresh
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

    def get_document_from_server(self, collection: str, document_id: str) -> Optional[Dict[str, Any]]:
        """Force server fetch (simulates Firestore getDocFromServer).
        In mock mode, bypasses in-memory cache by re-reading from disk."""
        if not self._initialized:
            self.initialize()
        if self.is_mock():
            global _mock_database
            fresh = load_mock_database()
            if fresh:
                _mock_database = fresh
            docs = _mock_database.get(collection, [])
            for doc in docs:
                if doc.get('id') == document_id:
                    return self._enforce_document_read_access(doc, collection)
            return None
        try:
            doc_ref = self.firestore_client.collection(collection).document(document_id)
            doc = doc_ref.get()
            result = doc.to_dict() if doc.exists else None
            return self._enforce_document_read_access(result, collection)
        except Exception as e:
            logger.error(f"Failed to get document from server {collection}: {str(e)}")
            return None

    def query_documents_from_server(self, collection: str, filters: List[Dict[str, Any]] = None,
                                    limit: int = None) -> List[Dict[str, Any]]:
        """Force server-side query (simulates Firestore getDocFromServer + query).
        Always re-reads from disk to bypass in-memory cache, then applies filters."""
        if not self._initialized:
            self.initialize()

        # Enforce multi-tenant isolation
        enforced_filters = self._enforce_query_filters(collection, filters)

        if self.is_mock():
            global _mock_database
            fresh = load_mock_database()
            if fresh:
                _mock_database = fresh
            _ensure_collection(collection)
            result = list(_mock_database.get(collection, []))
            if enforced_filters:
                for f in enforced_filters:
                    field = f.get('field')
                    value = f.get('value')
                    if field is not None:
                        result = [d for d in result if d.get(field) == value]
            if limit:
                result = result[:limit]
            return result
        try:
            from firebase_admin import firestore as _fs
            q = self.firestore_client.collection(collection)
            if enforced_filters:
                for f in enforced_filters:
                    q = q.where(f.get('field'), '==', f.get('value'))
            if limit:
                q = q.limit(limit)
            return [doc.to_dict() for doc in q.stream()]
        except Exception as e:
            logger.error(f"Failed to query {collection} from server: {str(e)}")
            return []

    def query_documents(self, collection: str, filters: List[Dict[str, Any]] = None,
                       limit: int = None, order_by: str = None) -> List[Dict[str, Any]]:
        if not self._initialized:
            self.initialize()

        # Enforce multi-tenant isolation: auto-inject institution_id filter
        enforced_filters = self._enforce_query_filters(collection, filters)
        if enforced_filters != (filters or []) and filters is not None:
            if enforced_filters != filters:
                logger.info(
                    f"Query filters augmented for {collection}: "
                    f"original={filters} enforced={enforced_filters}"
                )

        if self.is_mock():
            global _mock_database
            fresh = load_mock_database()
            if fresh:
                _mock_database = fresh
            _ensure_collection(collection)
            result = list(_mock_database.get(collection, []))

            if enforced_filters:
                for f in enforced_filters:
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
            if enforced_filters:
                for f in enforced_filters:
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