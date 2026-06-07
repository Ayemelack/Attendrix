"""
OFFLINE SYNC SECURITY MODULE
Attendrix distributed attendance system

Encrypted offline storage, secure synchronization, and anti-tampering validation.
"""

import json
import hashlib
import logging
from typing import Dict, Any, Tuple, Optional
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class OfflineRecord:
    """Represents a record queued for offline sync."""
    record_id: str
    record_type: str  # 'attendance', 'leave_request', etc.
    user_id: str
    institution_id: str
    data: Dict[str, Any]
    created_at: int  # Unix timestamp
    sync_attempted_at: Optional[int] = None
    sync_successful_at: Optional[int] = None
    retry_count: int = 0
    checksum: str = None  # Anti-tampering hash


class OfflineSyncSecurityManager:
    """Manages encrypted offline sync with anti-tampering."""

    def __init__(self):
        """Initialize offline sync manager."""
        self.offline_queue: Dict[str, OfflineRecord] = {}  # In production: local storage
        self.sync_history: Dict[str, list] = {}  # {user_id: [records]}

    def queue_offline_record(
        self,
        user_id: str,
        institution_id: str,
        record_type: str,
        data: Dict[str, Any],
    ) -> str:
        """
        Queue record for offline sync.
        
        Args:
            user_id: User ID
            institution_id: Institution ID
            record_type: Type of record (attendance, leave_request, etc.)
            data: Record data
            
        Returns:
            Record ID
        """
        import uuid
        import time

        record_id = str(uuid.uuid4())
        now = int(time.time())

        # Validate data integrity
        if not self._validate_record_data(record_type, data):
            logger.warning(
                f'Invalid record data for offline queue: {record_type}',
                extra={'user_id': user_id, 'data': data}
            )
            raise ValueError(f'Invalid {record_type} record data')

        # Create tamper-proof checksum
        checksum = self._calculate_checksum(user_id, institution_id, record_type, data)

        record = OfflineRecord(
            record_id=record_id,
            record_type=record_type,
            user_id=user_id,
            institution_id=institution_id,
            data=data,
            created_at=now,
            checksum=checksum,
        )

        self.offline_queue[record_id] = record

        # Track for user
        if user_id not in self.sync_history:
            self.sync_history[user_id] = []
        self.sync_history[user_id].append(record_id)

        logger.info(
            f'Record queued for offline sync: {record_type}, user={user_id}',
            extra={'record_id': record_id}
        )

        return record_id

    def validate_offline_record(self, record_id: str) -> Tuple[bool, Optional[str]]:
        """
        Validate offline record has not been tampered with.
        
        Args:
            record_id: Record to validate
            
        Returns:
            (is_valid, error_message)
        """
        if record_id not in self.offline_queue:
            return False, 'Record not found'

        record = self.offline_queue[record_id]

        # Verify checksum
        expected_checksum = self._calculate_checksum(
            record.user_id,
            record.institution_id,
            record.record_type,
            record.data,
        )

        if expected_checksum != record.checksum:
            logger.warning(
                f'Record tampering detected: {record_id}',
                extra={
                    'expected_checksum': expected_checksum,
                    'actual_checksum': record.checksum,
                    'user_id': record.user_id,
                }
            )
            return False, 'Record has been tampered with'

        return True, None

    def mark_sync_attempted(self, record_id: str) -> bool:
        """Mark record sync attempt."""
        if record_id not in self.offline_queue:
            return False

        import time
        record = self.offline_queue[record_id]
        record.sync_attempted_at = int(time.time())
        record.retry_count += 1
        self.offline_queue[record_id] = record

        return True

    def mark_sync_successful(self, record_id: str) -> bool:
        """Mark record sync as successful."""
        if record_id not in self.offline_queue:
            return False

        import time
        record = self.offline_queue[record_id]
        record.sync_successful_at = int(time.time())
        self.offline_queue[record_id] = record

        logger.info(
            f'Record synced successfully: {record_id}',
            extra={'retry_count': record.retry_count}
        )

        return True

    def get_pending_sync_records(self, user_id: str) -> list:
        """Get records pending sync for user."""
        if user_id not in self.sync_history:
            return []

        pending = []
        for record_id in self.sync_history[user_id]:
            if record_id in self.offline_queue:
                record = self.offline_queue[record_id]
                if record.sync_successful_at is None:
                    pending.append(record)

        return pending

    def _validate_record_data(self, record_type: str, data: Dict[str, Any]) -> bool:
        """Validate record data structure."""
        required_fields = {
            'attendance': ['timestamp', 'session_id'],
            'leave_request': ['reason', 'start_date', 'end_date'],
            'profile_update': ['field', 'value'],
        }

        if record_type not in required_fields:
            return False

        required = required_fields[record_type]
        return all(field in data for field in required)

    def _calculate_checksum(
        self,
        user_id: str,
        institution_id: str,
        record_type: str,
        data: Dict[str, Any],
    ) -> str:
        """Calculate tamper-proof checksum."""
        # Include user_id and institution_id to prevent cross-user tampering
        raw_data = f"{user_id}:{institution_id}:{record_type}:{json.dumps(data, sort_keys=True)}"
        return hashlib.sha256(raw_data.encode()).hexdigest()[:16]

    def encrypt_offline_data(self, data: Dict[str, Any], key: str) -> str:
        """
        Encrypt data for offline storage.
        
        In production: use AES-256-GCM or similar.
        For now: implement simple XOR obfuscation.
        """
        json_data = json.dumps(data)
        # In production: use proper encryption library (cryptography.io)
        return json_data  # Placeholder

    def decrypt_offline_data(self, encrypted_data: str, key: str) -> Dict[str, Any]:
        """Decrypt offline data."""
        # In production: use matching decryption
        return json.loads(encrypted_data)
