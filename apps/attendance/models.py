"""
Attendance models for Attendrix - Advanced attendance engine with anti-proxy mechanisms
"""
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from django.core.exceptions import ValidationError
from apps.core.models import TimeStampedModel, SoftDeleteModel, AuditModel, TenantModel
from apps.institutions.models import Institution
from apps.users.models import User
from apps.courses.models import Course, CourseEnrollment
from apps.scheduling.models import ScheduleOccurrence
import uuid
import hashlib


class AttendanceSession(TimeStampedModel, SoftDeleteModel, AuditModel, TenantModel):
    """
    Attendance session for tracking attendance in real-time
    """
    SESSION_TYPES = [
        ('class', 'Class Session'),
        ('exam', 'Exam Session'),
        ('meeting', 'Meeting'),
        ('event', 'Event'),
        ('lab', 'Laboratory Session'),
        ('other', 'Other'),
    ]

    VERIFICATION_METHODS = [
        ('session_code', 'Session Code'),
        ('qr_code', 'QR Code'),
        ('geolocation', 'Geolocation'),
        ('biometric', 'Biometric'),
        ('ip_address', 'IP Address'),
        ('face_recognition', 'Face Recognition'),
        ('manual', 'Manual Override'),
    ]

    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    session_type = models.CharField(max_length=20, choices=SESSION_TYPES)
    
    # Course and Schedule Association
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name='attendance_sessions'
    )
    schedule_occurrence = models.OneToOneField(
        ScheduleOccurrence,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='attendance_session'
    )
    
    # Session Timing
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    duration_minutes = models.IntegerField()
    grace_period_minutes = models.IntegerField(default=15)
    
    # Session Control
    session_code = models.CharField(max_length=10, unique=True)
    is_active = models.BooleanField(default=False)
    auto_close = models.BooleanField(default=True)
    actual_end_time = models.DateTimeField(null=True, blank=True)
    
    # Verification Settings
    verification_methods = models.JSONField(default=list)  # List of allowed methods
    require_geolocation = models.BooleanField(default=False)
    geolocation_radius = models.FloatField(default=100.0)  # meters
    allowed_ip_ranges = models.JSONField(default=list)  # List of allowed IP ranges
    require_device_fingerprint = models.BooleanField(default=True)
    
    # Location Settings
    location_name = models.CharField(max_length=200, blank=True)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    
    # Security Settings
    max_attempts = models.IntegerField(default=3)
    attempt_timeout_minutes = models.IntegerField(default=5)
    duplicate_check_window_minutes = models.IntegerField(default=10)
    
    # Lecturer
    lecturer = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='conducted_sessions',
        limit_choices_to={'role': 'lecturer'}
    )
    
    # Statistics
    total_enrolled = models.IntegerField(default=0)
    total_present = models.IntegerField(default=0)
    total_absent = models.IntegerField(default=0)
    total_late = models.IntegerField(default=0)
    total_excused = models.IntegerField(default=0)
    
    class Meta:
        db_table = 'attendance_session'
        verbose_name = 'Attendance Session'
        verbose_name_plural = 'Attendance Sessions'
        indexes = [
            models.Index(fields=['institution', 'start_time']),
            models.Index(fields=['course']),
            models.Index(fields=['lecturer']),
            models.Index(fields=['session_code']),
            models.Index(fields=['is_active']),
            models.Index(fields=['start_time', 'end_time']),
        ]

    def __str__(self):
        return f"{self.title} - {self.session_code}"

    def save(self, *args, **kwargs):
        # Generate session code if not provided
        if not self.session_code:
            self.session_code = self._generate_session_code()
        
        # Calculate duration if not provided
        if not self.duration_minutes and self.start_time and self.end_time:
            self.duration_minutes = int((self.end_time - self.start_time).total_seconds() / 60)
        
        # Update enrolled count
        if self.course:
            self.total_enrolled = self.course.enrollments.filter(status='enrolled').count()
        
        super().save(*args, **kwargs)

    def _generate_session_code(self):
        """Generate unique session code"""
        import random
        import string
        while True:
            code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
            if not AttendanceSession.objects.filter(session_code=code).exists():
                return code

    @property
    def is_expired(self):
        """Check if session has expired"""
        return timezone.now() > self.end_time

    @property
    def attendance_rate(self):
        """Calculate attendance rate"""
        if self.total_enrolled == 0:
            return 0.0
        return (self.total_present / self.total_enrolled) * 100

    def can_mark_attendance(self, user):
        """Check if user can mark attendance for this session"""
        # Check if session is active
        if not self.is_active or self.is_expired:
            return False, "Session is not active or has expired"
        
        # Check if user is enrolled in course
        if not CourseEnrollment.objects.filter(
            student=user,
            course=self.course,
            status='enrolled'
        ).exists():
            return False, "User is not enrolled in this course"
        
        # Check if already marked
        if AttendanceRecord.objects.filter(
            session=self,
            student=user,
            is_deleted=False
        ).exists():
            return False, "Attendance already marked"
        
        return True, "Can mark attendance"

    def verify_location(self, latitude, longitude):
        """Verify geolocation"""
        if not self.require_geolocation or not self.latitude or not self.longitude:
            return True
        
        # Calculate distance using Haversine formula
        from math import radians, sin, cos, sqrt, atan2
        
        R = 6371000  # Earth's radius in meters
        
        lat1, lon1 = radians(self.latitude), radians(self.longitude)
        lat2, lon2 = radians(latitude), radians(longitude)
        
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * atan2(sqrt(a), sqrt(1-a))
        
        distance = R * c
        
        return distance <= self.geolocation_radius

    def verify_ip_address(self, ip_address):
        """Verify IP address"""
        if not self.allowed_ip_ranges:
            return True
        
        # Simple IP range checking (can be enhanced)
        for allowed_range in self.allowed_ip_ranges:
            if ip_address.startswith(allowed_range):
                return True
        
        return False

    def verify_device_fingerprint(self, fingerprint):
        """Verify device fingerprint"""
        if not self.require_device_fingerprint:
            return True
        
        # Check for suspicious patterns
        recent_attendance = AttendanceRecord.objects.filter(
            session=self,
            device_fingerprint=fingerprint,
            created_at__gte=timezone.now() - timezone.timedelta(minutes=self.duplicate_check_window_minutes)
        ).count()
        
        return recent_attendance == 0


