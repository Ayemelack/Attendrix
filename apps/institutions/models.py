"""
Institution models for multi-tenant architecture
"""
from django.db import models
from django.core.validators import RegexValidator
from django.utils import timezone
from apps.core.models import TimeStampedModel, SoftDeleteModel, AuditModel
import uuid


class Institution(TimeStampedModel):
    """
    Multi-tenant institution model
    """
    INSTITUTION_TYPES = [
        ('university', 'University'),
        ('college', 'College'),
        ('high_school', 'High School'),
        ('elementary', 'Elementary School'),
        ('vocational', 'Vocational School'),
        ('training_center', 'Training Center'),
        ('corporate', 'Corporate Training'),
        ('other', 'Other'),
    ]

    SUBSCRIPTION_PLANS = [
        ('basic', 'Basic'),
        ('professional', 'Professional'),
        ('enterprise', 'Enterprise'),
        ('custom', 'Custom'),
    ]

    name = models.CharField(max_length=200, unique=True)
    code = models.CharField(
        max_length=20,
        unique=True,
        validators=[RegexValidator(r'^[A-Z0-9]+$', 'Only uppercase letters and numbers allowed')]
    )
    institution_type = models.CharField(max_length=20, choices=INSTITUTION_TYPES)
    subscription_plan = models.CharField(max_length=20, choices=SUBSCRIPTION_PLANS, default='basic')
    description = models.TextField(blank=True)
    
    # Contact Information
    address = models.TextField()
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    country = models.CharField(max_length=100)
    postal_code = models.CharField(max_length=20)
    phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField()
    website = models.URLField(blank=True)
    
    # Configuration
    timezone = models.CharField(max_length=50, default='UTC')
    currency = models.CharField(max_length=3, default='USD')
    academic_calendar_start = models.DateField()
    academic_calendar_end = models.DateField()
    
    # Limits and Quotas
    max_users = models.IntegerField(default=100)
    max_courses = models.IntegerField(default=50)
    max_storage_mb = models.IntegerField(default=1024)  # 1GB default
    
    # Features
    enable_geolocation = models.BooleanField(default=True)
    enable_device_fingerprinting = models.BooleanField(default=True)
    enable_predictive_analytics = models.BooleanField(default=False)
    enable_gamification = models.BooleanField(default=False)
    enable_api_access = models.BooleanField(default=False)
    
    # Status
    is_active = models.BooleanField(default=True)
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    is_trial = models.BooleanField(default=False)
    trial_ends_at = models.DateTimeField(null=True, blank=True)
    subscription_ends_at = models.DateTimeField(null=True, blank=True)
    
    # Settings
    default_attendance_threshold = models.IntegerField(default=75)  # Percentage
    late_arrival_grace_minutes = models.IntegerField(default=15)
    max_session_duration_minutes = models.IntegerField(default=120)
    auto_approve_leave_days = models.IntegerField(default=1)
    
    class Meta:
        db_table = 'institutions_institution'
        verbose_name = 'Institution'
        verbose_name_plural = 'Institutions'
        indexes = [
            models.Index(fields=['code']),
            models.Index(fields=['is_active', 'is_deleted']),
            models.Index(fields=['subscription_plan']),
            models.Index(fields=['academic_calendar_start', 'academic_calendar_end']),
        ]

    def __str__(self):
        return f"{self.name} ({self.code})"

    @property
    def is_subscription_active(self):
        """Check if institution subscription is active"""
        if self.is_trial and self.trial_ends_at:
            return timezone.now() <= self.trial_ends_at
        elif self.subscription_ends_at:
            return timezone.now() <= self.subscription_ends_at
        return True

    @property
    def days_until_subscription_ends(self):
        """Calculate days until subscription ends"""
        end_date = self.trial_ends_at if self.is_trial else self.subscription_ends_at
        if end_date:
            return (end_date - timezone.now()).days
        return None


class InstitutionDomain(TimeStampedModel):
    """
    Domain mapping for multi-tenant routing
    """
    institution = models.ForeignKey(
        Institution,
        on_delete=models.CASCADE,
        related_name='domains'
    )
    domain = models.CharField(max_length=255, unique=True)
    is_primary = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'institutions_domain'
        verbose_name = 'Institution Domain'
        verbose_name_plural = 'Institution Domains'
        indexes = [
            models.Index(fields=['domain']),
            models.Index(fields=['institution', 'is_primary']),
        ]

    def __str__(self):
        return f"{self.domain} -> {self.institution.name}"


