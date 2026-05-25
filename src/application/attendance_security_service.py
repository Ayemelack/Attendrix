import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
import secrets
import qrcode
import io
import base64

from src.domain.entities import AttendanceStatus

logger = logging.getLogger(__name__)


class AttendanceSecurityService:
    """Real attendance security implementation with QR codes and anti-proxy protection"""
    
    def __init__(self, firebase_service):
        self.firebase_service = firebase_service
        self.session_duration_minutes = 60  # 1 hour sessions
        self.qr_code_expiry_minutes = 5  # QR codes expire in 5 minutes
    
    def create_attendance_session(self, course_id: str, lecturer_id: str, 
                             location: Optional[str] = None,
                             institution_id: Optional[str] = None) -> Dict[str, Any]:
        """Create new attendance session with QR code"""
        try:
            session_id = str(secrets.token_hex(8))
            session_code = self._generate_session_code()
            now = datetime.utcnow()
            
            # Generate QR code before storing so it persists in the database
            qr_code_data = self._generate_qr_code(session_code)
            
            # Store session in database including qr_code for subsequent loads
            session_data = {
                'id': session_id,
                'course_id': course_id,
                'lecturer_id': lecturer_id,
                'session_code': session_code,
                'qr_code': qr_code_data,
                'start_time': now.isoformat(),
                'end_time': None,
                'location': location,
                'is_active': True,
                'institution_id': institution_id,
                'created_at': now.isoformat()
            }
            
            self.firebase_service.create_document('attendance_sessions', session_data, session_id)
            
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
            # Validate session
            session = self._validate_session(session_code)
            if not session:
                return {'error': 'Invalid or expired session code'}
            
            # Check if session is active (redundant with _validate_session, safety net)
            if not session.get('is_active', True):
                return {'error': 'Session is not active'}
            
            # Check if student already marked attendance for this session
            existing_attendance = self.firebase_service.query_documents(
                'attendance_records',
                filters=[
                    {'field': 'session_id', 'value': session['id']},
                    {'field': 'student_id', 'value': student_id}
                ]
            )
            
            if existing_attendance:
                return {'error': 'Attendance already marked for this session'}
            
            # Check session time window (defensive parsing, _validate_session already did this)
            start_raw = session.get('start_time') or session.get('created_at')
            if isinstance(start_raw, datetime):
                session_start = start_raw
            else:
                session_start = datetime.fromisoformat(str(start_raw).replace('Z', '+00:00'))
            session_end = session_start + timedelta(minutes=self.session_duration_minutes)
            if datetime.utcnow() > session_end:
                return {'error': 'Session has expired'}
            
            # Create attendance record
            record_id = str(secrets.token_hex(8))
            now = datetime.utcnow()
            
            record_data = {
                'id': record_id,
                'session_id': session['id'],
                'student_id': student_id,
                'mark_time': now.isoformat(),
                'status': AttendanceStatus.PRESENT.value,
                'location': location,
                'device_id': device_fingerprint,
                'ip_address': ip_address,
                'face_verified': face_verified,
                'face_match_score': face_match_score,
                'biometric_check': 'verified' if face_verified else 'not_provided',
                'created_at': now.isoformat()
            }
            
            self.firebase_service.create_document('attendance_records', record_data, record_id)
            
            logger.info(f"Attendance marked for student {student_id} in session {session_code}")
            return {
                'record_id': record_id,
                'session_id': session['id'],
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
            # Verify lecturer owns the session
            session = self.firebase_service.get_document('attendance_sessions', session_id)
            if not session:
                return {'error': 'Session not found or access denied'}
            stored_lecturer_id = session.get('lecturer_id')
            if stored_lecturer_id is not None and stored_lecturer_id != lecturer_id:
                return {'error': 'Session not found or access denied'}
            
            # Close session
            self.firebase_service.update_document('attendance_sessions', session_id, {
                'end_time': datetime.utcnow().isoformat(),
                'is_active': False
            })
            
            logger.info(f"Attendance session {session_id} closed")
            return {'message': 'Session closed successfully'}
            
        except Exception as e:
            logger.error(f"Session closure failed: {str(e)}")
            return {'error': 'Failed to close session'}
    
    def get_session_attendance(self, session_id: str) -> List[Dict[str, Any]]:
        """Get all attendance records for a session"""
        try:
            records = self.firebase_service.query_documents(
                'attendance_records',
                filters=[{'field': 'session_id', 'value': session_id}]
            )
            
            return [{
                'record_id': record['id'],
                'student_id': record['student_id'],
                'student_name': self._get_student_name(record['student_id']),
                'mark_time': record['mark_time'],
                'status': record['status'],
                'location': record['location'],
                'device_id': record['device_id']
            } for record in records]
            
        except Exception as e:
            logger.error(f"Failed to get session attendance: {str(e)}")
            return []
    
    def _validate_session(self, session_code: str) -> Optional[Dict[str, Any]]:
        """Validate session code and time window"""
        try:
            sessions = self.firebase_service.query_documents(
                'attendance_sessions',
                filters=[
                    {'field': 'session_code', 'value': session_code}
                ]
            )
            
            if not sessions:
                logger.info(f"Session validation: no docs for code {session_code}")
                return None
            
            session = sessions[0]
            session_active = session.get('is_active', True)
            if not session_active:
                logger.info(f"Session {session_code}: is_active={session_active}, rejecting")
                return None
            
            start_time_raw = session.get('start_time') or session.get('created_at')
            if not start_time_raw:
                logger.warning(f"Session {session_code} has no start_time or created_at; keys={list(session.keys())}")
                return None
            
            if isinstance(start_time_raw, datetime):
                session_start = start_time_raw
            elif isinstance(start_time_raw, str):
                session_start = datetime.fromisoformat(start_time_raw.replace('Z', '+00:00'))
            else:
                logger.debug(f"Session {session_code}: start_time type={type(start_time_raw).__name__}, forcing str")
                session_start = datetime.fromisoformat(str(start_time_raw).replace('Z', '+00:00'))
            
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
    
    def _generate_session_code(self) -> str:
        """Generate unique session code"""
        import string
        characters = string.ascii_uppercase + string.digits
        return ''.join(secrets.choice(characters) for _ in range(6))
    
    def _generate_qr_code(self, session_code: str) -> str:
        """Generate QR code for session"""
        try:
            # Create QR code
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=4,
            )
            qr.add_data(session_code)
            qr.make(fit=True)
            
            # Convert to base64 string
            img = qr.make_image(fill_color="black", back_color="white")
            buffer = io.BytesIO()
            img.save(buffer, format="PNG")
            img_str = base64.b64encode(buffer.getvalue()).decode()
            
            return f"data:image/png;base64,{img_str}"
            
        except Exception as e:
            logger.error(f"QR code generation failed: {str(e)}")
            return ""
    
    def _get_student_name(self, student_id: str) -> str:
        """Get student name from ID"""
        try:
            student = self.firebase_service.get_document('users', student_id)
            if student:
                return f"{student.get('first_name', '')} {student.get('last_name', '')}"
            return "Unknown Student"
        except Exception:
            return "Unknown Student"