class AttendanceRecord(TimeStampedModel, SoftDeleteModel, AuditModel, TenantModel):
    """
    Individual attendance record
    """
    ATTENDANCE_STATUSES = [
        ('present', 'Present'),
        ('absent', 'Absent'),
        ('late', 'Late'),
        ('excused', 'Excused'),
        ('suspended', 'Suspended'),
    ]

    MARKING_METHODS = [
        ('session_code', 'Session Code'),
        ('qr_code', 'QR Code'),
        ('geolocation', 'Geolocation'),
        ('biometric', 'Biometric'),
        ('ip_address', 'IP Address'),
        ('face_recognition', 'Face Recognition'),
        ('manual', 'Manual Override'),
    ]

    session = models.ForeignKey(
        AttendanceSession,
        on_delete=models.CASCADE,
        related_name='attendance_records'
    )
    student = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='attendance_records',
        limit_choices_to={'role': 'student'}
    )
    
    # Attendance Details
    status = models.CharField(max_length=20, choices=ATTENDANCE_STATUSES)
    marking_method = models.CharField(max_length=20, choices=MARKING_METHODS)
    marked_at = models.DateTimeField(auto_now_add=True)
    
    # Timing
    check_in_time = models.DateTimeField()
    check_out_time = models.DateTimeField(null=True, blank=True)
    minutes_late = models.IntegerField(default=0)
    
    # Location Verification
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    location_accuracy = models.FloatField(null=True, blank=True)
    location_verified = models.BooleanField(default=False)
    
    # Device Verification
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    device_fingerprint = models.CharField(max_length=255, blank=True)
    device_trusted = models.BooleanField(default=False)
    
    # Security
    verification_score = models.FloatField(default=0.0)  # 0-100 confidence score
    is_suspicious = models.BooleanField(default=False)
    security_flags = models.JSONField(default=list, blank=True)
    
    # Notes and Justification
    notes = models.TextField(blank=True)
    excuse_reason = models.TextField(blank=True)
    excuse_document = models.FileField(upload_to='excuse_documents/', blank=True)
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_attendance',
        limit_choices_to={'role': 'lecturer'}
    )
    
    class Meta:
        db_table = 'attendance_record'
        verbose_name = 'Attendance Record'
        verbose_name_plural = 'Attendance Records'
        unique_together = ['session', 'student']
        indexes = [
            models.Index(fields=['session', 'student']),
            models.Index(fields=['student', 'marked_at']),
            models.Index(fields=['status']),
            models.Index(fields=['marking_method']),
            models.Index(fields=['is_suspicious']),
            models.Index(fields=['verification_score']),
        ]

    def __str__(self):
        return f"{self.student.get_full_name()} - {self.session.title} - {self.status}"

    def save(self, *args, **kwargs):
        # Calculate if late
        if self.check_in_time and self.session.start_time:
            if self.check_in_time > self.session.start_time:
                delta = self.check_in_time - self.session.start_time
                self.minutes_late = int(delta.total_seconds() / 60)
                
                # Set status to late if within grace period and marked as present
                if self.status == 'present' and self.minutes_late <= self.session.grace_period_minutes:
                    self.status = 'late'
        
        # Calculate verification score
        self.verification_score = self._calculate_verification_score()
        
        # Check for suspicious patterns
        self.is_suspicious = self._is_suspicious()
        
        super().save(*args, **kwargs)

    def _calculate_verification_score(self):
        """Calculate verification confidence score"""
        score = 50  # Base score
        
        # Location verification
        if self.location_verified:
            score += 20
        
        # Device fingerprint
        if self.device_trusted:
            score += 15
        
        # IP verification
        if self.session.verify_ip_address(self.ip_address):
            score += 10
        
        # Timing (not too early or late)
        if self.check_in_time:
            session_start = self.session.start_time
            if session_start - timezone.timedelta(minutes=15) <= self.check_in_time <= session_start + timezone.timedelta(minutes=30):
                score += 5
        
        return min(100, score)

    def _is_suspicious(self):
        """Check for suspicious attendance patterns"""
        flags = []
        
        # Low verification score
        if self.verification_score < 50:
            flags.append('low_verification_score')
        
        # Multiple attempts in short time
        recent_attempts = AttendanceRecord.objects.filter(
            student=self.student,
            session=self.session,
            created_at__gte=self.created_at - timezone.timedelta(minutes=5)
        ).count()
        
        if recent_attempts > 1:
            flags.append('multiple_attempts')
        
        # Unusual location
        if self.latitude and self.longitude and self.session.latitude and self.session.longitude:
            distance = self._calculate_distance(
                self.latitude, self.longitude,
                self.session.latitude, self.session.longitude
            )
            if distance > self.session.geolocation_radius * 2:
                flags.append('unusual_location')
        
        # Device fingerprint mismatch
        if self.device_fingerprint:
            trusted_devices = AttendanceRecord.objects.filter(
                student=self.student,
                device_fingerprint=self.device_fingerprint,
                device_trusted=True
            ).count()
            
            if trusted_devices == 0:
                flags.append('unknown_device')
        
        self.security_flags = flags
        return len(flags) > 0

    def _calculate_distance(self, lat1, lon1, lat2, lon2):
        """Calculate distance between two points"""
        from math import radians, sin, cos, sqrt, atan2
        
        R = 6371000  # Earth's radius in meters
        
        lat1_rad, lon1_rad = radians(lat1), radians(lon1)
        lat2_rad, lon2_rad = radians(lat2), radians(lon2)
        
        dlat = lat2_rad - lat1_rad
        dlon = lon2_rad - lon1_rad
        
        a = sin(dlat/2)**2 + cos(lat1_rad) * cos(lat2_rad) * sin(dlon/2)**2
        c = 2 * atan2(sqrt(a), sqrt(1-a))
        
        return R * c


