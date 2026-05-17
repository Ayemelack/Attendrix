from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from enum import Enum
from dataclasses import dataclass, field
import uuid


class UserRole(Enum):
    """User roles in the system"""
    SUPER_ADMIN = "super_admin"
    INSTITUTIONAL_ADMIN = "institutional_admin"
    LECTURER = "lecturer"
    STUDENT = "student"
    EMPLOYEE = "employee"


class AttendanceStatus(Enum):
    """Attendance status options"""
    PRESENT = "present"
    ABSENT = "absent"
    LATE = "late"
    EXCUSED = "excused"


class Voucher:
    """DEPRECATED — use Voucher dataclass below."""
    def __init__(self, id: str, code: str, email: str, role: UserRole,
                 institution_id: str, is_used: bool = False, 
                 created_at: Optional[datetime] = None, used_at: Optional[datetime] = None,
                 expires_at: Optional[datetime] = None):
        self.id = id
        self.code = code
        self.email = email
        self.role = role
        self.institution_id = institution_id
        self.is_used = is_used
        self.created_at = created_at or datetime.utcnow()
        self.used_at = used_at
        self.expires_at = expires_at or (datetime.utcnow() + timedelta(days=7))


@dataclass
class Voucher:
    id: str
    code: str
    email: str
    role: UserRole
    institution_id: str
    is_used: bool = False
    created_at: datetime = None
    used_at: Optional[datetime] = None
    expires_at: datetime = None

    def __post_init__(self):
        if self.id is None:
            self.id = str(uuid.uuid4())
        if self.created_at is None:
            self.created_at = datetime.utcnow()
        if self.expires_at is None:
            self.expires_at = datetime.utcnow() + timedelta(days=7)  # 7-day expiry


class Institution:
    """DEPRECATED — use @dataclass Institution below."""
    def __init__(self, id: str, name: str, code: str, address: str,
                 phone: Optional[str] = None, email: Optional[str] = None,
                 is_active: bool = True, created_at: Optional[datetime] = None):
        self.id = id
        self.name = name
        self.code = code
        self.address = address
        self.phone = phone
        self.email = email
        self.is_active = is_active
        self.created_at = created_at or datetime.utcnow()


class Course:
    """DEPRECATED — use @dataclass Course below."""
    def __init__(self, id: str, institution_id: str, name: str, code: str,
                 department_id: Optional[str] = None, lecturer_id: Optional[str] = None,
                 is_active: bool = True, created_at: Optional[datetime] = None):
        self.id = id
        self.institution_id = institution_id
        self.name = name
        self.code = code
        self.department_id = department_id
        self.lecturer_id = lecturer_id
        self.is_active = is_active
        self.created_at = created_at or datetime.utcnow()


class AttendanceSession:
    """DEPRECATED — use @dataclass AttendanceSession below."""
    def __init__(self, id: str, course_id: str, lecturer_id: str,
                 session_code: str, start_time: datetime, end_time: Optional[datetime] = None,
                 location: Optional[str] = None, is_active: bool = True,
                 created_at: Optional[datetime] = None):
        self.id = id
        self.course_id = course_id
        self.lecturer_id = lecturer_id
        self.session_code = session_code
        self.start_time = start_time
        self.end_time = end_time
        self.location = location
        self.is_active = is_active
        self.created_at = created_at or datetime.utcnow()


class AttendanceRecord:
    """DEPRECATED — use @dataclass AttendanceRecord below."""
    def __init__(self, id: str, session_id: str, student_id: str,
                 mark_time: datetime, status: str, location: Optional[str] = None,
                 device_id: Optional[str] = None, ip_address: Optional[str] = None,
                 created_at: Optional[datetime] = None):
        self.id = id
        self.session_id = session_id
        self.student_id = student_id
        self.mark_time = mark_time
        self.status = status
        self.location = location
        self.device_id = device_id
        self.ip_address = ip_address
        self.created_at = created_at or datetime.utcnow()


class Department:
    """DEPRECATED — use @dataclass Department below."""
    def __init__(self, id: str, institution_id: str, name: str, code: str,
                 head_id: Optional[str] = None, is_active: bool = True,
                 created_at: Optional[datetime] = None):
        self.id = id
        self.institution_id = institution_id
        self.name = name
        self.code = code
        self.head_id = head_id
        self.is_active = is_active
        self.created_at = created_at or datetime.utcnow()


class LeaveStatus(Enum):
    """Leave request status"""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


