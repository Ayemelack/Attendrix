"""
ATTENDANCE ANTI-PROXY PROTECTION MODULE
Attendrix distributed attendance system

Prevents proxy attendance (students recording attendance for others).
Implements dynamic sessions, expiring tokens, live lecturer validation, and timestamp verification.
"""

import uuid
import time
import hashlib
import logging
from typing import Dict, Any, Tuple, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class AttendanceSession:
    """Represents a single attendance session."""
    session_id: str
    lecturer_id: str
    class_id: str
    institution_id: str
    created_at: int  # Unix timestamp
    expires_at: int  # Unix timestamp
    is_active: bool = True
    qr_token: str = None  # Expiring QR code token
    location_proof_required: bool = False
    expected_location_lat: float = None
    expected_location_lon: float = None
    expected_location_radius_m: float = 50  # 50 meter radius
    max_participants: int = None
    current_participant_count: int = 0
    recorded_attendance: Dict[str, int] = None  # {user_id: timestamp}

    def __post_init__(self):
        if self.recorded_attendance is None:
            self.recorded_attendance = {}

    @property
    def is_expired(self) -> bool:
        return int(time.time()) > self.expires_at

    @property
    def time_remaining_seconds(self) -> int:
        return max(0, self.expires_at - int(time.time()))