class AttendanceStatistics(TimeStampedModel, TenantModel):
    """
    Attendance statistics and analytics
    """
    STATISTICS_TYPES = [
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
        ('semester', 'Semester'),
        ('course', 'Course'),
        ('student', 'Student'),
        ('lecturer', 'Lecturer'),
    ]

    statistics_type = models.CharField(max_length=20, choices=STATISTICS_TYPES)
    reference_id = models.UUIDField(null=True, blank=True)  # Course ID, Student ID, etc.
    reference_date = models.DateField()
    
    # Attendance Metrics
    total_sessions = models.IntegerField(default=0)
    total_attendance_records = models.IntegerField(default=0)
    present_count = models.IntegerField(default=0)
    absent_count = models.IntegerField(default=0)
    late_count = models.IntegerField(default=0)
    excused_count = models.IntegerField(default=0)
    
    # Calculated Metrics
    attendance_rate = models.FloatField(default=0.0)
    punctuality_rate = models.FloatField(default=0.0)  # On-time rate
    engagement_score = models.FloatField(default=0.0)
    
    # Risk Assessment
    dropout_risk_score = models.FloatField(default=0.0)  # 0-100
    performance_risk_score = models.FloatField(default=0.0)  # 0-100
    
    # Trends
    attendance_trend = models.FloatField(default=0.0)  # Positive or negative trend
    trend_direction = models.CharField(
        max_length=10,
        choices=[
            ('improving', 'Improving'),
            ('declining', 'Declining'),
            ('stable', 'Stable'),
        ],
        default='stable'
    )
    
    # Additional Data
    metadata = models.JSONField(default=dict, blank=True)
    
    class Meta:
        db_table = 'attendance_statistics'
        verbose_name = 'Attendance Statistics'
        verbose_name_plural = 'Attendance Statistics'
        unique_together = ['institution', 'statistics_type', 'reference_id', 'reference_date']
        indexes = [
            models.Index(fields=['institution', 'statistics_type', 'reference_date']),
            models.Index(fields=['statistics_type']),
            models.Index(fields=['reference_date']),
            models.Index(fields=['dropout_risk_score']),
        ]

    def __str__(self):
        return f"{self.statistics_type.title()} - {self.reference_date}"

    def calculate_metrics(self):
        """Calculate attendance metrics"""
        if self.total_sessions == 0:
            self.attendance_rate = 0.0
            self.punctuality_rate = 0.0
        else:
            self.attendance_rate = (self.present_count / self.total_sessions) * 100
            self.punctuality_rate = ((self.present_count - self.late_count) / self.total_sessions) * 100
        
        # Calculate engagement score (combination of attendance and punctuality)
        self.engagement_score = (self.attendance_rate * 0.7 + self.punctuality_rate * 0.3)
        
        # Calculate risk scores (simplified logic)
        if self.attendance_rate < 70:
            self.dropout_risk_score = 80
        elif self.attendance_rate < 80:
            self.dropout_risk_score = 60
        elif self.attendance_rate < 90:
            self.dropout_risk_score = 40
        else:
            self.dropout_risk_score = 20
        
        # Performance risk based on attendance trend
        if self.attendance_trend < -5:
            self.performance_risk_score = 70
        elif self.attendance_trend < -2:
            self.performance_risk_score = 50
        elif self.attendance_trend > 2:
            self.performance_risk_score = 20
        else:
            self.performance_risk_score = 30
        
        self.save()