class SessionStatus(Enum):
    """Attendance session status"""
    SCHEDULED = "scheduled"
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


@dataclass
class Institution:
    """Institution entity"""
    id: str
    name: str
    code: str
    address: str
    phone: str
    email: str
    website: Optional[str] = None
    logo_url: Optional[str] = None
    is_active: bool = True
    settings: Dict[str, Any] = None
    created_at: datetime = None
    updated_at: datetime = None
    
    def __post_init__(self):
        if self.id is None:
            self.id = str(uuid.uuid4())
        if self.created_at is None:
            self.created_at = datetime.utcnow()
        if self.updated_at is None:
            self.updated_at = datetime.utcnow()
        if self.settings is None:
            self.settings = {}


@dataclass
class Department:
    """Department entity"""
    id: str
    institution_id: str
    name: str
    code: str
    description: Optional[str] = None
    head_id: Optional[str] = None
    is_active: bool = True
    created_at: datetime = None
    updated_at: datetime = None
    
    def __post_init__(self):
        if self.id is None:
            self.id = str(uuid.uuid4())
        if self.created_at is None:
            self.created_at = datetime.utcnow()
        if self.updated_at is None:
            self.updated_at = datetime.utcnow()


class User:
    """DEPRECATED — use @dataclass User below."""
    def __init__(self, id: str, institution_id: str, email: str, password_hash: str, 
                 first_name: str, last_name: str, role: UserRole, phone: Optional[str] = None,
                 profile_image_url: Optional[str] = None, is_active: bool = True,
                 email_verified: bool = False, phone_verified: bool = False,
                 last_login: Optional[datetime] = None, created_at: datetime = None,
                 updated_at: datetime = None):
        self.id = id
        self.institution_id = institution_id
        self.email = email
        self.password_hash = password_hash
        self.first_name = first_name
        self.last_name = last_name
        self.role = role
        self.phone = phone
        self.profile_image_url = profile_image_url
        self.is_active = is_active
        self.email_verified = email_verified
        self.phone_verified = phone_verified
        self.last_login = last_login
        self.created_at = created_at
        self.updated_at = updated_at
        
        if self.id is None:
            self.id = str(uuid.uuid4())
        if self.created_at is None:
            self.created_at = datetime.utcnow()
        if self.updated_at is None:
            self.updated_at = datetime.utcnow()
    
    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"
    
    @property
    def is_admin(self) -> bool:
        return self.role in [UserRole.SUPER_ADMIN, UserRole.INSTITUTIONAL_ADMIN]
    
    def __str__(self) -> str:
        return f"User(id={self.id}, email={self.email}, role={self.role.value})"


@dataclass
class User:
    id: str
    institution_id: str
    email: str
    password_hash: str
    first_name: str
    last_name: str
    role: UserRole
    phone: Optional[str] = None
    profile_image_url: Optional[str] = None
    is_active: bool = True
    email_verified: bool = False
    phone_verified: bool = False
    last_login: Optional[datetime] = None
    created_at: datetime = None
    updated_at: datetime = None

    def __post_init__(self):
        if self.id is None:
            self.id = str(uuid.uuid4())
        if self.created_at is None:
            self.created_at = datetime.utcnow()
        if self.updated_at is None:
            self.updated_at = datetime.utcnow()

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"

    @property
    def is_admin(self) -> bool:
        return self.role in [UserRole.SUPER_ADMIN, UserRole.INSTITUTIONAL_ADMIN]

    def __str__(self) -> str:
        return f"User(id={self.id}, email={self.email}, role={self.role.value})"


@dataclass
class UserProfile:
    """Extended user profile information"""
    id: str
    user_id: str
    employee_id: Optional[str] = None
    student_id: Optional[str] = None
    date_of_birth: Optional[datetime] = None
    gender: Optional[str] = None
    address: Optional[str] = None
    emergency_contact_name: Optional[str] = None
    emergency_contact_phone: Optional[str] = None
    department_id: Optional[str] = None
    join_date: Optional[datetime] = None
    metadata: Dict[str, Any] = None
    created_at: datetime = None
    updated_at: datetime = None
    
    def __post_init__(self):
        if self.id is None:
            self.id = str(uuid.uuid4())
        if self.created_at is None:
            self.created_at = datetime.utcnow()
        if self.updated_at is None:
            self.updated_at = datetime.utcnow()
        if self.metadata is None:
            self.metadata = {}


