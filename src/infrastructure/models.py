import uuid
from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, Enum as SAEnum, ForeignKey, JSON, Integer, UniqueConstraint, Float, Text, Index
from sqlalchemy.orm import relationship
import enum

from src.infrastructure.sqlalchemy_db import Base
from src.domain.entities import UserRole

# --- Enums ---

class AttendanceStatus(str, enum.Enum):
    PRESENT = 'present'
    LATE = 'late'
    ABSENT = 'absent'


class SessionStatus(str, enum.Enum):
    ACTIVE = 'ACTIVE'
    CLOSED = 'CLOSED'
    CANCELLED = 'CANCELLED'

class EnrollmentStatus(str, enum.Enum):
    ENROLLED = 'enrolled'
    DROPPED = 'dropped'
    COMPLETED = 'completed'
    SUSPENDED = 'suspended'

# --- Core Models ---

class Institution(Base):
    __tablename__ = 'institutions'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False)
    code = Column(String(50), unique=True, index=True, nullable=False)
    address = Column(String(500), nullable=True)
    phone = Column(String(50), nullable=True)
    email = Column(String(255), nullable=True)
    website = Column(String(255), nullable=True)
    logo_url = Column(String(500), nullable=True)
    timezone = Column(String(50), nullable=True, default='UTC')
    country = Column(String(100), nullable=True)
    city = Column(String(100), nullable=True)
    is_active = Column(Boolean, default=True)
    settings = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    users = relationship("User", back_populates="institution")
    departments = relationship("Department", back_populates="institution")
    courses = relationship("Course", back_populates="institution")


class User(Base):
    __tablename__ = 'users'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(SAEnum(UserRole, values_callable=lambda x: [e.value for e in x]), nullable=False, default=UserRole.STUDENT)
    institution_id = Column(String(36), ForeignKey('institutions.id'), index=True, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    institution = relationship("Institution", back_populates="users")
    profile = relationship("UserProfile", back_populates="user", uselist=False)
    vouchers_used = relationship("Voucher", back_populates="user")
    attendance_records = relationship("AttendanceRecord", back_populates="student")
    sessions_lectured = relationship("AttendanceSession", back_populates="lecturer")
    enrollments = relationship("CourseEnrollment", back_populates="student")


class UserProfile(Base):
    __tablename__ = 'user_profiles'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey('users.id'), unique=True, nullable=False)
    first_name = Column(String(100), nullable=True)
    last_name = Column(String(100), nullable=True)
    employee_id = Column(String(100), index=True, nullable=True)
    student_id = Column(String(100), index=True, nullable=True)
    date_of_birth = Column(DateTime, nullable=True)
    gender = Column(String(50), nullable=True)
    address = Column(String(500), nullable=True)
    phone = Column(String(50), nullable=True)
    emergency_contact_name = Column(String(255), nullable=True)
    emergency_contact_phone = Column(String(50), nullable=True)
    department_id = Column(String(36), ForeignKey('departments.id'), nullable=True)
    join_date = Column(DateTime, nullable=True)
    profile_image_url = Column(String(500), nullable=True)
    nationality = Column(String(100), nullable=True)
    metadata_json = Column(JSON, nullable=True) # Used for extensible data
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="profile")
    department = relationship("Department", foreign_keys=[department_id])


class Department(Base):
    __tablename__ = 'departments'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    institution_id = Column(String(36), ForeignKey('institutions.id'), nullable=False)
    name = Column(String(255), nullable=False)
    code = Column(String(50), nullable=False)
    description = Column(String(1000), nullable=True)
    head_id = Column(String(36), ForeignKey('users.id'), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint('institution_id', 'code', name='uq_department_inst_code'),
    )

    # Relationships
    institution = relationship("Institution", back_populates="departments")
    courses = relationship("Course", back_populates="department")
    head = relationship("User", foreign_keys=[head_id])