class AttendancePattern(TimeStampedModel, TenantModel):
    """
    Attendance pattern analysis for fraud detection
    """
    PATTERN_TYPES = [
        ('consistent', 'Consistent'),
        ('erratic', 'Erratic'),
        ('declining', 'Declining'),
        ('improving', 'Improving'),
        ('suspicious', 'Suspicious'),
        ('normal', 'Normal'),
    ]

    student = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='attendance_patterns',
        limit_choices_to={'role': 'student'}
    )
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name='attendance_patterns',
        null=True,
        blank=True
    )
    
    # Pattern Analysis
    pattern_type = models.CharField(max_length=20, choices=PATTERN_TYPES)
    confidence_score = models.FloatField(default=0.0)  # 0-100
    risk_level = models.CharField(
        max_length=10,
        choices=[
            ('low', 'Low'),
            ('medium', 'Medium'),
            ('high', 'High'),
            ('critical', 'Critical'),
        ],
        default='low'
    )
    
    # Pattern Metrics
    average_attendance_rate = models.FloatField(default=0.0)
    attendance_variance = models.FloatField(default=0.0)
    consistency_score = models.FloatField(default=0.0)
    
    # Anomaly Detection
    anomaly_count = models.IntegerField(default=0)
    last_anomaly_date = models.DateTimeField(null=True, blank=True)
    
    # Behavioral Patterns
    preferred_seating_position = models.CharField(max_length=50, blank=True)
    typical_arrival_time = models.TimeField(null=True, blank=True)
    device_consistency = models.FloatField(default=0.0)
    
    # Analysis Period
    analysis_start_date = models.DateField()
    analysis_end_date = models.DateField()
    total_sessions_analyzed = models.IntegerField(default=0)
    
    class Meta:
        db_table = 'attendance_pattern'
        verbose_name = 'Attendance Pattern'
        verbose_name_plural = 'Attendance Patterns'
        unique_together = ['institution', 'student', 'course', 'analysis_start_date', 'analysis_end_date']
        indexes = [
            models.Index(fields=['student', 'analysis_end_date']),
            models.Index(fields=['pattern_type']),
            models.Index(fields=['risk_level']),
            models.Index(fields=['confidence_score']),
        ]

    def __str__(self):
        return f"{self.student.get_full_name()} - {self.pattern_type}"