@dataclass
class Course:
    """Course entity"""
    id: str
    institution_id: str
    department_id: str
    code: str
    name: str
    description: Optional[str] = None
    credits: int = 0
    lecturer_id: Optional[str] = None
    is_active: bool = True
    created_at: datetime = None
    updated_at: datetime = None
    
    def __post_init__(self):
        if self.id is None:
            self.id = str(uuid.uuid4())
        if self.created_at is None:
            self.created_at = datetime.utcnow()
        if self.updated_at is None:
            self.updated_at = datetime.utcnow()


@dataclass
class CourseEnrollment:
    """Course enrollment entity"""
    id: str
    course_id: str
    student_id: str
    enrollment_date: datetime
    is_active: bool = True
    created_at: datetime = None
    updated_at: datetime = None
    
    def __post_init__(self):
        if self.id is None:
            self.id = str(uuid.uuid4())
        if self.created_at is None:
            self.created_at = datetime.utcnow()
        if self.updated_at is None:
            self.updated_at = datetime.utcnow()


@dataclass
class Schedule:
    """Schedule entity"""
    id: str
    institution_id: str
    course_id: str
    lecturer_id: str
    room_id: Optional[str] = None
    day_of_week: int = 1  # 1-7 (Monday-Sunday)
    start_time: str = "09:00"
    end_time: str = "10:00"
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    is_recurring: bool = True
    is_active: bool = True
    created_at: datetime = None
    updated_at: datetime = None
    
    def __post_init__(self):
        if self.id is None:
            self.id = str(uuid.uuid4())
        if self.created_at is None:
            self.created_at = datetime.utcnow()
        if self.updated_at is None:
            self.updated_at = datetime.utcnow()


@dataclass
class ClassSession:
    """Individual class session"""
    id: str
    schedule_id: str
    course_id: str
    lecturer_id: str
    session_date: datetime
    start_time: datetime
    end_time: datetime
    room_id: Optional[str] = None
    topic: Optional[str] = None
    notes: Optional[str] = None
    status: SessionStatus = SessionStatus.SCHEDULED
    created_at: datetime = None
    updated_at: datetime = None
    
    def __post_init__(self):
        if self.id is None:
            self.id = str(uuid.uuid4())
        if self.created_at is None:
            self.created_at = datetime.utcnow()
        if self.updated_at is None:
            self.updated_at = datetime.utcnow()


@dataclass
class AttendanceSession:
    """Attendance session for marking attendance"""
    id: str
    class_session_id: str
    session_code: str
    start_time: datetime
    end_time: datetime
    geolocation_enabled: bool = False
    geolocation_lat: Optional[float] = None
    geolocation_lng: Optional[float] = None
    geolocation_radius: int = 100
    ip_restriction_enabled: bool = False
    allowed_ips: List[str] = None
    is_active: bool = True
    created_at: datetime = None
    updated_at: datetime = None
    
    def __post_init__(self):
        if self.id is None:
            self.id = str(uuid.uuid4())
        if self.session_code is None:
            self.session_code = str(uuid.uuid4())[:8].upper()
        if self.created_at is None:
            self.created_at = datetime.utcnow()
        if self.updated_at is None:
            self.updated_at = datetime.utcnow()
        if self.allowed_ips is None:
            self.allowed_ips = []


@dataclass
class AttendanceRecord:
    """Individual attendance record"""
    id: str
    attendance_session_id: str
    student_id: str
    marked_at: datetime
    status: AttendanceStatus = AttendanceStatus.PRESENT
    marked_by: Optional[str] = None  # User ID who marked (if marked by lecturer)
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    geolocation_lat: Optional[float] = None
    geolocation_lng: Optional[float] = None
    is_late: bool = False
    minutes_late: int = 0
    notes: Optional[str] = None
    is_suspicious: bool = False
    suspicion_reason: Optional[str] = None
    created_at: datetime = None
    updated_at: datetime = None
    
    def __post_init__(self):
        if self.id is None:
            self.id = str(uuid.uuid4())
        if self.created_at is None:
            self.created_at = datetime.utcnow()
        if self.updated_at is None:
            self.updated_at = datetime.utcnow()


@dataclass
class LeaveRequest:
    """Leave request entity"""
    id: str
    user_id: str
    institution_id: str
    leave_type: str
    start_date: datetime
    end_date: datetime
    reason: str
    attachment_url: Optional[str] = None
    status: LeaveStatus = LeaveStatus.PENDING
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None
    created_at: datetime = None
    updated_at: datetime = None
    
    def __post_init__(self):
        if self.id is None:
            self.id = str(uuid.uuid4())
        if self.created_at is None:
            self.created_at = datetime.utcnow()
        if self.updated_at is None:
            self.updated_at = datetime.utcnow()