class Course(Base):
    __tablename__ = 'courses'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    institution_id = Column(String(36), ForeignKey('institutions.id'), nullable=False)
    department_id = Column(String(36), ForeignKey('departments.id'), nullable=True)
    code = Column(String(50), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(String(1000), nullable=True)
    credits = Column(Integer, default=0)
    lecturer_id = Column(String(36), ForeignKey('users.id'), nullable=True)
    semester = Column(String(50), nullable=True)
    academic_year = Column(String(50), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint('institution_id', 'code', name='uq_course_inst_code'),
    )

    # Relationships
    institution = relationship("Institution", back_populates="courses")
    department = relationship("Department", back_populates="courses")
    lecturer = relationship("User", foreign_keys=[lecturer_id])
    enrollments = relationship("CourseEnrollment", back_populates="course")


class CourseEnrollment(Base):
    __tablename__ = 'course_enrollments'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    course_id = Column(String(36), ForeignKey('courses.id'), nullable=False, index=True)
    student_id = Column(String(36), ForeignKey('users.id'), nullable=False, index=True)
    enrollment_date = Column(DateTime, default=datetime.utcnow)
    status = Column(SAEnum(EnrollmentStatus), nullable=False, default=EnrollmentStatus.ENROLLED)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint('course_id', 'student_id', name='uq_course_student_enrollment'),
    )

    # Relationships
    course = relationship("Course", back_populates="enrollments")
    student = relationship("User", back_populates="enrollments")


class Voucher(Base):
    __tablename__ = 'vouchers'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    code = Column(String(50), unique=True, index=True, nullable=False)
    role = Column(SAEnum(UserRole, values_callable=lambda x: [e.value for e in x]), nullable=False)
    institution_id = Column(String(36), ForeignKey('institutions.id'), index=True, nullable=False)
    email_binding = Column(String(255), nullable=True)
    is_used = Column(Boolean, default=False)
    used_by = Column(String(36), ForeignKey('users.id'), nullable=True)
    used_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)
    revoked = Column(Boolean, default=False)
    revoked_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    assigned_to_email = Column(String(255), nullable=True)
    assigned_to_name = Column(String(255), nullable=True)
    assigned_at = Column(DateTime, nullable=True)
    email_sent_status = Column(String(50), nullable=True)
    email_sent_at = Column(DateTime, nullable=True)

    # Relationships
    user = relationship("User", back_populates="vouchers_used")


class AttendanceSession(Base):
    __tablename__ = 'attendance_sessions'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_code = Column(String(255), nullable=False)
    qr_payload = Column(Text, nullable=True)
    qr_hash = Column(String(255), nullable=True)

    course_id = Column(String(36), ForeignKey("courses.id"))
    institution_id = Column(String(36), ForeignKey("institutions.id"))
    lecturer_id = Column(String(36), ForeignKey("users.id"))

    start_time = Column(DateTime, default=datetime.utcnow)
    end_time = Column(DateTime, nullable=True)
    status = Column(SAEnum(SessionStatus, values_callable=lambda x: [e.value for e in x]), default=SessionStatus.ACTIVE)
    is_active = Column(Boolean, default=True)
    location_data = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_session_course", course_id),
        Index("ix_session_institution", institution_id),
        Index("ix_session_code", session_code, unique=True),
    )

    # Relationships
    lecturer = relationship("User", back_populates="sessions_lectured")
    records = relationship("AttendanceRecord", back_populates="session")
    course = relationship("Course")
    institution = relationship("Institution")


