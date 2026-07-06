from typing import List, Optional, Dict, Any
from datetime import datetime
from sqlalchemy.orm import joinedload
from sqlalchemy import desc, or_

from src.infrastructure.pg_repositories.base import SqlAlchemyRepository
from src.infrastructure.models import AttendanceSession, AttendanceRecord, AttendanceVerificationLog, SessionStatus

class PostgresAttendanceSessionRepository(SqlAlchemyRepository[AttendanceSession]):
    def __init__(self, session=None):
        super().__init__(AttendanceSession, session)

    def create_session(self, session: AttendanceSession) -> AttendanceSession:
        return self.create(session)

    def get_by_session_code(self, session_code: str) -> Optional[AttendanceSession]:
        return self.session.query(AttendanceSession).filter_by(
            session_code=session_code
        ).first()

    def get_active_session_by_code(self, session_code: str) -> Optional[AttendanceSession]:
        return self.session.query(AttendanceSession).filter_by(
            session_code=session_code,
            is_active=True
        ).first()

    def get_active_sessions(self) -> List[AttendanceSession]:
        return self.session.query(AttendanceSession).filter_by(is_active=True).all()

    def get_sessions_by_course(self, course_id: str) -> List[AttendanceSession]:
        return self.session.query(AttendanceSession).filter_by(course_id=course_id).order_by(desc(AttendanceSession.created_at)).all()

    def close_session(self, session_id: str) -> bool:
        session = self.get(session_id)
        if session:
            session.is_active = False
            session.status = SessionStatus.CLOSED
            session.end_time = datetime.utcnow()
            self.update(session)
            return True
        return False


class PostgresAttendanceRecordRepository(SqlAlchemyRepository[AttendanceRecord]):
    def __init__(self, session=None):
        super().__init__(AttendanceRecord, session)

    def mark_attendance(self, record: AttendanceRecord) -> AttendanceRecord:
        return self.create(record)

    def get_student_attendance(self, session_id: str, student_id: str) -> Optional[AttendanceRecord]:
        return self.session.query(AttendanceRecord).filter_by(
            session_id=session_id,
            student_id=student_id
        ).first()

    def get_by_session(self, session_id: str) -> List[AttendanceRecord]:
        return self.session.query(AttendanceRecord).filter_by(session_id=session_id).all()

    def get_by_student(self, student_id: str) -> List[AttendanceRecord]:
        return self.session.query(AttendanceRecord).filter_by(student_id=student_id).all()

    def bulk_mark_attendance(self, records: List[AttendanceRecord]) -> List[AttendanceRecord]:
        self.session.add_all(records)
        self.session.commit()
        for record in records:
            self.session.refresh(record)
        return records

    def get_recent_attendance(self, student_id: str, limit: int = 10) -> List[AttendanceRecord]:
        return self.session.query(AttendanceRecord).filter_by(student_id=student_id).order_by(desc(AttendanceRecord.marked_at)).limit(limit).all()


class PostgresAttendanceVerificationLogRepository(SqlAlchemyRepository[AttendanceVerificationLog]):
    def __init__(self, session=None):
        super().__init__(AttendanceVerificationLog, session)
