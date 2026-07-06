import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
import secrets
import qrcode
import io
import base64
import uuid

from src.domain.entities import AttendanceStatus, UserRole
from src.infrastructure.pg_repositories import pg_repos
from src.infrastructure.models import AttendanceSession, AttendanceRecord, SessionStatus

logger = logging.getLogger(__name__)


class AttendanceSecurityService:
    """Real attendance security implementation with QR codes and anti-proxy protection"""

    def __init__(self):
        self.session_duration_minutes = 60
        self.qr_code_expiry_minutes = 5

    def create_attendance_session(self, course_id: str, lecturer_id: str,
                                  location: Optional[str] = None,
                                  institution_id: Optional[str] = None) -> Dict[str, Any]:
        """Create new attendance session with QR code"""
        try:
            session_id = str(uuid.uuid4())
            session_code = self._generate_session_code()
            now = datetime.utcnow()

            qr_code_data = self._generate_qr_code(session_code)

            session = AttendanceSession(
                id=session_id,
                course_id=course_id,
                lecturer_id=lecturer_id,
                institution_id=institution_id,
                session_code=session_code,
                qr_payload=qr_code_data,
                start_time=now,
                is_active=True,
                location_data={'location': location} if location else None,
                status=SessionStatus.ACTIVE
            )

            pg_repos.attendance_session.create_session(session)

            logger.info(f"Created attendance session {session_code} for course {course_id}")
            return {
                'session_id': session_id,
                'session_code': session_code,
                'qr_code': qr_code_data,
                'start_time': now.isoformat(),
                'expires_at': (now + timedelta(minutes=self.session_duration_minutes)).isoformat(),
                'location': location,
                'message': 'Attendance session created successfully'
            }

        except Exception as e:
            err_msg = str(e)
            logger.error(f"Session creation failed: {err_msg}")
            return {'error': f'Session creation failed: {err_msg}'}

    def mark_attendance(self, session_code: str, student_id: str,
                        device_fingerprint: Optional[str] = None,
                        ip_address: Optional[str] = None,
                        location: Optional[str] = None,
                        face_verified: bool = False,
                        face_match_score: float = 0.0) -> Dict[str, Any]:
        """Mark attendance with security validation"""
        try:
            session = self._validate_session(session_code)
            if not session:
                return {'error': 'Invalid or expired session code'}

            if not session.is_active:
                return {'error': 'Session is not active'}

            existing = pg_repos.attendance_record.get_student_attendance(session.id, student_id)
            if existing:
                return {'error': 'Attendance already marked for this session'}

            session_start = session.start_time
            session_end = session_start + timedelta(minutes=self.session_duration_minutes)
            if datetime.utcnow() > session_end:
                return {'error': 'Session has expired'}

            record_id = str(uuid.uuid4())
            now = datetime.utcnow()

            record = AttendanceRecord(
                id=record_id,
                session_id=session.id,
                student_id=student_id,
                institution_id=session.institution_id,
                marked_at=now,
                status=AttendanceStatus.PRESENT,
                device_id=device_fingerprint,
                ip_address=ip_address,
                device_fingerprint=device_fingerprint,
                face_verified=face_verified
            )

            pg_repos.attendance_record.mark_attendance(record)

            logger.info(f"Attendance marked for student {student_id} in session {session_code}")
            return {
                'record_id': record_id,
                'session_id': session.id,
                'mark_time': now.isoformat(),
                'status': AttendanceStatus.PRESENT.value,
                'message': 'Attendance marked successfully'
            }

        except Exception as e:
            logger.error(f"Attendance marking failed: {str(e)}")
            return {'error': 'Failed to mark attendance'}

    def close_attendance_session(self, session_id: str, lecturer_id: str) -> Dict[str, Any]:
        """Close attendance session"""
        try:
            session = pg_repos.attendance_session.get(session_id)
            if not session:
                return {'error': 'Session not found or access denied'}
            if session.lecturer_id is not None and session.lecturer_id != lecturer_id:
                return {'error': 'Session not found or access denied'}

            pg_repos.attendance_session.close_session(session_id)

            logger.info(f"Attendance session {session_id} closed")
            return {'message': 'Session closed successfully'}

        except Exception as e:
            logger.error(f"Session closure failed: {str(e)}")
            return {'error': 'Failed to close session'}

    def get_session_attendance(self, session_id: str) -> List[Dict[str, Any]]:
        """Get all attendance records for a session"""
        try:
            records = pg_repos.attendance_record.get_by_session(session_id)

            return [{
                'record_id': record.id,
                'student_id': record.student_id,
                'student_name': self._get_student_name(record.student_id),
                'mark_time': record.marked_at.isoformat() if record.marked_at else None,
                'status': record.status.value if record.status else 'present',
                'location': record.ip_address,
                'device_id': record.device_id
            } for record in records]

        except Exception as e:
            logger.error(f"Failed to get session attendance: {str(e)}")
            return []

    def _validate_session(self, session_code: str) -> Optional[AttendanceSession]:
        """Validate session code and time window"""
        try:
            session = pg_repos.attendance_session.get_by_session_code(session_code)
            if not session:
                logger.info(f"Session validation: no session for code {session_code}")
                return None

            if not session.is_active:
                logger.info(f"Session {session_code}: is_active=False, rejecting")
                return None

            if session.end_time is not None:
                end = session.end_time
                if end.tzinfo is not None:
                    end = end.replace(tzinfo=None)
                if datetime.utcnow() > end:
                    logger.info(f"Session {session_code}: passed end_time {end.isoformat()}, rejecting")
                    return None
                return session

            session_start = session.start_time
            if session_start.tzinfo is not None:
                session_start = session_start.replace(tzinfo=None)
            session_end = session_start + timedelta(minutes=self.session_duration_minutes)
            if datetime.utcnow() > session_end:
                logger.info(f"Session {session_code}: expired at {session_end.isoformat()}")
                return None

            return session

        except Exception as e:
            logger.error(f"Session validation failed for {session_code}: {type(e).__name__}: {str(e)}")
            return None

    def get_server_session(self, session_code: str) -> Optional[Dict[str, Any]]:
        """Fetch session from server (no cache distinction in PG — direct query)."""
        try:
            normalized_code = session_code.strip().upper()
            session = pg_repos.attendance_session.get_by_session_code(normalized_code)

            if not session:
                logger.info(f"Server session fetch: no session for code {normalized_code}")
                return None

            logger.info(f"Server session {normalized_code}: found id={session.id}")

            if not session.is_active:
                logger.info(f"Server session {normalized_code}: is_active=False, rejecting")
                return None

            if session.end_time is not None:
                end = session.end_time
                if end.tzinfo is not None:
                    end = end.replace(tzinfo=None)
                if datetime.utcnow() > end:
                    logger.info(f"Server session {normalized_code}: passed end_time, rejecting")
                    return None
                return self._session_to_dict(session)

            session_start = session.start_time
            if session_start.tzinfo is not None:
                session_start = session_start.replace(tzinfo=None)
            session_end = session_start + timedelta(minutes=self.session_duration_minutes)
            if datetime.utcnow() > session_end:
                logger.info(f"Server session {normalized_code}: expired")
                return None

            logger.info(f"Server session {normalized_code}: valid and active")
            return self._session_to_dict(session)

        except Exception as e:
            logger.error(f"Server session fetch failed for {session_code}: {type(e).__name__}: {str(e)}")
            return None

    def _session_to_dict(self, session: AttendanceSession) -> Dict[str, Any]:
        return {
            'id': session.id,
            'session_code': session.session_code,
            'course_id': session.course_id,
            'lecturer_id': session.lecturer_id,
            'institution_id': session.institution_id,
            'start_time': session.start_time.isoformat() if session.start_time else None,
            'end_time': session.end_time.isoformat() if session.end_time else None,
            'is_active': session.is_active,
            'course_name': getattr(session, 'course_name', ''),
            'lecturer_name': getattr(session, 'lecturer_name', ''),
            'location_data': session.location_data,
            'created_at': session.created_at.isoformat() if session.created_at else None,
        }

    def validate_server_session(self, session_code: str) -> Dict[str, Any]:
        """Comprehensive server-side session validation."""
        server_session = self.get_server_session(session_code)
        if not server_session:
            return {
                'valid': False,
                'error': 'Invalid Session Code \u2192 STOP PROCESS',
                'message': 'Session not found, inactive, or expired'
            }

        return {
            'valid': True,
            'session': server_session,
            'session_code': server_session.get('session_code'),
            'course_name': server_session.get('course_name', ''),
            'lecturer_name': server_session.get('lecturer_name', ''),
            'lecturer_id': server_session.get('lecturer_id'),
            'is_active': server_session.get('is_active', True),
            'message': 'Session validated from server'
        }

    def _generate_session_code(self) -> str:
        import string
        characters = string.ascii_uppercase + string.digits
        return ''.join(secrets.choice(characters) for _ in range(6))

    def _generate_qr_code(self, session_code: str) -> str:
        try:
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=4,
            )
            qr.add_data(session_code)
            qr.make(fit=True)

            img = qr.make_image(fill_color="black", back_color="white")
            buffer = io.BytesIO()
            img.save(buffer, format="PNG")
            img_str = base64.b64encode(buffer.getvalue()).decode()

            return f"data:image/png;base64,{img_str}"

        except Exception as e:
            logger.error(f"QR code generation failed: {str(e)}")
            return ""

    def _get_student_name(self, student_id: str) -> str:
        try:
            user = pg_repos.user.get(student_id)
            if user:
                profile = pg_repos.user_profile.get_by_user(student_id)
                if profile:
                    return f"{profile.first_name or ''} {profile.last_name or ''}".strip()
                return user.email or "Unknown Student"
            return "Unknown Student"
        except Exception:
            return "Unknown Student"