class AttendanceSessionManager:
    """Manages secure attendance sessions to prevent proxy attendance."""

    def __init__(self, session_duration_seconds: int = 600):
        """
        Initialize attendance session manager.
        
        Args:
            session_duration_seconds: How long session stays open (default: 10 minutes)
        """
        self.session_duration = session_duration_seconds
        self.sessions: Dict[str, AttendanceSession] = {}  # In production: use Redis
        self.lecturer_sessions: Dict[str, list] = {}  # {lecturer_id: [session_ids]}

    def create_session(
        self,
        lecturer_id: str,
        class_id: str,
        institution_id: str,
        location_proof_required: bool = False,
        expected_location_lat: Optional[float] = None,
        expected_location_lon: Optional[float] = None,
        max_participants: Optional[int] = None,
    ) -> AttendanceSession:
        """
        Create new attendance session (lecturer initiates).
        
        Args:
            lecturer_id: Lecturer's user ID
            class_id: Class ID
            institution_id: Institution ID
            location_proof_required: Require GPS validation
            expected_location_lat: Expected class GPS latitude
            expected_location_lon: Expected class GPS longitude
            max_participants: Max students in class (optional)
            
        Returns:
            AttendanceSession
        """
        now = int(time.time())
        session_id = str(uuid.uuid4())
        qr_token = self._generate_qr_token(session_id)

        session = AttendanceSession(
            session_id=session_id,
            lecturer_id=lecturer_id,
            class_id=class_id,
            institution_id=institution_id,
            created_at=now,
            expires_at=now + self.session_duration,
            qr_token=qr_token,
            location_proof_required=location_proof_required,
            expected_location_lat=expected_location_lat,
            expected_location_lon=expected_location_lon,
            max_participants=max_participants,
        )

        self.sessions[session_id] = session

        # Track lecturer sessions
        if lecturer_id not in self.lecturer_sessions:
            self.lecturer_sessions[lecturer_id] = []
        self.lecturer_sessions[lecturer_id].append(session_id)

        logger.info(
            f'Attendance session created: lecturer={lecturer_id}, class={class_id}, expires_in={self.session_duration}s',
            extra={'session_id': session_id, 'qr_token': qr_token[:8]}
        )

        return session

    def validate_attendance_session(
        self,
        session_id: str,
        user_id: str,
        device_fingerprint_id: str,
        timestamp: Optional[int] = None,
    ) -> Tuple[bool, Optional[str], Optional[AttendanceSession]]:
        """
        Validate attendance session before recording.
        
        Args:
            session_id: Session to validate
            user_id: Student user ID
            device_fingerprint_id: Device fingerprint
            timestamp: Request timestamp (for anti-replay)
            
        Returns:
            (is_valid, error_message, session)
        """
        if session_id not in self.sessions:
            return False, 'Attendance session not found', None

        session = self.sessions[session_id]

        # Check if session is active
        if not session.is_active:
            return False, 'Attendance session has been closed by lecturer', session

        # Check expiration
        if session.is_expired:
            logger.warning(
                f'Expired attendance session: {session_id}',
                extra={'user_id': user_id, 'class_id': session.class_id}
            )
            return False, f'Attendance session expired. Time remaining was {session.time_remaining_seconds}s ago.', session

        # Check max participants
        if session.max_participants and session.current_participant_count >= session.max_participants:
            logger.warning(
                f'Attendance session full: {session_id}',
                extra={'user_id': user_id, 'max': session.max_participants}
            )
            return False, 'Attendance session is full.', session

        # Check if user already recorded (prevent duplicate)
        if user_id in session.recorded_attendance:
            recorded_time = session.recorded_attendance[user_id]
            logger.warning(
                f'Duplicate attendance attempt: {session_id}, user={user_id}',
                extra={'original_time': recorded_time, 'retry_time': int(time.time())}
            )
            return False, 'You have already recorded attendance for this session.', session

        # Validate timestamp freshness (prevent replay)
        if timestamp:
            now = int(time.time())
            time_diff = abs(now - timestamp)
            if time_diff > 30:  # Allow 30 second clock skew
                logger.warning(
                    f'Stale timestamp: {time_diff}s skew',
                    extra={'session_id': session_id, 'user_id': user_id}
                )
                return False, f'Clock skew too large ({time_diff}s). Synchronize device time.', session

        return True, None, session

    def record_attendance(
        self,
        session_id: str,
        user_id: str,
        device_fingerprint_id: str,
        location_data: Optional[Dict[str, float]] = None,
    ) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
        """
        Record student attendance in session.
        
        Args:
            session_id: Attendance session
            user_id: Student user ID
            device_fingerprint_id: Device fingerprint
            location_data: GPS location data (if required)
            
        Returns:
            (success, error_message, record_data)
        """
        # Validate session
        is_valid, error, session = self.validate_attendance_session(
            session_id,
            user_id,
            device_fingerprint_id,
        )

        if not is_valid:
            return False, error, None

        # Validate location if required
        if session.location_proof_required and location_data:
            is_location_valid = self._validate_attendance_location(
                session,
                location_data,
            )
            if not is_location_valid:
                logger.warning(
                    f'Location validation failed for attendance: session={session_id}, user={user_id}',
                    extra={'location': location_data}
                )
                return False, 'Your location is outside the attendance zone.', None

        # Record attendance
        now = int(time.time())
        session.recorded_attendance[user_id] = now
        session.current_participant_count += 1

        record_data = {
            'session_id': session_id,
            'user_id': user_id,
            'class_id': session.class_id,
            'lecturer_id': session.lecturer_id,
            'recorded_at': now,
            'device_fingerprint_id': device_fingerprint_id,
        }

        logger.info(
            f'Attendance recorded: user={user_id}, class={session.class_id}, session={session_id}',
            extra=record_data
        )

        return True, None, record_data

    def close_session(self, session_id: str, lecturer_id: str) -> Tuple[bool, Optional[str]]:
        """
        Close attendance session (lecturer action).
        
        Args:
            session_id: Session to close
            lecturer_id: Lecturer closing session (must match)
            
        Returns:
            (success, error_message)
        """
        if session_id not in self.sessions:
            return False, 'Session not found'

        session = self.sessions[session_id]

        # Verify lecturer
        if session.lecturer_id != lecturer_id:
            logger.warning(
                f'Unauthorized session close attempt: user={lecturer_id}, session_lecturer={session.lecturer_id}',
                extra={'session_id': session_id}
            )
            return False, 'You are not authorized to close this session'

        session.is_active = False
        self.sessions[session_id] = session

        logger.info(
            f'Attendance session closed: lecturer={lecturer_id}, session={session_id}, participants={session.current_participant_count}',
            extra={'session_id': session_id}
        )

        return True, None

    def get_session_summary(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session summary for lecturer."""
        if session_id not in self.sessions:
            return None

        session = self.sessions[session_id]
        return {
            'session_id': session_id,
            'class_id': session.class_id,
            'created_at': session.created_at,
            'expires_at': session.expires_at,
            'is_active': session.is_active,
            'is_expired': session.is_expired,
            'time_remaining_seconds': session.time_remaining_seconds,
            'participants_recorded': session.current_participant_count,
            'max_participants': session.max_participants,
            'recorded_students': list(session.recorded_attendance.keys()),
        }

    def _validate_attendance_location(
        self,
        session: AttendanceSession,
        location_data: Dict[str, float],
    ) -> bool:
        """Validate student location is in class zone."""
        if not session.location_proof_required:
            return True

        if not (session.expected_location_lat and session.expected_location_lon):
            return False

        student_lat = location_data.get('latitude')
        student_lon = location_data.get('longitude')

        if not (student_lat and student_lon):
            return False

        # Calculate distance (simplified Haversine)
        import math
        R = 6371000  # Earth radius in meters

        lat1_rad = math.radians(session.expected_location_lat)
        lat2_rad = math.radians(student_lat)
        delta_lat = math.radians(student_lat - session.expected_location_lat)
        delta_lon = math.radians(student_lon - session.expected_location_lon)

        a = (
            math.sin(delta_lat / 2) ** 2 +
            math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2
        )
        c = 2 * math.asin(math.sqrt(a))
        distance = R * c

        return distance <= session.expected_location_radius_m

    def _generate_qr_token(self, session_id: str) -> str:
        """Generate secure QR token."""
        raw = f"{session_id}{uuid.uuid4()}{int(time.time())}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def cleanup_expired_sessions(self) -> int:
        """Remove expired sessions."""
        count = 0
        for session_id in list(self.sessions.keys()):
            if self.sessions[session_id].is_expired:
                session = self.sessions.pop(session_id)
                # Clean from lecturer tracking
                if session.lecturer_id in self.lecturer_sessions:
                    self.lecturer_sessions[session.lecturer_id] = [
                        s for s in self.lecturer_sessions[session.lecturer_id]
                        if s != session_id
                    ]
                count += 1

        if count > 0:
            logger.info(f'Cleaned up {count} expired attendance sessions')

        return count