class AttendanceRecord(Base):
    __tablename__ = 'attendance_records'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String(36), ForeignKey("attendance_sessions.id"))
    student_id = Column(String(36), ForeignKey("users.id"))
    institution_id = Column(String(36), ForeignKey("institutions.id"))

    status = Column(SAEnum(AttendanceStatus, values_callable=lambda x: [e.value for e in x]), default=AttendanceStatus.PRESENT)
    marked_at = Column(DateTime, default=datetime.utcnow)

    device_id = Column(String(255), nullable=True)
    ip_address = Column(String(255), nullable=True)

    face_verified = Column(Boolean, default=False)
    biometric_verified = Column(Boolean, default=False)

    device_fingerprint = Column(String(255), nullable=True)
    network_ssid = Column(String(255), nullable=True)
    geo_hash = Column(String(255), nullable=True)

    __table_args__ = (
        Index("ix_record_session", session_id),
        Index("ix_record_student", student_id),
        Index("ix_record_institution", institution_id),
        UniqueConstraint("session_id", "student_id", name="uq_session_student"),
    )

    # Relationships
    session = relationship("AttendanceSession", back_populates="records")
    student = relationship("User", back_populates="attendance_records")
    institution = relationship("Institution")
    verification_logs = relationship("AttendanceVerificationLog", back_populates="record")


class AttendanceVerificationLog(Base):
    __tablename__ = 'attendance_verification_logs'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    attendance_record_id = Column(String(36), ForeignKey("attendance_records.id"))
    
    method = Column(String(50))  # face, fingerprint, device, qr
    score = Column(Float, nullable=True)
    device_id = Column(String(255), nullable=True)
    ip_address = Column(String(255), nullable=True)
    raw_payload = Column(JSON, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)

    # Relationships
    record = relationship("AttendanceRecord", back_populates="verification_logs")


# ==========================================
# PHASE 6: OFFLINE SYNCHRONIZATION & TELEMETRY
# ==========================================

class OfflineQueueItem(Base):
    __tablename__ = "offline_queue"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    institution_id = Column(String(36), ForeignKey("institutions.id"), index=True, nullable=False)
    operation_type = Column(String(50), nullable=False)
    payload = Column(JSON, nullable=False)
    status = Column(String(20), nullable=False, default="pending")
    node_name = Column(String(100), nullable=True)
    priority = Column(Integer, default=0)
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=5)
    next_retry_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)
    conflict_info = Column(JSON, nullable=True)
    checksum = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    synced_at = Column(DateTime, nullable=True)

class NetworkPresence(Base):
    __tablename__ = "network_presence"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), index=True, nullable=False)
    institution_id = Column(String(36), ForeignKey("institutions.id"), index=True, nullable=False)
    ip_address = Column(String(255), nullable=True)
    user_agent = Column(Text, nullable=True)
    browser = Column(String(100), nullable=True)
    os = Column(String(100), nullable=True)
    device_type = Column(String(100), nullable=True)
    login_time = Column(DateTime, default=datetime.utcnow)
    last_activity_time = Column(DateTime, default=datetime.utcnow)

class ActivityLog(Base):
    __tablename__ = "activity_logs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    institution_id = Column(String(36), ForeignKey("institutions.id"), index=True, nullable=False)
    user_id = Column(String(36), ForeignKey("users.id"), index=True, nullable=True)
    type = Column(String(50), nullable=False)
    message = Column(Text, nullable=False)
    faculty = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class DeviceFingerprint(Base):
    __tablename__ = "device_fingerprints"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), index=True, nullable=False)
    fingerprint_hash = Column(String(255), nullable=False)
    user_agent = Column(String(500), nullable=True)
    ip_address = Column(String(255), nullable=True)
    screen_resolution = Column(String(100), nullable=True)
    timezone = Column(String(100), nullable=True)
    language = Column(String(100), nullable=True)
    is_trusted = Column(Boolean, default=False)
    last_seen = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)


class SecurityLog(Base):
    __tablename__ = "security_logs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    institution_id = Column(String(36), ForeignKey("institutions.id"), index=True, nullable=False)
    user_id = Column(String(36), ForeignKey("users.id"), index=True, nullable=True)
    event_type = Column(String(50), nullable=False)
    severity = Column(String(50), nullable=False)
    description = Column(Text, nullable=True)
    ip_address = Column(String(255), nullable=True)
    is_resolved = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