class AttendanceAlert(TimeStampedModel, AuditModel, TenantModel):
    """
    Attendance alerts and notifications
    """
    ALERT_TYPES = [
        ('low_attendance', 'Low Attendance'),
        ('absenteeism', 'Chronic Absenteeism'),
        ('suspicious_activity', 'Suspicious Activity'),
        ('pattern_anomaly', 'Pattern Anomaly'),
        ('dropout_risk', 'Dropout Risk'),
        ('performance_decline', 'Performance Decline'),
        ('proxy_detection', 'Proxy Detection'),
    ]

    SEVERITY_LEVELS = [
        ('info', 'Info'),
        ('warning', 'Warning'),
        ('critical', 'Critical'),
        ('urgent', 'Urgent'),
    ]

    alert_type = models.CharField(max_length=30, choices=ALERT_TYPES)
    severity = models.CharField(max_length=10, choices=SEVERITY_LEVELS)
    title = models.CharField(max_length=200)
    description = models.TextField()
    
    # Target
    student = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='attendance_alerts',
        null=True,
        blank=True,
        limit_choices_to={'role': 'student'}
    )
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name='attendance_alerts',
        null=True,
        blank=True
    )
    
    # Alert Data
    alert_data = models.JSONField(default=dict, blank=True)
    threshold_value = models.FloatField(null=True, blank=True)
    actual_value = models.FloatField(null=True, blank=True)
    
    # Status
    is_active = models.BooleanField(default=True)
    acknowledged = models.BooleanField(default=False)
    acknowledged_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='acknowledged_alerts'
    )
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    
    # Resolution
    resolved = models.BooleanField(default=False)
    resolved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='resolved_alerts'
    )
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolution_notes = models.TextField(blank=True)
    
    class Meta:
        db_table = 'attendance_alert'
        verbose_name = 'Attendance Alert'
        verbose_name_plural = 'Attendance Alerts'
        indexes = [
            models.Index(fields=['institution', 'is_active']),
            models.Index(fields=['alert_type']),
            models.Index(fields=['severity']),
            models.Index(fields=['student']),
            models.Index(fields=['acknowledged']),
            models.Index(fields=['resolved']),
        ]

    def __str__(self):
        return f"{self.title} - {self.severity}"


class AttendanceSettings(TimeStampedModel, TenantModel):
    """
    Institution-specific attendance settings
    """
    institution = models.OneToOneField(
        Institution,
        on_delete=models.CASCADE,
        related_name='attendance_settings'
    )
    
    # Default Settings
    default_session_duration = models.IntegerField(default=60)  # minutes
    default_grace_period = models.IntegerField(default=15)  # minutes
    default_geolocation_radius = models.FloatField(default=100.0)  # meters
    
    # Security Settings
    enable_geolocation_verification = models.BooleanField(default=True)
    enable_device_fingerprinting = models.BooleanField(default=True)
    enable_ip_verification = models.BooleanField(default=False)
    enable_biometric_verification = models.BooleanField(default=False)
    
    # Alert Thresholds
    low_attendance_threshold = models.FloatField(default=70.0)  # percentage
    chronic_absenteeism_threshold = models.IntegerField(default=3)  # consecutive absences
    suspicious_activity_threshold = models.FloatField(default=50.0)  # verification score
    
    # Auto-Actions
    auto_close_sessions = models.BooleanField(default=True)
    auto_generate_reports = models.BooleanField(default=True)
    auto_send_alerts = models.BooleanField(default=True)
    
    # Notification Settings
    notify_lecturers_absenteeism = models.BooleanField(default=True)
    notify_students_low_attendance = models.BooleanField(default=True)
    notify_admins_suspicious_activity = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'attendance_settings'
        verbose_name = 'Attendance Settings'
        verbose_name_plural = 'Attendance Settings'

    def __str__(self):
        return f"Attendance Settings for {self.institution.name}"
