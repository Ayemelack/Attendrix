from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import logging

from src.domain.entities import (
    Institution, Department, User, UserProfile, Course, CourseEnrollment,
    Schedule, ClassSession, AttendanceSession, AttendanceRecord, LeaveRequest,
    AuditLog, SecurityLog, DeviceFingerprint, Notification, SystemConfiguration,
    UserRole, AttendanceStatus, LeaveStatus, SessionStatus, DemoBooking,
    DemoBookingStatus
)
from src.infrastructure.firebase_service import firebase_service

logger = logging.getLogger(__name__)


class BaseRepository:
    """Base repository class for Firestore operations"""
    
    def __init__(self, collection_name: str):
        self.collection_name = collection_name
        self.firebase_service = firebase_service
    
    def create(self, entity_data: Dict[str, Any], document_id: str = None) -> Optional[str]:
        """Create entity in Firestore"""
        try:
            return self.firebase_service.create_document(
                self.collection_name, entity_data, document_id
            )
        except Exception as e:
            logger.error(f"Failed to create {self.collection_name}: {str(e)}")
            return None
    
    def get_by_id(self, document_id: str) -> Optional[Dict[str, Any]]:
        """Get entity by ID"""
        try:
            return self.firebase_service.get_document(self.collection_name, document_id)
        except Exception as e:
            logger.error(f"Failed to get {self.collection_name} by ID: {str(e)}")
            return None
    
    def get_by_field(self, field: str, value: Any) -> List[Dict[str, Any]]:
        """Get entities by field value"""
        try:
            return self.firebase_service.query_documents(
                self.collection_name,
                filters=[{'field': field, 'value': value}]
            )
        except Exception as e:
            logger.error(f"Failed to get {self.collection_name} by field: {str(e)}")
            return []
    
    def get_by_multiple_fields(self, filters: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Get entities by multiple field filters"""
        try:
            return self.firebase_service.query_documents(
                self.collection_name, filters=filters
            )
        except Exception as e:
            logger.error(f"Failed to get {self.collection_name} by filters: {str(e)}")
            return []
    
    def update(self, document_id: str, data: Dict[str, Any]) -> bool:
        """Update entity"""
        try:
            return self.firebase_service.update_document(
                self.collection_name, document_id, data
            )
        except Exception as e:
            logger.error(f"Failed to update {self.collection_name}: {str(e)}")
            return False
    
    def delete(self, document_id: str) -> bool:
        """Delete entity"""
        try:
            return self.firebase_service.delete_document(self.collection_name, document_id)
        except Exception as e:
            logger.error(f"Failed to delete {self.collection_name}: {str(e)}")
            return False
    
    def list_all(self, limit: int = None, order_by: str = None) -> List[Dict[str, Any]]:
        """List all entities"""
        try:
            return self.firebase_service.query_documents(
                self.collection_name, limit=limit, order_by=order_by
            )
        except Exception as e:
            logger.error(f"Failed to list {self.collection_name}: {str(e)}")
            return []


class InstitutionRepository(BaseRepository):
    """Repository for Institution entities"""
    
    def __init__(self):
        super().__init__('institutions')
    
    def get_by_code(self, code: str) -> Optional[Dict[str, Any]]:
        """Get institution by code"""
        return self.get_by_field('code', code)
    
    def get_active_institutions(self) -> List[Dict[str, Any]]:
        """Get all active institutions"""
        return self.get_by_field('is_active', True)


class DepartmentRepository(BaseRepository):
    """Repository for Department entities"""
    
    def __init__(self):
        super().__init__('departments')
    
    def get_by_institution(self, institution_id: str) -> List[Dict[str, Any]]:
        """Get departments by institution"""
        return self.get_by_field('institution_id', institution_id)
    
    def get_by_code(self, institution_id: str, code: str) -> Optional[Dict[str, Any]]:
        """Get department by institution and code"""
        return self.get_by_multiple_fields([
            {'field': 'institution_id', 'value': institution_id},
            {'field': 'code', 'value': code}
        ])


class UserRepository(BaseRepository):
    """Repository for User entities"""
    
    def __init__(self):
        super().__init__('users')
    
    def get_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Get user by email"""
        users = self.get_by_field('email', email)
        return users[0] if users else None
    
    def get_by_institution(self, institution_id: str) -> List[Dict[str, Any]]:
        """Get users by institution"""
        return self.get_by_field('institution_id', institution_id)
    
    def get_by_role(self, role: UserRole) -> List[Dict[str, Any]]:
        """Get users by role"""
        return self.get_by_field('role', role.value)
    
    def get_by_institution_and_role(self, institution_id: str, role: UserRole) -> List[Dict[str, Any]]:
        """Get users by institution and role"""
        return self.get_by_multiple_fields([
            {'field': 'institution_id', 'value': institution_id},
            {'field': 'role', 'value': role.value}
        ])
    
    def get_active_users(self, institution_id: str = None) -> List[Dict[str, Any]]:
        """Get active users"""
        if institution_id:
            return self.get_by_multiple_fields([
                {'field': 'institution_id', 'value': institution_id},
                {'field': 'is_active', 'value': True}
            ])
        return self.get_by_field('is_active', True)


class UserProfileRepository(BaseRepository):
    """Repository for UserProfile entities"""
    
    def __init__(self):
        super().__init__('user_profiles')
    
    def get_by_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get profile by user ID"""
        profiles = self.get_by_field('user_id', user_id)
        return profiles[0] if profiles else None
    
    def get_by_student_id(self, institution_id: str, student_id: str) -> Optional[Dict[str, Any]]:
        """Get profile by student ID"""
        return self.get_by_multiple_fields([
            {'field': 'institution_id', 'value': institution_id},
            {'field': 'student_id', 'value': student_id}
        ])
    
    def get_by_employee_id(self, institution_id: str, employee_id: str) -> Optional[Dict[str, Any]]:
        """Get profile by employee ID"""
        return self.get_by_multiple_fields([
            {'field': 'institution_id', 'value': institution_id},
            {'field': 'employee_id', 'value': employee_id}
        ])


class CourseRepository(BaseRepository):
    """Repository for Course entities"""
    
    def __init__(self):
        super().__init__('courses')
    
    def get_by_institution(self, institution_id: str) -> List[Dict[str, Any]]:
        """Get courses by institution"""
        return self.get_by_field('institution_id', institution_id)
    
    def get_by_department(self, department_id: str) -> List[Dict[str, Any]]:
        """Get courses by department"""
        return self.get_by_field('department_id', department_id)
    
    def get_by_lecturer(self, lecturer_id: str) -> List[Dict[str, Any]]:
        """Get courses by lecturer"""
        return self.get_by_field('lecturer_id', lecturer_id)
    
    def get_by_code(self, institution_id: str, code: str) -> Optional[Dict[str, Any]]:
        """Get course by institution and code"""
        return self.get_by_multiple_fields([
            {'field': 'institution_id', 'value': institution_id},
            {'field': 'code', 'value': code}
        ])


class CourseEnrollmentRepository(BaseRepository):
    """Repository for CourseEnrollment entities"""
    
    def __init__(self):
        super().__init__('course_enrollments')
    
    def get_by_student(self, student_id: str) -> List[Dict[str, Any]]:
        """Get enrollments by student"""
        return self.get_by_field('student_id', student_id)
    
    def get_by_course(self, course_id: str) -> List[Dict[str, Any]]:
        """Get enrollments by course"""
        return self.get_by_field('course_id', course_id)
    
    def get_active_enrollments(self, course_id: str = None, student_id: str = None) -> List[Dict[str, Any]]:
        """Get active enrollments"""
        filters = [{'field': 'is_active', 'value': True}]
        
        if course_id:
            filters.append({'field': 'course_id', 'value': course_id})
        
        if student_id:
            filters.append({'field': 'student_id', 'value': student_id})
        
        return self.get_by_multiple_fields(filters)


class ScheduleRepository(BaseRepository):
    """Repository for Schedule entities"""
    
    def __init__(self):
        super().__init__('schedules')
    
    def get_by_institution(self, institution_id: str) -> List[Dict[str, Any]]:
        """Get schedules by institution"""
        return self.get_by_field('institution_id', institution_id)
    
    def get_by_course(self, course_id: str) -> List[Dict[str, Any]]:
        """Get schedules by course"""
        return self.get_by_field('course_id', course_id)
    
    def get_by_lecturer(self, lecturer_id: str) -> List[Dict[str, Any]]:
        """Get schedules by lecturer"""
        return self.get_by_field('lecturer_id', lecturer_id)
    
    def get_by_day_of_week(self, day_of_week: int) -> List[Dict[str, Any]]:
        """Get schedules by day of week"""
        return self.get_by_field('day_of_week', day_of_week)
    
    def get_conflicting_schedules(self, lecturer_id: str, day_of_week: int,
                                start_time: str, end_time: str) -> List[Dict[str, Any]]:
        """Get conflicting schedules for a lecturer"""
        # This is a simplified check - in production, you'd want more sophisticated conflict detection
        return self.get_by_multiple_fields([
            {'field': 'lecturer_id', 'value': lecturer_id},
            {'field': 'day_of_week', 'value': day_of_week},
            {'field': 'is_active', 'value': True}
        ])


class ClassSessionRepository(BaseRepository):
    """Repository for ClassSession entities"""
    
    def __init__(self):
        super().__init__('class_sessions')
    
    def get_by_schedule(self, schedule_id: str) -> List[Dict[str, Any]]:
        """Get sessions by schedule"""
        return self.get_by_field('schedule_id', schedule_id)
    
    def get_by_course(self, course_id: str) -> List[Dict[str, Any]]:
        """Get sessions by course"""
        return self.get_by_field('course_id', course_id)
    
    def get_by_lecturer(self, lecturer_id: str) -> List[Dict[str, Any]]:
        """Get sessions by lecturer"""
        return self.get_by_field('lecturer_id', lecturer_id)
    
    def get_by_date_range(self, start_date: datetime, end_date: datetime) -> List[Dict[str, Any]]:
        """Get sessions within date range"""
        # Note: Firestore range queries require composite indexes
        # This is a simplified implementation
        return self.list_all(order_by='session_date')


class AttendanceSessionRepository(BaseRepository):
    """Repository for AttendanceSession entities"""
    
    def __init__(self):
        super().__init__('attendance_sessions')
    
    def get_by_class_session(self, class_session_id: str) -> List[Dict[str, Any]]:
        """Get attendance sessions by class session"""
        return self.get_by_field('class_session_id', class_session_id)
    
    def get_active_sessions(self) -> List[Dict[str, Any]]:
        """Get currently active sessions"""
        return self.get_by_field('is_active', True)
    
    def get_by_session_code(self, session_code: str) -> Optional[Dict[str, Any]]:
        """Get session by code"""
        sessions = self.get_by_field('session_code', session_code)
        return sessions[0] if sessions else None


class AttendanceRecordRepository(BaseRepository):
    """Repository for AttendanceRecord entities"""
    
    def __init__(self):
        super().__init__('attendance_records')
    
    def get_by_session(self, attendance_session_id: str) -> List[Dict[str, Any]]:
        """Get records by attendance session"""
        return self.get_by_field('attendance_session_id', attendance_session_id)
    
    def get_by_student(self, student_id: str) -> List[Dict[str, Any]]:
        """Get records by student"""
        return self.get_by_field('student_id', student_id)
    
    def get_by_student_and_session(self, student_id: str, attendance_session_id: str) -> Optional[Dict[str, Any]]:
        """Get record by student and session"""
        records = self.get_by_multiple_fields([
            {'field': 'student_id', 'value': student_id},
            {'field': 'attendance_session_id', 'value': attendance_session_id}
        ])
        return records[0] if records else None
    
    def get_suspicious_records(self, institution_id: str = None) -> List[Dict[str, Any]]:
        """Get suspicious attendance records"""
        return self.get_by_field('is_suspicious', True)


class LeaveRequestRepository(BaseRepository):
    """Repository for LeaveRequest entities"""
    
    def __init__(self):
        super().__init__('leave_requests')
    
    def get_by_user(self, user_id: str) -> List[Dict[str, Any]]:
        """Get leave requests by user"""
        return self.get_by_field('user_id', user_id)
    
    def get_by_institution(self, institution_id: str) -> List[Dict[str, Any]]:
        """Get leave requests by institution"""
        return self.get_by_field('institution_id', institution_id)
    
    def get_by_status(self, status: LeaveStatus) -> List[Dict[str, Any]]:
        """Get leave requests by status"""
        return self.get_by_field('status', status.value)
    
    def get_pending_requests(self, institution_id: str = None) -> List[Dict[str, Any]]:
        """Get pending leave requests"""
        if institution_id:
            return self.get_by_multiple_fields([
                {'field': 'institution_id', 'value': institution_id},
                {'field': 'status', 'value': LeaveStatus.PENDING.value}
            ])
        return self.get_by_status(LeaveStatus.PENDING)


class AuditLogRepository(BaseRepository):
    """Repository for AuditLog entities"""
    
    def __init__(self):
        super().__init__('audit_logs')
    
    def get_by_user(self, user_id: str) -> List[Dict[str, Any]]:
        """Get audit logs by user"""
        return self.get_by_field('user_id', user_id)
    
    def get_by_institution(self, institution_id: str) -> List[Dict[str, Any]]:
        """Get audit logs by institution"""
        return self.get_by_field('institution_id', institution_id)
    
    def get_by_action(self, action: str) -> List[Dict[str, Any]]:
        """Get audit logs by action"""
        return self.get_by_field('action', action)
    
    def get_by_date_range(self, start_date: datetime, end_date: datetime) -> List[Dict[str, Any]]:
        """Get audit logs within date range"""
        return self.list_all(order_by='timestamp')


class SecurityLogRepository(BaseRepository):
    """Repository for SecurityLog entities"""
    
    def __init__(self):
        super().__init__('security_logs')
    
    def get_by_user(self, user_id: str) -> List[Dict[str, Any]]:
        """Get security logs by user"""
        return self.get_by_field('user_id', user_id)
    
    def get_by_institution(self, institution_id: str) -> List[Dict[str, Any]]:
        """Get security logs by institution"""
        return self.get_by_field('institution_id', institution_id)
    
    def get_by_event_type(self, event_type: str) -> List[Dict[str, Any]]:
        """Get security logs by event type"""
        return self.get_by_field('event_type', event_type)
    
    def get_high_risk_events(self, min_risk_score: int = 50) -> List[Dict[str, Any]]:
        """Get high-risk security events"""
        # Note: Firestore doesn't support greater-than queries on single fields without indexes
        # This is a simplified implementation
        return self.list_all(order_by='risk_score')


class DeviceFingerprintRepository(BaseRepository):
    """Repository for DeviceFingerprint entities"""
    
    def __init__(self):
        super().__init__('device_fingerprints')
    
    def get_by_user(self, user_id: str) -> List[Dict[str, Any]]:
        """Get fingerprints by user"""
        return self.get_by_field('user_id', user_id)
    
    def get_by_hash(self, fingerprint_hash: str) -> List[Dict[str, Any]]:
        """Get fingerprints by hash"""
        return self.get_by_field('fingerprint_hash', fingerprint_hash)
    
    def get_trusted_devices(self, user_id: str) -> List[Dict[str, Any]]:
        """Get trusted devices for user"""
        return self.get_by_multiple_fields([
            {'field': 'user_id', 'value': user_id},
            {'field': 'is_trusted', 'value': True}
        ])


class NotificationRepository(BaseRepository):
    """Repository for Notification entities"""
    
    def __init__(self):
        super().__init__('notifications')
    
    def get_by_user(self, user_id: str) -> List[Dict[str, Any]]:
        """Get notifications by user"""
        return self.get_by_field('user_id', user_id)
    
    def get_unread(self, user_id: str) -> List[Dict[str, Any]]:
        """Get unread notifications for user"""
        return self.get_by_multiple_fields([
            {'field': 'user_id', 'value': user_id},
            {'field': 'is_read', 'value': False}
        ])
    
    def get_by_institution(self, institution_id: str) -> List[Dict[str, Any]]:
        """Get notifications by institution"""
        return self.get_by_field('institution_id', institution_id)


class SystemConfigurationRepository(BaseRepository):
    """Repository for SystemConfiguration entities"""
    
    def __init__(self):
        super().__init__('system_configurations')
    
    def get_by_key(self, key: str, institution_id: str = None) -> Optional[Dict[str, Any]]:
        """Get configuration by key"""
        if institution_id:
            configs = self.get_by_multiple_fields([
                {'field': 'key', 'value': key},
                {'field': 'institution_id', 'value': institution_id}
            ])
        else:
            configs = self.get_by_field('key', key)
        
        return configs[0] if configs else None
    
    def get_by_institution(self, institution_id: str) -> List[Dict[str, Any]]:
        """Get configurations by institution"""
        return self.get_by_field('institution_id', institution_id)
    
    def get_global_configurations(self) -> List[Dict[str, Any]]:
        """Get global configurations (no institution)"""
        # Note: This would require a more complex query in production
        return self.list_all()


class DemoBookingRepository(BaseRepository):
    """Repository for DemoBooking entities"""

    def __init__(self):
        super().__init__('demo_bookings')

    def get_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Get booking by email"""
        bookings = self.get_by_field('email', email)
        if bookings:
            bookings.sort(key=lambda b: b.get('created_at', ''), reverse=True)
        return bookings[0] if bookings else None

    def get_by_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Get booking by booking token"""
        bookings = self.get_by_field('booking_token', token)
        return bookings[0] if bookings else None

    def get_by_session_token(self, session_token: str) -> Optional[Dict[str, Any]]:
        """Get booking by onboarding session token"""
        bookings = self.get_by_field('session_token', session_token)
        if bookings:
            bookings.sort(key=lambda b: b.get('created_at', ''), reverse=True)
        return bookings[0] if bookings else None

    def get_active_by_session_token(self, session_token: str) -> Optional[Dict[str, Any]]:
        """Get non-expired, non-cancelled booking by session token"""
        bookings = self.get_by_field('session_token', session_token)
        active = [b for b in bookings
                  if b.get('status') not in (
                      DemoBookingStatus.CANCELLED.value,
                      DemoBookingStatus.EXPIRED.value
                  )]
        if active:
            active.sort(key=lambda b: b.get('created_at', ''), reverse=True)
        return active[0] if active else None

    def get_active_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Get non-expired, non-cancelled booking by email"""
        bookings = self.get_by_field('email', email)
        active = [b for b in bookings
                  if b.get('status') not in (
                      DemoBookingStatus.CANCELLED.value,
                      DemoBookingStatus.EXPIRED.value
                  )]
        if active:
            active.sort(key=lambda b: b.get('created_at', ''), reverse=True)
        return active[0] if active else None

    def update_status(self, token: str, status: str) -> bool:
        """Update booking status by token"""
        booking = self.get_by_token(token)
        if not booking:
            return False
        return self.update(booking['id'], {'status': status, 'updated_at': datetime.utcnow().isoformat()})

    def to_dict(self, entity: DemoBooking) -> Dict[str, Any]:
        """Convert DemoBooking entity to dict for storage"""
        return {
            'id': entity.id,
            'email': entity.email,
            'full_name': entity.full_name,
            'phone': entity.phone,
            'institution': entity.institution,
            'institution_type': entity.institution_type,
            'number_of_students': entity.number_of_students,
            'preferred_date': entity.preferred_date,
            'preferred_time': entity.preferred_time,
            'status': entity.status,
            'booking_token': entity.booking_token,
            'csrf_token': entity.csrf_token,
            'session_token': entity.session_token,
            'meeting_url': entity.meeting_url,
            'meeting_provider': entity.meeting_provider,
            'onboarding_progress': entity.onboarding_progress,
            'onboarding_completed': entity.onboarding_completed,
            'metadata': entity.metadata,
            'created_at': entity.created_at.isoformat() if entity.created_at else None,
            'updated_at': entity.updated_at.isoformat() if entity.updated_at else None,
            'expires_at': entity.expires_at.isoformat() if entity.expires_at else None,
            'confirmed_at': entity.confirmed_at.isoformat() if entity.confirmed_at else None,
            'scheduled_at': entity.scheduled_at.isoformat() if entity.scheduled_at else None
        }


# Repository instances
institution_repo = InstitutionRepository()
department_repo = DepartmentRepository()
user_repo = UserRepository()
user_profile_repo = UserProfileRepository()
course_repo = CourseRepository()
course_enrollment_repo = CourseEnrollmentRepository()
schedule_repo = ScheduleRepository()
class_session_repo = ClassSessionRepository()
attendance_session_repo = AttendanceSessionRepository()
attendance_record_repo = AttendanceRecordRepository()
leave_request_repo = LeaveRequestRepository()
audit_log_repo = AuditLogRepository()
security_log_repo = SecurityLogRepository()
device_fingerprint_repo = DeviceFingerprintRepository()
notification_repo = NotificationRepository()
system_config_repo = SystemConfigurationRepository()
demo_booking_repo = DemoBookingRepository()
