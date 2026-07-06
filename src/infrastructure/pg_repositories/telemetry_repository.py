from typing import List, Optional
from datetime import datetime

from src.infrastructure.pg_repositories.base import SqlAlchemyRepository
from src.infrastructure.models import OfflineQueueItem, NetworkPresence, ActivityLog, SecurityLog, DeviceFingerprint

class PostgresOfflineQueueRepository(SqlAlchemyRepository[OfflineQueueItem]):
    def __init__(self, session):
        super().__init__(OfflineQueueItem, session)

    def get_pending(self, institution_id: Optional[str] = None, limit: int = 100) -> List[OfflineQueueItem]:
        query = self.session.query(OfflineQueueItem).filter(OfflineQueueItem.status == 'pending')
        if institution_id:
            query = query.filter(OfflineQueueItem.institution_id == institution_id)
        return query.order_by(OfflineQueueItem.created_at).limit(limit).all()

    def get_failed(self, institution_id: Optional[str] = None, limit: int = 50) -> List[OfflineQueueItem]:
        query = self.session.query(OfflineQueueItem).filter(OfflineQueueItem.status == 'failed')
        if institution_id:
            query = query.filter(OfflineQueueItem.institution_id == institution_id)
        return query.order_by(OfflineQueueItem.updated_at.desc()).limit(limit).all()

class PostgresNetworkPresenceRepository(SqlAlchemyRepository[NetworkPresence]):
    def __init__(self, session):
        super().__init__(NetworkPresence, session)

    def get_presence_list(self, institution_id: str) -> List[NetworkPresence]:
        return self.session.query(NetworkPresence).filter(NetworkPresence.institution_id == institution_id).all()

class PostgresActivityLogRepository(SqlAlchemyRepository[ActivityLog]):
    def __init__(self, session):
        super().__init__(ActivityLog, session)

    def get_activity_feed(self, institution_id: str, limit: int = 15) -> List[ActivityLog]:
        return self.session.query(ActivityLog)\
            .filter(ActivityLog.institution_id == institution_id)\
            .order_by(ActivityLog.created_at.desc())\
            .limit(limit).all()

class PostgresSecurityLogRepository(SqlAlchemyRepository[SecurityLog]):
    def __init__(self, session):
        super().__init__(SecurityLog, session)

    def get_security_alerts(self, institution_id: str, limit: int = 8) -> List[SecurityLog]:
        return self.session.query(SecurityLog)\
            .filter(SecurityLog.institution_id == institution_id)\
            .order_by(SecurityLog.created_at.desc())\
            .limit(limit).all()


class PostgresDeviceFingerprintRepository(SqlAlchemyRepository[DeviceFingerprint]):
    def __init__(self, session):
        super().__init__(DeviceFingerprint, session)

    def get_by_user(self, user_id: str) -> List[DeviceFingerprint]:
        return self.session.query(DeviceFingerprint).filter_by(user_id=user_id).order_by(DeviceFingerprint.last_seen.desc()).all()

    def get_by_hash(self, fingerprint_hash: str) -> List[DeviceFingerprint]:
        return self.session.query(DeviceFingerprint).filter_by(fingerprint_hash=fingerprint_hash).all()