@dataclass
class AuditLog:
    """Audit log entity"""
    id: str
    user_id: Optional[str] = None
    institution_id: Optional[str] = None
    action: str = ""
    resource_type: str = ""
    resource_id: Optional[str] = None
    old_values: Dict[str, Any] = None
    new_values: Dict[str, Any] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.id is None:
            self.id = str(uuid.uuid4())
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()
        if self.old_values is None:
            self.old_values = {}
        if self.new_values is None:
            self.new_values = {}


@dataclass
class SecurityLog:
    """Security event log"""
    id: Optional[str] = None
    user_id: Optional[str] = None
    institution_id: Optional[str] = None
    event_type: str = ""
    description: str = ""
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    geolocation_lat: Optional[float] = None
    geolocation_lng: Optional[float] = None
    risk_score: int = 0
    is_resolved: bool = False
    resolved_by: Optional[str] = None
    resolved_at: Optional[datetime] = None
    created_at: datetime = None
    
    def __post_init__(self):
        if self.id is None:
            self.id = str(uuid.uuid4())
        if self.created_at is None:
            self.created_at = datetime.utcnow()


@dataclass
class DeviceFingerprint:
    """Device fingerprint for security"""
    id: str
    user_id: str
    fingerprint_hash: str
    user_agent: str
    ip_address: str
    screen_resolution: Optional[str] = None
    timezone: Optional[str] = None
    language: Optional[str] = None
    is_trusted: bool = False
    last_seen: datetime = None
    created_at: datetime = None
    
    def __post_init__(self):
        if self.id is None:
            self.id = str(uuid.uuid4())
        if self.last_seen is None:
            self.last_seen = datetime.utcnow()
        if self.created_at is None:
            self.created_at = datetime.utcnow()


@dataclass
class Notification:
    """Notification entity"""
    id: str
    user_id: str
    institution_id: str
    title: str
    message: str
    type: str = "info"
    is_read: bool = False
    action_url: Optional[str] = None
    metadata: Dict[str, Any] = None
    created_at: datetime = None
    read_at: Optional[datetime] = None
    
    def __post_init__(self):
        if self.id is None:
            self.id = str(uuid.uuid4())
        if self.created_at is None:
            self.created_at = datetime.utcnow()
        if self.metadata is None:
            self.metadata = {}


@dataclass
class SystemConfiguration:
    """System configuration"""
    id: str
    institution_id: Optional[str] = None
    key: str = ""
    value: str = ""
    description: Optional[str] = None
    is_active: bool = True
    created_at: datetime = None
    updated_at: datetime = None
    
    def __post_init__(self):
        if self.id is None:
            self.id = str(uuid.uuid4())
        if self.created_at is None:
            self.created_at = datetime.utcnow()
        if self.updated_at is None:
            self.updated_at = datetime.utcnow()


class DemoBookingStatus(Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    SCHEDULED = "scheduled"
    ONBOARDING = "onboarding"
    ACTIVE = "active"
    COMPLETED = "completed"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


@dataclass
class DemoBooking:
    id: str
    email: str
    full_name: str
    phone: str
    institution: str
    institution_type: Optional[str] = None
    number_of_students: Optional[int] = None
    preferred_date: Optional[str] = None
    preferred_time: Optional[str] = None
    status: str = DemoBookingStatus.PENDING.value
    booking_token: Optional[str] = None
    csrf_token: Optional[str] = None
    session_token: Optional[str] = None
    meeting_url: Optional[str] = None
    meeting_provider: Optional[str] = None
    onboarding_progress: Dict[str, Any] = field(default_factory=dict)
    onboarding_completed: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = None
    updated_at: datetime = None
    expires_at: Optional[datetime] = None
    confirmed_at: Optional[datetime] = None
    scheduled_at: Optional[datetime] = None

    def __post_init__(self):
        if self.id is None:
            self.id = str(uuid.uuid4())
        if self.created_at is None:
            self.created_at = datetime.utcnow()
        if self.updated_at is None:
            self.updated_at = datetime.utcnow()
        if self.expires_at is None:
            self.expires_at = datetime.utcnow() + timedelta(days=30)
        if self.booking_token is None:
            self.booking_token = uuid.uuid4().hex