class InstitutionSettings(TimeStampedModel):
    """
    Institution-specific settings and preferences
    """
    institution = models.OneToOneField(
        Institution,
        on_delete=models.CASCADE,
        related_name='settings'
    )
    
    # Email Settings
    email_notifications_enabled = models.BooleanField(default=True)
    email_from_name = models.CharField(max_length=100, default='Attendrix')
    email_from_address = models.EmailField(blank=True)
    email_reply_to = models.EmailField(blank=True)
    
    # SMS Settings
    sms_notifications_enabled = models.BooleanField(default=False)
    sms_provider = models.CharField(max_length=50, blank=True)
    sms_api_key = models.CharField(max_length=255, blank=True)
    
    # Attendance Settings
    attendance_auto_close_minutes = models.IntegerField(default=120)
    attendance_reminder_minutes = models.IntegerField(default=15)
    allow_late_marking = models.BooleanField(default=True)
    late_marking_cutoff_minutes = models.IntegerField(default=30)
    
    # Security Settings
    require_two_factor = models.BooleanField(default=False)
    session_timeout_minutes = models.IntegerField(default=60)
    max_login_attempts = models.IntegerField(default=5)
    lockout_duration_minutes = models.IntegerField(default=30)
    
    # Reporting Settings
    auto_generate_reports = models.BooleanField(default=True)
    report_delivery_time = models.TimeField(default='09:00:00')
    report_recipients = models.TextField(blank=True)  # Comma-separated emails
    
    # Integration Settings
    lms_integration_enabled = models.BooleanField(default=False)
    lms_provider = models.CharField(max_length=50, blank=True)
    lms_api_url = models.URLField(blank=True)
    lms_api_key = models.CharField(max_length=255, blank=True)
    
    # UI/UX Settings
    primary_color = models.CharField(max_length=7, default='#1e40af')  # Hex color
    secondary_color = models.CharField(max_length=7, default='#64748b')
    logo_url = models.URLField(blank=True)
    custom_css = models.TextField(blank=True)
    
    # Feature Toggles
    enable_student_dashboard = models.BooleanField(default=True)
    enable_parent_access = models.BooleanField(default=False)
    enable_mobile_app = models.BooleanField(default=False)
    enable_offline_mode = models.BooleanField(default=False)
    
    class Meta:
        db_table = 'institutions_settings'
        verbose_name = 'Institution Settings'
        verbose_name_plural = 'Institution Settings'

    def __str__(self):
        return f"Settings for {self.institution.name}"


class AcademicSession(TimeStampedModel):
    """
    Academic session/term management
    """
    institution = models.ForeignKey(
        Institution,
        on_delete=models.CASCADE,
        related_name='academic_sessions'
    )
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20)
    start_date = models.DateField()
    end_date = models.DateField()
    is_current = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    description = models.TextField(blank=True)
    
    class Meta:
        db_table = 'institutions_academic_session'
        verbose_name = 'Academic Session'
        verbose_name_plural = 'Academic Sessions'
        unique_together = ['institution', 'code']
        indexes = [
            models.Index(fields=['institution', 'is_current']),
            models.Index(fields=['start_date', 'end_date']),
        ]

    def __str__(self):
        return f"{self.institution.name} - {self.name}"

    def save(self, *args, **kwargs):
        # Ensure only one current session per institution
        if self.is_current:
            AcademicSession.objects.filter(
                institution=self.institution,
                is_current=True
            ).exclude(pk=self.pk).update(is_current=False)
        super().save(*args, **kwargs)


class HolidayCalendar(TimeStampedModel):
    """
    Holiday and break calendar management
    """
    institution = models.ForeignKey(
        Institution,
        on_delete=models.CASCADE,
        related_name='holidays'
    )
    name = models.CharField(max_length=100)
    date = models.DateField()
    holiday_type = models.CharField(
        max_length=20,
        choices=[
            ('public_holiday', 'Public Holiday'),
            ('institution_holiday', 'Institution Holiday'),
            ('break', 'Break'),
            ('exam_period', 'Exam Period'),
            ('other', 'Other'),
        ]
    )
    is_recurring = models.BooleanField(default=False)
    description = models.TextField(blank=True)
    affects_attendance = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'institutions_holiday_calendar'
        verbose_name = 'Holiday Calendar'
        verbose_name_plural = 'Holiday Calendars'
        unique_together = ['institution', 'date', 'name']
        indexes = [
            models.Index(fields=['institution', 'date']),
            models.Index(fields=['holiday_type']),
            models.Index(fields=['is_recurring']),
        ]

    def __str__(self):
        return f"{self.institution.name} - {self.name} ({self.date})"


class InstitutionStatistics(TimeStampedModel):
    """
    Institution usage statistics and metrics
    """
    institution = models.ForeignKey(
        Institution,
        on_delete=models.CASCADE,
        related_name='statistics'
    )
    date = models.DateField()
    
    # User Statistics
    total_users = models.IntegerField(default=0)
    active_users = models.IntegerField(default=0)
    new_users = models.IntegerField(default=0)
    
    # Attendance Statistics
    total_sessions = models.IntegerField(default=0)
    total_attendance_records = models.IntegerField(default=0)
    average_attendance_rate = models.FloatField(default=0.0)
    
    # Course Statistics
    total_courses = models.IntegerField(default=0)
    active_courses = models.IntegerField(default=0)
    
    # System Usage
    api_calls = models.IntegerField(default=0)
    storage_used_mb = models.FloatField(default=0.0)
    
    # Performance Metrics
    average_response_time_ms = models.FloatField(default=0.0)
    error_count = models.IntegerField(default=0)
    
    class Meta:
        db_table = 'institutions_statistics'
        verbose_name = 'Institution Statistics'
        verbose_name_plural = 'Institution Statistics'
        unique_together = ['institution', 'date']
        indexes = [
            models.Index(fields=['institution', 'date']),
            models.Index(fields=['date']),
        ]

    def __str__(self):
        return f"{self.institution.name} - {self.date}"
