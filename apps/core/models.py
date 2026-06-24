"""
Core models for Attendrix - Base models and shared functionality
"""
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.utils import timezone
from django.core.validators import RegexValidator
import uuid


class TimeStampedModel(models.Model):
    """
    Abstract base model with created_at and updated_at fields
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
        ordering = ['-created_at']


class SoftDeleteModel(TimeStampedModel):
    """
    Abstract model for soft delete functionality
    """
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        abstract = True

    def soft_delete(self):
        """Mark the record as deleted"""
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save()

    def restore(self):
        """Restore the soft deleted record"""
        self.is_deleted = False
        self.deleted_at = None
        self.save()


class AuditModel(SoftDeleteModel):
    """
    Abstract model for audit trail functionality
    """
    created_by = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(class)s_created'
    )
    updated_by = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(class)s_updated'
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        abstract = True


class TenantModel:
    """
    Abstract model for multi-tenant functionality
    """
    institution = models.ForeignKey(
        'institutions.Institution',
        on_delete=models.CASCADE,
        related_name='%(class)s_set'
    )

    class Meta:
        abstract = True


class SystemConfiguration(TimeStampedModel):
    """
    System-wide configuration settings
    """
    key = models.CharField(max_length=100, unique=True)
    value = models.TextField()
    description = models.TextField(blank=True)
    is_public = models.BooleanField(default=False)  # Whether this config can be exposed in API

    class Meta:
        db_table = 'core_system_configuration'
        verbose_name = 'System Configuration'
        verbose_name_plural = 'System Configurations'

    def __str__(self):
        return f"{self.key}: {self.value}"


class ActivityLog(TimeStampedModel):
    """
    Comprehensive activity logging for audit and security
    """
    ACTION_TYPES = [
        ('login', 'Login'),
        ('logout', 'Logout'),
        ('create', 'Create'),
        ('update', 'Update'),
        ('delete', 'Delete'),
        ('view', 'View'),
        ('export', 'Export'),
        ('import', 'Import'),
        ('attendance_mark', 'Attendance Mark'),
        ('attendance_session_start', 'Attendance Session Start'),
        ('attendance_session_end', 'Attendance Session End'),
        ('leave_request', 'Leave Request'),
        ('leave_approve', 'Leave Approve'),
        ('leave_reject', 'Leave Reject'),
        ('schedule_create', 'Schedule Create'),
        ('schedule_update', 'Schedule Update'),
        ('alert_trigger', 'Alert Trigger'),
        ('survey_submit', 'Survey Submit'),
        ('message_send', 'Message Send'),
        ('file_upload', 'File Upload'),
        ('security_violation', 'Security Violation'),
        ('system_error', 'System Error'),
    ]

    user = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='activity_logs'
    )
    institution = models.ForeignKey(
        'institutions.Institution',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='activity_logs'
    )
    action_type = models.CharField(max_length=50, choices=ACTION_TYPES)
    action_description = models.TextField()
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    device_fingerprint = models.CharField(max_length=255, blank=True)
    geolocation = models.JSONField(null=True, blank=True)  # {lat, lng, city, country}
    metadata = models.JSONField(default=dict, blank=True)  # Additional context
    severity = models.CharField(
        max_length=20,
        choices=[
            ('low', 'Low'),
            ('medium', 'Medium'),
            ('high', 'High'),
            ('critical', 'Critical'),
        ],
        default='low'
    )

    class Meta:
        db_table = 'core_activity_log'
        verbose_name = 'Activity Log'
        verbose_name_plural = 'Activity Logs'
        indexes = [
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['institution', 'created_at']),
            models.Index(fields=['action_type', 'created_at']),
            models.Index(fields=['severity', 'created_at']),
            models.Index(fields=['ip_address']),
        ]

    def __str__(self):
        return f"{self.user} - {self.action_type} - {self.created_at}"


class SecurityLog(TimeStampedModel):
    """
    Security-specific logging for threat detection and compliance
    """
    EVENT_TYPES = [
        ('failed_login', 'Failed Login'),
        ('successful_login', 'Successful Login'),
        ('password_change', 'Password Change'),
        ('password_reset', 'Password Reset'),
        ('account_locked', 'Account Locked'),
        ('account_unlocked', 'Account Unlocked'),
        ('suspicious_activity', 'Suspicious Activity'),
        ('brute_force_attempt', 'Brute Force Attempt'),
        ('unauthorized_access', 'Unauthorized Access'),
        ('data_breach_attempt', 'Data Breach Attempt'),
        ('malicious_request', 'Malicious Request'),
        ('session_hijack', 'Session Hijack'),
        ('device_anomaly', 'Device Anomaly'),
        ('geolocation_anomaly', 'Geolocation Anomaly'),
        ('rate_limit_exceeded', 'Rate Limit Exceeded'),
    ]

    user = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='security_logs'
    )
    institution = models.ForeignKey(
        'institutions.Institution',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='security_logs'
    )
    event_type = models.CharField(max_length=50, choices=EVENT_TYPES)
    event_description = models.TextField()
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    device_fingerprint = models.CharField(max_length=255, blank=True)
    geolocation = models.JSONField(null=True, blank=True)
    risk_score = models.IntegerField(default=0)  # 0-100 risk score
    is_blocked = models.BooleanField(default=False)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = 'core_security_log'
        verbose_name = 'Security Log'
        verbose_name_plural = 'Security Logs'
        indexes = [
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['institution', 'created_at']),
            models.Index(fields=['event_type', 'created_at']),
            models.Index(fields=['risk_score']),
            models.Index(fields=['ip_address']),
            models.Index(fields=['is_blocked']),
        ]

    def __str__(self):
        return f"{self.user} - {self.event_type} - Risk: {self.risk_score}"


class DeviceFingerprint(TimeStampedModel):
    """
    Device fingerprinting for security and session management
    """
    user = models.ForeignKey(
        'users.User',
        on_delete=models.CASCADE,
        related_name='device_fingerprints'
    )
    fingerprint = models.CharField(max_length=255, unique=True)
    device_type = models.CharField(max_length=50)  # mobile, tablet, desktop
    operating_system = models.CharField(max_length=100)
    browser = models.CharField(max_length=100)
    browser_version = models.CharField(max_length=50)
    screen_resolution = models.CharField(max_length=20)
    is_trusted = models.BooleanField(default=False)
    last_seen = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'core_device_fingerprint'
        verbose_name = 'Device Fingerprint'
        verbose_name_plural = 'Device Fingerprints'
        unique_together = ['user', 'fingerprint']
        indexes = [
            models.Index(fields=['user', 'last_seen']),
            models.Index(fields=['fingerprint']),
            models.Index(fields=['is_trusted']),
        ]

    def __str__(self):
        return f"{self.user} - {self.device_type} - {self.browser}"


class APIKey(TimeStampedModel):
    """
    API key management for external integrations
    """
    user = models.ForeignKey(
        'users.User',
        on_delete=models.CASCADE,
        related_name='api_keys'
    )
    institution = models.ForeignKey(
        'institutions.Institution',
        on_delete=models.CASCADE,
        related_name='api_keys'
    )
    name = models.CharField(max_length=100)
    key = models.CharField(max_length=255, unique=True)
    is_active = models.BooleanField(default=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    last_used = models.DateTimeField(null=True, blank=True)
    usage_count = models.IntegerField(default=0)
    permissions = models.JSONField(default=list)  # List of allowed permissions
    rate_limit = models.IntegerField(default=1000)  # Requests per hour

    class Meta:
        db_table = 'core_api_key'
        verbose_name = 'API Key'
        verbose_name_plural = 'API Keys'
        indexes = [
            models.Index(fields=['key']),
            models.Index(fields=['user', 'is_active']),
            models.Index(fields=['institution', 'is_active']),
        ]

    def __str__(self):
        return f"{self.name} - {self.user}"


class RefreshToken(TimeStampedModel):
    """
    JWT refresh token management
    """
    user = models.ForeignKey(
        'users.User',
        on_delete=models.CASCADE,
        related_name='refresh_tokens'
    )
    token = models.CharField(max_length=255, unique=True)
    is_active = models.BooleanField(default=True)
    expires_at = models.DateTimeField()
    device_fingerprint = models.CharField(max_length=255, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        db_table = 'core_refresh_token'
        verbose_name = 'Refresh Token'
        verbose_name_plural = 'Refresh Tokens'
        indexes = [
            models.Index(fields=['token']),
            models.Index(fields=['user', 'is_active']),
            models.Index(fields=['expires_at']),
        ]

    def __str__(self):
        return f"{self.user} - {self.created_at}"


class SystemHealth(TimeStampedModel):
    """
    System health monitoring and metrics
    """
    METRIC_TYPES = [
        ('database', 'Database'),
        ('cache', 'Cache'),
        ('queue', 'Queue'),
        ('storage', 'Storage'),
        ('memory', 'Memory'),
        ('cpu', 'CPU'),
        ('network', 'Network'),
    ]

    metric_type = models.CharField(max_length=50, choices=METRIC_TYPES)
    metric_name = models.CharField(max_length=100)
    metric_value = models.FloatField()
    metric_unit = models.CharField(max_length=20, blank=True)
    status = models.CharField(
        max_length=20,
        choices=[
            ('healthy', 'Healthy'),
            ('warning', 'Warning'),
            ('critical', 'Critical'),
            ('unknown', 'Unknown'),
        ],
        default='unknown'
    )
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = 'core_system_health'
        verbose_name = 'System Health'
        verbose_name_plural = 'System Health'
        indexes = [
            models.Index(fields=['metric_type', 'created_at']),
            models.Index(fields=['status', 'created_at']),
        ]

    def __str__(self):
        return f"{self.metric_type} - {self.metric_name}: {self.metric_value} {self.metric_unit}"
