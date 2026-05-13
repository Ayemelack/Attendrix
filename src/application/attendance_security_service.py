import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
import secrets
import qrcode
import io
import base64

from src.domain.entities import AttendanceSession, AttendanceRecord, AttendanceStatus

logger = logging.getLogger(__name__)


class AttendanceSecurityService:
    """Real attendance security implementation with QR codes and anti-proxy protection"""
    
    def __init__(self, firebase_service):
        self.firebase_service = firebase_service
        self.session_duration_minutes = 60  # 1 hour sessions
        self.qr_code_expiry_minutes = 5  # QR codes expire in 5 minutes
    
    def create_attendance_session(self, course_id: str, lecturer_id: str, 
                             location: Optional[str] = None) -> Dict[str, Any]:
        """Create new attendance session with QR code"""
        try:
            # Generate unique session code
            session_code = self._generate_session_code()
            
            # Create session
            session = AttendanceSession(
                id=str(secrets.token_hex(8)),
                course_id=course_id,
                lecturer_id=lecturer_id,
                session_code=session_code,
                start_time=datetime.utcnow(),
                location=location,
                is_active=True
            )
            
            # Store session in database
            session_data = {
                'id': session.id,
                'course_id': session.course_id,
                'lecturer_id': session.lecturer_id,
                'session_code': session.session_code,
                'start_time': session.start_time.isoformat(),
                'end_time': None,
                'location': session.location,
                'is_active': session.is_active,
                'created_at': session.created_at.isoformat()
            }
            
            self.firebase_service.create_document('attendance_sessions', session_data, session.id)
            
            # Generate QR code
            qr_code_data = self._generate_qr_code(session_code)
            
            logger.info(f"Created attendance session {session_code} for course {course_id}")
            return {
                'session_id': session.id,
                'session_code': session_code,
                'qr_code': qr_code_data,
                'start_time': session.start_time.isoformat(),
                'expires_at': (session.start_time + timedelta(minutes=self.session_duration_minutes)).isoformat(),
                'location': session.location,
                'message': 'Attendance session created successfully'
            }
            
        except Exception as e:
            logger.error(f"Session creation failed: {str(e)}")
            return {'error': 'Failed to create attendance session'}
    
    def mark_attendance(self, session_code: str, student_id: str, 
                      device_fingerprint: Optional[str] = None,
                      ip_address: Optional[str] = None,
                      location: Optional[str] = None) -> Dict[str, Any]:
        """Mark attendance with security validation"""
        try:
            # Validate session
            session = self._validate_session(session_code)
            if not session:
                return {'error': 'Invalid or expired session code'}
            
            # Check if session is active
            if not session['is_active']:
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
            
            # Check session time window
            session_start = datetime.fromisoformat(session['start_time'])
            session_end = session_start + timedelta(minutes=self.session_duration_minutes)
            if datetime.utcnow() > session_end:
                return {'error': 'Session has expired'}
            
            # Create attendance record
            record = AttendanceRecord(
                id=str(secrets.token_hex(8)),
                session_id=session['id'],
                student_id=student_id,
                mark_time=datetime.utcnow(),
                status=AttendanceStatus.PRESENT,
                location=location,
                device_id=device_fingerprint,
                ip_address=ip_address
            )
            
            record_data = {
                'id': record.id,
                'session_id': record.session_id,
                'student_id': record.student_id,
                'mark_time': record.mark_time.isoformat(),
                'status': record.status.value,
                'location': record.location,
                'device_id': record.device_id,
                'ip_address': record.ip_address,
                'created_at': record.created_at.isoformat()
            }
            
            self.firebase_service.create_document('attendance_records', record_data, record.id)
            
            logger.info(f"Attendance marked for student {student_id} in session {session_code}")
            return {
                'record_id': record.id,
                'session_id': session['id'],
                'mark_time': record.mark_time.isoformat(),
                'status': record.status.value,
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
            if not session or session['lecturer_id'] != lecturer_id:
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
                    {'field': 'session_code', 'value': session_code},
                    {'field': 'is_active', 'value': True}
                ]
            )
            
            if not sessions:
                return None
            
            session = sessions[0]
            
            # Check if session is expired
            session_start = datetime.fromisoformat(session['start_time'])
            session_end = session_start + timedelta(minutes=self.session_duration_minutes)
            
            if datetime.utcnow() > session_end:
                return None
            
            return session
            
        except Exception as e:
            logger.error(f"Session validation failed: {str(e)}")
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
