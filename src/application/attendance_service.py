from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
import hashlib
import secrets
import logging
from geopy.distance import geodesic

from src.domain.entities import (
    AttendanceSession, AttendanceRecord, ClassSession, User,
    AttendanceStatus, SecurityLog, DeviceFingerprint
)
from src.infrastructure.repositories import (
    attendance_session_repo, attendance_record_repo, class_session_repo,
    user_repo, security_log_repo, device_fingerprint_repo
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
        self.attendance_session_repo = attendance_session_repo
        self.attendance_record_repo = attendance_record_repo
        self.class_session_repo = class_session_repo
        self.user_repo = user_repo
        self.security_log_repo = security_log_repo
        self.device_fingerprint_repo = device_fingerprint_repo
    
    def create_attendance_session(self, class_session_id: str, 
                                settings: Dict[str, Any]) -> Tuple[Optional[str], List[str]]:
        """Create a new attendance session with security settings"""
        errors = []
        
        try:
            # Validate class session
            class_session = self.class_session_repo.get_by_id(class_session_id)
            if not class_session:
                errors.append("Class session not found")
                return None, errors
            
            # Check if there's already an active session
            existing_sessions = self.attendance_session_repo.get_active_sessions()
            for session in existing_sessions:
                if session['class_session_id'] == class_session_id:
                    errors.append("Attendance session already active for this class")
                    return None, errors
            
            # Generate unique session code
            session_code = self._generate_session_code()
            
            # Create attendance session
            attendance_session = AttendanceSession(
                class_session_id=class_session_id,
                session_code=session_code,
                start_time=datetime.utcnow(),
                end_time=datetime.utcnow() + timedelta(minutes=settings.get('duration_minutes', 15)),
                geolocation_enabled=settings.get('geolocation_enabled', False),
                geolocation_lat=settings.get('geolocation_lat'),
                geolocation_lng=settings.get('geolocation_lng'),
                geolocation_radius=settings.get('geolocation_radius', 100),
                ip_restriction_enabled=settings.get('ip_restriction_enabled', False),
                allowed_ips=settings.get('allowed_ips', [])
            )
            
            session_data = {
                'id': attendance_session.id,
                'class_session_id': attendance_session.class_session_id,
                'session_code': attendance_session.session_code,
                'start_time': attendance_session.start_time.isoformat(),
                'end_time': attendance_session.end_time.isoformat(),
                'geolocation_enabled': attendance_session.geolocation_enabled,
                'geolocation_lat': attendance_session.geolocation_lat,
                'geolocation_lng': attendance_session.geolocation_lng,
                'geolocation_radius': attendance_session.geolocation_radius,
                'ip_restriction_enabled': attendance_session.ip_restriction_enabled,
                'allowed_ips': attendance_session.allowed_ips,
                'is_active': attendance_session.is_active,
                'created_at': attendance_session.created_at.isoformat(),
                'updated_at': attendance_session.updated_at.isoformat()
            }
            
            session_id = self.attendance_session_repo.create(session_data)
            
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
            # Validate session
            session = self.attendance_session_repo.get_by_session_code(session_code)
            if not session:
                return False, "Invalid session code", None
            
            if not session['is_active']:
                return False, "Session is not active", None
            
            if datetime.utcnow() > datetime.fromisoformat(session['end_time'].replace('Z', '+00:00')):
                return False, "Session has expired", None
            
            # Check if already marked
            existing_record = self.attendance_record_repo.get_by_student_and_session(
                student_id, session['id']
            )
            if existing_record:
                return False, "Attendance already marked", None
            
            # Perform security checks
            security_result = self._perform_security_checks(
                student_id, session, request_data
            )
            
            if not security_result['allowed']:
                return False, security_result['reason'], None
            
            # Create attendance record
            attendance_record = AttendanceRecord(
                attendance_session_id=session['id'],
                student_id=student_id,
                marked_at=datetime.utcnow(),
                status=AttendanceStatus.PRESENT,
                ip_address=request_data.get('ip_address'),
                user_agent=request_data.get('user_agent'),
                geolocation_lat=request_data.get('geolocation_lat'),
                geolocation_lng=request_data.get('geolocation_lng'),
                is_suspicious=security_result['suspicious'],
                suspicion_reason=security_result['suspicion_reason']
            )
            
            # Check if late
            class_session = self.class_session_repo.get_by_id(session['class_session_id'])
            if class_session:
                session_start = datetime.fromisoformat(class_session['start_time'].replace('Z', '+00:00'))
                if attendance_record.marked_at > session_start:
                    attendance_record.is_late = True
                    attendance_record.minutes_late = int(
                        (attendance_record.marked_at - session_start).total_seconds() / 60
                    )
                    attendance_record.status = AttendanceStatus.LATE
            
            record_data = {
                'id': attendance_record.id,
                'attendance_session_id': attendance_record.attendance_session_id,
                'student_id': attendance_record.student_id,
                'marked_at': attendance_record.marked_at.isoformat(),
                'status': attendance_record.status.value,
                'marked_by': attendance_record.marked_by,
                'ip_address': attendance_record.ip_address,
                'user_agent': attendance_record.user_agent,
                'geolocation_lat': attendance_record.geolocation_lat,
                'geolocation_lng': attendance_record.geolocation_lng,
                'is_late': attendance_record.is_late,
                'minutes_late': attendance_record.minutes_late,
                'notes': attendance_record.notes,
                'is_suspicious': attendance_record.is_suspicious,
                'suspicion_reason': attendance_record.suspicion_reason,
                'created_at': attendance_record.created_at.isoformat(),
                'updated_at': attendance_record.updated_at.isoformat()
            }
            
            record_id = self.attendance_record_repo.create(record_data)
            
            # Log security event if suspicious
            if attendance_record.is_suspicious:
                self._log_suspicious_activity(
                    student_id, session, attendance_record, security_result
                )
            
            logger.info(f"Attendance marked: {record_id} for student: {student_id}")
            return True, "Attendance marked successfully", record_id
            
        except Exception as e:
            logger.error(f"Failed to mark attendance: {str(e)}")
            return False, "Internal server error", None
    
    def _perform_security_checks(self, student_id: str, session: Dict[str, Any], 
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
            # 1. IP Restriction Check
            if session.get('ip_restriction_enabled'):
                client_ip = request_data.get('ip_address')
                if client_ip not in session.get('allowed_ips', []):
                    result['allowed'] = False
                    result['reason'] = "IP address not allowed"
                    return result
            
            # 2. Geolocation Check
            if session.get('geolocation_enabled'):
                geo_result = self._check_geolocation(session, request_data)
                if not geo_result['valid']:
                    result['allowed'] = False
                    result['reason'] = geo_result['reason']
                    return result
                elif geo_result['suspicious']:
                    result['suspicious'] = True
                    result['suspicion_reason'] = geo_result['reason']
                    result['risk_score'] += geo_result['risk_score']
            
            # 3. Device Fingerprint Check
            device_result = self._check_device_fingerprint(student_id, request_data)
            if device_result['suspicious']:
                result['suspicious'] = True
                result['suspicion_reason'] = device_result['reason']
                result['risk_score'] += device_result['risk_score']
            
            # 4. Rapid Succession Check
            rapid_result = self._check_rapid_succession(student_id, session['id'])
            if rapid_result['suspicious']:
                result['suspicious'] = True
                result['suspicion_reason'] = rapid_result['reason']
                result['risk_score'] += rapid_result['risk_score']
            
            # 5. Multiple Device Check
            multi_device_result = self._check_multiple_devices(student_id, session['id'])
            if multi_device_result['suspicious']:
                result['suspicious'] = True
                result['suspicion_reason'] = multi_device_result['reason']
                result['risk_score'] += multi_device_result['risk_score']
            
            # 6. Time Anomaly Check
            time_result = self._check_time_anomaly(student_id, session)
            if time_result['suspicious']:
                result['suspicious'] = True
                result['suspicion_reason'] = time_result['reason']
                result['risk_score'] += time_result['risk_score']
            
            # Determine if suspicious based on risk score
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
    
    def _check_geolocation(self, session: Dict[str, Any], 
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
            
            # Calculate distance from allowed location
            allowed_lat = session.get('geolocation_lat')
            allowed_lng = session.get('geolocation_lng')
            allowed_radius = session.get('geolocation_radius', 100)  # meters
            
            if allowed_lat and allowed_lng:
                distance = geodesic(
                    (allowed_lat, allowed_lng),
                    (client_lat, client_lng)
                ).meters
                
                if distance > allowed_radius:
                    result['valid'] = False
                    result['reason'] = f"Location too far ({distance:.0f}m from allowed location)"
                    return result
                elif distance > allowed_radius * 0.8:  # Close to boundary
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
            
            # Generate device fingerprint
            fingerprint_data = f"{user_agent}_{ip_address}"
            fingerprint_hash = hashlib.sha256(fingerprint_data.encode()).hexdigest()
            
            # Check existing fingerprints for this student
            existing_fingerprints = self.device_fingerprint_repo.get_by_user(student_id)
            
            if existing_fingerprints:
                # Check if this is a known device
                known_device = False
                for fp in existing_fingerprints:
                    if fp['fingerprint_hash'] == fingerprint_hash:
                        known_device = True
                        # Update last seen
                        self.device_fingerprint_repo.update(fp['id'], {
                            'last_seen': datetime.utcnow().isoformat()
                        })
                        break
                
                if not known_device:
                    # New device detected
                    result['suspicious'] = True
                    result['reason'] = "New device detected"
                    result['risk_score'] = 40
                    
                    # Check if multiple new devices recently
                    recent_devices = [fp for fp in existing_fingerprints 
                                    if (datetime.utcnow() - datetime.fromisoformat(
                                        fp['created_at'].replace('Z', '+00:00')
                                    )).days <= 7]
                    
                    if len(recent_devices) >= 2:
                        result['risk_score'] += 30
                        result['reason'] = "Multiple new devices detected recently"
            
            # Create new fingerprint record
            from src.application.auth_service import device_fingerprint_service
            device_fingerprint_service.create_fingerprint(
                student_id, user_agent, ip_address,
                request_data.get('screen_resolution'),
                request_data.get('timezone'),
                request_data.get('language')
            )
            
        except Exception as e:
            logger.error(f"Device fingerprint check failed: {str(e)}")
        
        return result
    
    def _check_rapid_succession(self, student_id: str, session_id: str) -> Dict[str, Any]:
        """Check for rapid succession attendance marking"""
        result = {'suspicious': False, 'reason': '', 'risk_score': 0}
        
        try:
            # Get recent attendance records for this student
            recent_records = self.attendance_record_repo.get_by_student(student_id)
            
            # Filter records from last 5 minutes
            five_minutes_ago = datetime.utcnow() - timedelta(minutes=5)
            recent_records = [
                record for record in recent_records
                if datetime.fromisoformat(record['marked_at'].replace('Z', '+00:00')) > five_minutes_ago
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
            # Get all records for this session
            session_records = self.attendance_record_repo.get_by_session(session_id)
            
            # Check if student has multiple records with different IPs/User Agents
            student_records = [
                record for record in session_records
                if record['student_id'] == student_id
            ]
            
            if len(student_records) > 1:
                # Check for different IPs or user agents
                ips = set(record.get('ip_address') for record in student_records)
                user_agents = set(record.get('user_agent') for record in student_records)
                
                if len(ips) > 1 or len(user_agents) > 1:
                    result['suspicious'] = True
                    result['reason'] = "Multiple devices/IPs detected in same session"
                    result['risk_score'] = 80
            
        except Exception as e:
            logger.error(f"Multiple device check failed: {str(e)}")
        
        return result
    
    def _check_time_anomaly(self, student_id: str, session: Dict[str, Any]) -> Dict[str, Any]:
        """Check for time-based anomalies"""
        result = {'suspicious': False, 'reason': '', 'risk_score': 0}
        
        try:
            # Get student's attendance pattern
            student_records = self.attendance_record_repo.get_by_student(student_id)
            
            if len(student_records) < 5:  # Not enough data for pattern analysis
                return result
            
            # Calculate average marking time relative to session start
            marking_times = []
            for record in student_records[-10:]:  # Last 10 records
                record_session = self.attendance_session_repo.get_by_id(
                    record['attendance_session_id']
                )
                if record_session:
                    class_session = self.class_session_repo.get_by_id(
                        record_session['class_session_id']
                    )
                    if class_session:
                        session_start = datetime.fromisoformat(
                            class_session['start_time'].replace('Z', '+00:00')
                        )
                        marked_at = datetime.fromisoformat(
                            record['marked_at'].replace('Z', '+00:00')
                        )
                        marking_times.append((marked_at - session_start).total_seconds())
            
            if marking_times:
                avg_time = sum(marking_times) / len(marking_times)
                
                # Current marking time
                class_session = self.class_session_repo.get_by_id(session['class_session_id'])
                if class_session:
                    session_start = datetime.fromisoformat(
                        class_session['start_time'].replace('Z', '+00:00')
                    )
                    current_time = (datetime.utcnow() - session_start).total_seconds()
                    
                    # Check if current time is significantly different from average
                    if abs(current_time - avg_time) > 1800:  # 30 minutes difference
                        result['suspicious'] = True
                        result['reason'] = "Unusual attendance marking time"
                        result['risk_score'] = 25
            
        except Exception as e:
            logger.error(f"Time anomaly check failed: {str(e)}")
        
        return result
    
    def _generate_session_code(self) -> str:
        """Generate unique session code"""
        return secrets.token_hex(4).upper()
    
    def _log_suspicious_activity(self, student_id: str, session: Dict[str, Any],
                                record: AttendanceRecord, security_result: Dict[str, Any]):
        """Log suspicious activity for investigation"""
        try:
            security_log = SecurityLog(
                user_id=student_id,
                institution_id=None,  # Will be fetched from user data
                event_type=SuspiciousActivityType.MULTIPLE_DEVICES,
                description=f"Suspicious attendance activity: {security_result['suspicion_reason']}",
                ip_address=record.ip_address,
                user_agent=record.user_agent,
                geolocation_lat=record.geolocation_lat,
                geolocation_lng=record.geolocation_lng,
                risk_score=security_result['risk_score']
            )
            
            log_data = {
                'id': security_log.id,
                'user_id': security_log.user_id,
                'institution_id': security_log.institution_id,
                'event_type': security_log.event_type,
                'description': security_log.description,
                'ip_address': security_log.ip_address,
                'user_agent': security_log.user_agent,
                'geolocation_lat': security_log.geolocation_lat,
                'geolocation_lng': security_log.geolocation_lng,
                'risk_score': security_log.risk_score,
                'is_resolved': security_log.is_resolved,
                'resolved_by': security_log.resolved_by,
                'resolved_at': security_log.resolved_at.isoformat() if security_log.resolved_at else None,
                'created_at': security_log.created_at.isoformat()
            }
            
            self.security_log_repo.create(log_data)
            
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
                # Count by status
                status = record.get('status', 'present')
                if status == 'present':
                    stats['present'] += 1
                elif status == 'late':
                    stats['late'] += 1
                elif status == 'absent':
                    stats['absent'] += 1
                elif status == 'excused':
                    stats['excused'] += 1
                
                # Count suspicious
                if record.get('is_suspicious', False):
                    stats['suspicious'] += 1
                
                # Collect unique IPs and devices
                if record.get('ip_address'):
                    stats['unique_ips'].add(record['ip_address'])
                if record.get('user_agent'):
                    stats['unique_devices'].add(record['user_agent'])
                
                # Collect marking times
                marked_at = datetime.fromisoformat(record['marked_at'].replace('Z', '+00:00'))
                marking_times.append(marked_at)
                
                # Count geolocation records
                if record.get('geolocation_lat') and record.get('geolocation_lng'):
                    stats['geolocation_coverage'] += 1
            
            # Calculate average marking time
            if marking_times:
                avg_timestamp = sum(dt.timestamp() for dt in marking_times) / len(marking_times)
                stats['average_marking_time'] = datetime.fromtimestamp(avg_timestamp).isoformat()
            
            # Convert sets to counts
            stats['unique_ips'] = len(stats['unique_ips'])
            stats['unique_devices'] = len(stats['unique_devices'])
            
            # Calculate geolocation coverage percentage
            if stats['total_records'] > 0:
                stats['geolocation_coverage'] = (stats['geolocation_coverage'] / stats['total_records']) * 100
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get session statistics: {str(e)}")
            return {}
    
    def close_attendance_session(self, session_id: str) -> Tuple[bool, str]:
        """Close an attendance session"""
        try:
            session = self.attendance_session_repo.get_by_id(session_id)
            if not session:
                return False, "Session not found"
            
            if not session['is_active']:
                return False, "Session already closed"
            
            # Update session status
            success = self.attendance_session_repo.update(session_id, {
                'is_active': False,
                'updated_at': datetime.utcnow().isoformat()
            })
            
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
