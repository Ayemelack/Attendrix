from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
import hashlib
import secrets
import logging
import uuid
from geopy.distance import geodesic

from src.domain.entities import (
    AttendanceSession, AttendanceRecord, AttendanceStatus
)
from src.infrastructure.pg_repositories import pg_repos
from src.infrastructure.models import (
    AttendanceSession as PGAttendanceSession,
    AttendanceRecord as PGAttendanceRecord,
    SecurityLog as PG_SecurityLog,
    SessionStatus,
    AttendanceStatus as PgAttendanceStatus
)

logger = logging.getLogger(__name__)


class SuspiciousActivityType:
    """Types of suspicious attendance activities"""
    MULTIPLE_DEVICES = "multiple_devices"
    IMPOSSIBLE_LOCATION = "impossible_location"
    RAPID_SUCCESSION = "rapid_succession"
    UNUSUAL_IP_PATTERN = "unusual_ip_pattern"
    DEVICE_MISMATCH = "device_mismatch"
    TIME_ANOMALY = "time_anomaly"


class AttendanceEngine:
    """Advanced attendance engine with anti-proxy mechanisms"""

    def __init__(self):
        self.attendance_session_repo = pg_repos.attendance_session
        self.attendance_record_repo = pg_repos.attendance_record
        self.user_repo = pg_repos.user
        self.security_log_repo = pg_repos.security_logs
        self.device_fingerprint_repo = pg_repos.device_fingerprint

    def create_attendance_session(self, class_session_id: str,
                                  settings: Dict[str, Any]) -> Tuple[Optional[str], List[str]]:
        """Create a new attendance session with security settings"""
        errors = []

        try:
            course = pg_repos.course.get(class_session_id)
            if not course:
                errors.append("Course not found")
                return None, errors

            existing_sessions = self.attendance_session_repo.get_active_sessions()
            for session in existing_sessions:
                if session.course_id == class_session_id:
                    errors.append("Attendance session already active for this course")
                    return None, errors

            session_code = self._generate_session_code()

            now = datetime.utcnow()
            pg_session = PGAttendanceSession(
                id=str(uuid.uuid4()),
                course_id=class_session_id,
                session_code=session_code,
                start_time=now,
                end_time=now + timedelta(minutes=settings.get('duration_minutes', 15)),
                location_data={
                    'geolocation_enabled': settings.get('geolocation_enabled', False),
                    'geolocation_lat': settings.get('geolocation_lat'),
                    'geolocation_lng': settings.get('geolocation_lng'),
                    'geolocation_radius': settings.get('geolocation_radius', 100),
                    'ip_restriction_enabled': settings.get('ip_restriction_enabled', False),
                    'allowed_ips': settings.get('allowed_ips', [])
                },
                is_active=True,
                status=SessionStatus.ACTIVE
            )

            created = self.attendance_session_repo.create_session(pg_session)
            session_id = created.id

            logger.info(f"Attendance session created: {session_id} with code: {session_code}")
            return session_id, []

        except Exception as e:
            logger.error(f"Failed to create attendance session: {str(e)}")
            errors.append("Internal server error")
            return None, errors

    def mark_attendance(self, session_code: str, student_id: str,
                        request_data: Dict[str, Any]) -> Tuple[bool, str, Optional[str]]:
        """Mark attendance with comprehensive security checks"""
        try:
            session = self.attendance_session_repo.get_by_session_code(session_code)
            if not session:
                return False, "Invalid session code", None

            if not session.is_active:
                return False, "Session is not active", None

            end = session.end_time
            if end and end.tzinfo is not None:
                end = end.replace(tzinfo=None)
            if end and datetime.utcnow() > end:
                return False, "Session has expired", None
            if not end:
                ses_end = session.start_time + timedelta(hours=1)
                if ses_end.tzinfo is not None:
                    ses_end = ses_end.replace(tzinfo=None)
                if datetime.utcnow() > ses_end:
                    return False, "Session has expired", None

            existing_record = self.attendance_record_repo.get_student_attendance(
                session.id, student_id
            )
            if existing_record:
                return False, "Attendance already marked", None

            security_result = self._perform_security_checks(
                student_id, session, request_data
            )

            if not security_result['allowed']:
                return False, security_result['reason'], None

            now = datetime.utcnow()

            record = PGAttendanceRecord(
                id=str(uuid.uuid4()),
                session_id=session.id,
                student_id=student_id,
                institution_id=session.institution_id,
                marked_at=now,
                status=PgAttendanceStatus.PRESENT if not security_result['suspicious'] else PgAttendanceStatus.LATE,
                ip_address=request_data.get('ip_address'),
                device_id=request_data.get('user_agent'),
                device_fingerprint=request_data.get('user_agent')
            )

            if security_result.get('suspicion_reason'):
                record.status = PgAttendanceStatus.LATE

            course_start = session.start_time
            if course_start.tzinfo is not None:
                course_start = course_start.replace(tzinfo=None)
            if now > course_start:
                minutes_late = int((now - course_start).total_seconds() / 60)
                if minutes_late > 0:
                    record.status = PgAttendanceStatus.LATE

            created = self.attendance_record_repo.mark_attendance(record)
            record_id = created.id

            if security_result['suspicious']:
                self._log_suspicious_activity(
                    student_id, session, record, security_result
                )

            logger.info(f"Attendance marked: {record_id} for student: {student_id}")
            return True, "Attendance marked successfully", record_id

        except Exception as e:
            logger.error(f"Failed to mark attendance: {str(e)}")
            return False, "Internal server error", None

    def _perform_security_checks(self, student_id: str, session: Any,
                                 request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Perform comprehensive security checks"""
        result = {
            'allowed': True,
            'reason': '',
            'suspicious': False,
            'suspicion_reason': None,
            'risk_score': 0
        }

        try:
            location_data = session.location_data or {}

            if location_data.get('ip_restriction_enabled'):
                client_ip = request_data.get('ip_address')
                if client_ip not in location_data.get('allowed_ips', []):
                    result['allowed'] = False
                    result['reason'] = "IP address not allowed"
                    return result

            if location_data.get('geolocation_enabled'):
                geo_result = self._check_geolocation(location_data, request_data)
                if not geo_result['valid']:
                    result['allowed'] = False
                    result['reason'] = geo_result['reason']
                    return result
                elif geo_result['suspicious']:
                    result['suspicious'] = True
                    result['suspicion_reason'] = geo_result['reason']
                    result['risk_score'] += geo_result['risk_score']

            device_result = self._check_device_fingerprint(student_id, request_data)
            if device_result['suspicious']:
                result['suspicious'] = True
                result['suspicion_reason'] = device_result['reason']
                result['risk_score'] += device_result['risk_score']

            rapid_result = self._check_rapid_succession(student_id, session.id)
            if rapid_result['suspicious']:
                result['suspicious'] = True
                result['suspicion_reason'] = rapid_result['reason']
                result['risk_score'] += rapid_result['risk_score']

            multi_device_result = self._check_multiple_devices(student_id, session.id)
            if multi_device_result['suspicious']:
                result['suspicious'] = True
                result['suspicion_reason'] = multi_device_result['reason']
                result['risk_score'] += multi_device_result['risk_score']

            time_result = self._check_time_anomaly(student_id, session)
            if time_result['suspicious']:
                result['suspicious'] = True
                result['suspicion_reason'] = time_result['reason']
                result['risk_score'] += time_result['risk_score']

            if result['risk_score'] > 50:
                result['suspicious'] = True
                if not result['suspicion_reason']:
                    result['suspicion_reason'] = "High risk activity detected"

            return result

        except Exception as e:
            logger.error(f"Security checks failed: {str(e)}")
            result['allowed'] = False
            result['reason'] = "Security check failed"
            return result

    def _check_geolocation(self, location_data: Dict[str, Any],
                           request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Check geolocation validity"""
        result = {'valid': True, 'suspicious': False, 'reason': '', 'risk_score': 0}

        try:
            client_lat = request_data.get('geolocation_lat')
            client_lng = request_data.get('geolocation_lng')

            if not client_lat or not client_lng:
                result['valid'] = False
                result['reason'] = "Geolocation required but not provided"
                return result

            allowed_lat = location_data.get('geolocation_lat')
            allowed_lng = location_data.get('geolocation_lng')
            allowed_radius = location_data.get('geolocation_radius', 100)

            if allowed_lat and allowed_lng:
                distance = geodesic(
                    (allowed_lat, allowed_lng),
                    (client_lat, client_lng)
                ).meters

                if distance > allowed_radius:
                    result['valid'] = False
                    result['reason'] = f"Location too far ({distance:.0f}m from allowed location)"
                    return result
                elif distance > allowed_radius * 0.8:
                    result['suspicious'] = True
                    result['reason'] = f"Near location boundary ({distance:.0f}m)"
                    result['risk_score'] = 30

        except Exception as e:
            logger.error(f"Geolocation check failed: {str(e)}")
            result['valid'] = False
            result['reason'] = "Geolocation verification failed"

        return result

    def _check_device_fingerprint(self, student_id: str,
                                  request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Check device fingerprint for anomalies"""
        result = {'suspicious': False, 'reason': '', 'risk_score': 0}

        try:
            user_agent = request_data.get('user_agent')
            ip_address = request_data.get('ip_address')

            if not user_agent or not ip_address:
                return result

            fingerprint_data = f"{user_agent}_{ip_address}"
            fingerprint_hash = hashlib.sha256(fingerprint_data.encode()).hexdigest()

            existing_fingerprints = self.device_fingerprint_repo.get_by_user(student_id)

            if existing_fingerprints:
                known_device = False
                for fp in existing_fingerprints:
                    if fp.fingerprint_hash == fingerprint_hash:
                        known_device = True
                        fp.last_seen = datetime.utcnow()
                        self.device_fingerprint_repo.update(fp)
                        break

                if not known_device:
                    result['suspicious'] = True
                    result['reason'] = "New device detected"
                    result['risk_score'] = 40

                    recent_devices = [
                        fp for fp in existing_fingerprints
                        if (datetime.utcnow() - fp.created_at).days <= 7
                    ]

                    if len(recent_devices) >= 2:
                        result['risk_score'] += 30
                        result['reason'] = "Multiple new devices detected recently"

            from src.infrastructure.models import DeviceFingerprint as PG_DFP
            dfp = PG_DFP(
                id=str(uuid.uuid4()),
                user_id=student_id,
                fingerprint_hash=fingerprint_hash,
                user_agent=user_agent,
                ip_address=ip_address,
                screen_resolution=request_data.get('screen_resolution'),
                timezone=request_data.get('timezone'),
                language=request_data.get('language')
            )
            self.device_fingerprint_repo.create(dfp)

        except Exception as e:
            logger.error(f"Device fingerprint check failed: {str(e)}")

        return result

    def _check_rapid_succession(self, student_id: str, session_id: str) -> Dict[str, Any]:
        """Check for rapid succession attendance marking"""
        result = {'suspicious': False, 'reason': '', 'risk_score': 0}

        try:
            recent_records = self.attendance_record_repo.get_by_student(student_id)

            five_minutes_ago = datetime.utcnow() - timedelta(minutes=5)
            recent_records = [
                record for record in recent_records
                if record.marked_at and record.marked_at > five_minutes_ago
            ]

            if len(recent_records) >= 2:
                result['suspicious'] = True
                result['reason'] = "Multiple attendance marks in rapid succession"
                result['risk_score'] = 60

        except Exception as e:
            logger.error(f"Rapid succession check failed: {str(e)}")

        return result

    def _check_multiple_devices(self, student_id: str, session_id: str) -> Dict[str, Any]:
        """Check for multiple devices in same session"""
        result = {'suspicious': False, 'reason': '', 'risk_score': 0}

        try:
            session_records = self.attendance_record_repo.get_by_session(session_id)

            student_records = [
                record for record in session_records
                if record.student_id == student_id
            ]

            if len(student_records) > 1:
                ips = set(record.ip_address for record in student_records if record.ip_address)
                user_agents = set(record.device_id for record in student_records if record.device_id)

                if len(ips) > 1 or len(user_agents) > 1:
                    result['suspicious'] = True
                    result['reason'] = "Multiple devices/IPs detected in same session"
                    result['risk_score'] = 80

        except Exception as e:
            logger.error(f"Multiple device check failed: {str(e)}")

        return result

    def _check_time_anomaly(self, student_id: str, session: Any) -> Dict[str, Any]:
        """Check for time-based anomalies"""
        result = {'suspicious': False, 'reason': '', 'risk_score': 0}

        try:
            student_records = self.attendance_record_repo.get_by_student(student_id)

            if len(student_records) < 5:
                return result

            marking_times = []
            for record in student_records[-10:]:
                record_session = self.attendance_session_repo.get(record.session_id)
                if record_session and record_session.start_time and record.marked_at:
                    marked_at = record.marked_at
                    ses_start = record_session.start_time
                    if marked_at.tzinfo is not None:
                        marked_at = marked_at.replace(tzinfo=None)
                    if ses_start.tzinfo is not None:
                        ses_start = ses_start.replace(tzinfo=None)
                    marking_times.append((marked_at - ses_start).total_seconds())

            if marking_times:
                avg_time = sum(marking_times) / len(marking_times)
                ses_start = session.start_time
                if ses_start.tzinfo is not None:
                    ses_start = ses_start.replace(tzinfo=None)
                current_time = (datetime.utcnow() - ses_start).total_seconds()

                if abs(current_time - avg_time) > 1800:
                    result['suspicious'] = True
                    result['reason'] = "Unusual attendance marking time"
                    result['risk_score'] = 25

        except Exception as e:
            logger.error(f"Time anomaly check failed: {str(e)}")

        return result

    def _generate_session_code(self) -> str:
        """Generate unique session code"""
        return secrets.token_hex(4).upper()

    def _log_suspicious_activity(self, student_id: str, session: Any,
                                 record: Any, security_result: Dict[str, Any]):
        """Log suspicious activity for investigation"""
        try:
            from src.infrastructure.models import SecurityLog as PG_SecLog
            log_entry = PG_SecLog(
                id=str(uuid.uuid4()),
                user_id=student_id,
                institution_id=session.institution_id,
                event_type=SuspiciousActivityType.MULTIPLE_DEVICES,
                severity='medium',
                description=f"Suspicious attendance activity: {security_result['suspicion_reason']}",
                ip_address=record.ip_address,
                is_resolved=False
            )

            self.security_log_repo.create(log_entry)

            logger.warning(f"Suspicious activity logged for student {student_id}: {security_result['suspicion_reason']}")

        except Exception as e:
            logger.error(f"Failed to log suspicious activity: {str(e)}")

    def get_session_statistics(self, session_id: str) -> Dict[str, Any]:
        """Get comprehensive statistics for an attendance session"""
        try:
            records = self.attendance_record_repo.get_by_session(session_id)

            stats = {
                'session_id': session_id,
                'total_records': len(records),
                'present': 0,
                'late': 0,
                'absent': 0,
                'excused': 0,
                'suspicious': 0,
                'average_marking_time': None,
                'unique_ips': set(),
                'unique_devices': set(),
                'geolocation_coverage': 0
            }

            marking_times = []

            for record in records:
                status = record.status.value if record.status else 'present'
                if status == 'present':
                    stats['present'] += 1
                elif status == 'late':
                    stats['late'] += 1
                elif status == 'absent':
                    stats['absent'] += 1
                elif status == 'excused':
                    stats['excused'] += 1

                if hasattr(record, 'is_suspicious') and record.is_suspicious:
                    stats['suspicious'] += 1

                if record.ip_address:
                    stats['unique_ips'].add(record.ip_address)
                if record.device_id:
                    stats['unique_devices'].add(record.device_id)

                if record.marked_at:
                    marking_times.append(record.marked_at)

                if getattr(record, 'geolocation_lat', None) and getattr(record, 'geolocation_lng', None):
                    stats['geolocation_coverage'] += 1

            if marking_times:
                avg_timestamp = sum(dt.timestamp() for dt in marking_times) / len(marking_times)
                stats['average_marking_time'] = datetime.fromtimestamp(avg_timestamp).isoformat()

            stats['unique_ips'] = len(stats['unique_ips'])
            stats['unique_devices'] = len(stats['unique_devices'])

            if stats['total_records'] > 0:
                stats['geolocation_coverage'] = (stats['geolocation_coverage'] / stats['total_records']) * 100

            return stats

        except Exception as e:
            logger.error(f"Failed to get session statistics: {str(e)}")
            return {}

    def close_attendance_session(self, session_id: str) -> Tuple[bool, str]:
        """Close an attendance session"""
        try:
            session = self.attendance_session_repo.get(session_id)
            if not session:
                return False, "Session not found"

            if not session.is_active:
                return False, "Session already closed"

            success = self.attendance_session_repo.close_session(session_id)

            if success:
                logger.info(f"Attendance session closed: {session_id}")
                return True, "Session closed successfully"
            else:
                return False, "Failed to close session"

        except Exception as e:
            logger.error(f"Failed to close attendance session: {str(e)}")
            return False, "Internal server error"


# Global attendance engine instance
attendance_engine = AttendanceEngine()