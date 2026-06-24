"""
Authentication models for Attendrix security system
"""
from django.db import models
from django.utils import timezone
from apps.core.models import TimeStampedModel, AuditModel
from apps.users.models import User
from apps.institutions.models import Institution
import uuid


class LoginAttempt(TimeStampedModel):
    """
    Track login attempts for security monitoring
    """
    ATTEMPT_TYPES = [
        ('login', 'Login'),
        ('logout', 'Logout'),
        ('password_reset', 'Password Reset'),
        ('password_change', 'Password Change'),
        ('two_factor', 'Two Factor'),
    ]
    
    STATUS_CHOICES = [
        ('success', 'Success'),
        ('failed', 'Failed'),
        ('blocked', 'Blocked'),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='login_attempts'
    )
    institution = models.ForeignKey(
        Institution,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='login_attempts'
    )
    
    attempt_type = models.CharField(max_length=20, choices=ATTEMPT_TYPES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    
    # Request Information
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField(blank=True)
    device_fingerprint = models.CharField(max_length=255, blank=True)
    geolocation = models.JSONField(null=True, blank=True)
    
    # Authentication Details
    username_or_email = models.CharField(max_length=255, blank=True)
    failure_reason = models.CharField(max_length=100, blank=True)
    
    # Security
    risk_score = models.IntegerField(default=0)  # 0-100
    is_suspicious = models.BooleanField(default=False)
    
    class Meta:
        db_table = 'authentication_login_attempt'
        verbose_name = 'Login Attempt'
        verbose_name_plural = 'Login Attempts'
        indexes = [
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['institution', 'created_at']),
            models.Index(fields=['ip_address']),
            models.Index(fields=['status']),
            models.Index(fields=['is_suspicious']),
            models.Index(fields=['risk_score']),
        ]

    def __str__(self):
        return f"{self.user} - {self.attempt_type} - {self.status}"


class SecurityToken(TimeStampedModel):
    """
    Security tokens for various authentication purposes
    """
    TOKEN_TYPES = [
        ('password_reset', 'Password Reset'),
        ('email_verification', 'Email Verification'),
        ('two_factor', 'Two Factor'),
        ('api_access', 'API Access'),
        ('session_recovery', 'Session Recovery'),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='security_tokens'
    )
    token_type = models.CharField(max_length=20, choices=TOKEN_TYPES)
    token = models.CharField(max_length=255, unique=True)
    
    # Validity
    is_used = models.BooleanField(default=False)
    used_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField()
    
    # Context
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    
    class Meta:
        db_table = 'authentication_security_token'
        verbose_name = 'Security Token'
        verbose_name_plural = 'Security Tokens'
        indexes = [
            models.Index(fields=['user', 'token_type']),
            models.Index(fields=['token']),
            models.Index(fields=['expires_at']),
            models.Index(fields=['is_used']),
        ]

    def __str__(self):
        return f"{self.user.email} - {self.token_type}"

    @property
    def is_expired(self):
        """Check if token is expired"""
        return timezone.now() > self.expires_at

    @property
    def is_valid(self):
        """Check if token is valid and not used"""
        return not self.is_used and not self.is_expired


class TwoFactorDevice(TimeStampedModel):
    """
    Two-factor authentication devices
    """
    DEVICE_TYPES = [
        ('totp', 'Time-based OTP'),
        ('sms', 'SMS'),
        ('email', 'Email'),
        ('backup_code', 'Backup Code'),
        ('hardware', 'Hardware Token'),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='two_factor_devices'
    )
    device_type = models.CharField(max_length=20, choices=DEVICE_TYPES)
    device_name = models.CharField(max_length=100)
    
    # Device Details
    phone_number = models.CharField(max_length=20, blank=True)
    email_address = models.EmailField(blank=True)
    secret_key = models.CharField(max_length=255, blank=True)
    backup_codes = models.JSONField(default=list, blank=True)
    
    # Status
    is_active = models.BooleanField(default=True)
    is_verified = models.BooleanField(default=False)
    last_used = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'authentication_two_factor_device'
        verbose_name = 'Two Factor Device'
        verbose_name_plural = 'Two Factor Devices'
        indexes = [
            models.Index(fields=['user', 'is_active']),
            models.Index(fields=['device_type']),
        ]

    def __str__(self):
        return f"{self.user.email} - {self.device_name}"


class SecurityQuestion(TimeStampedModel):
    """
    Security questions for account recovery
    """
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='security_questions'
    )
    question = models.CharField(max_length=255)
    answer_hash = models.CharField(max_length=255)  # Hashed answer
    is_active = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'authentication_security_question'
        verbose_name = 'Security Question'
        verbose_name_plural = 'Security Questions'
        indexes = [
            models.Index(fields=['user', 'is_active']),
        ]

    def __str__(self):
        return f"{self.user.email} - {self.question[:50]}..."


class Permission(TimeStampedModel):
    """
    Custom permissions for role-based access control
    """
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    module = models.CharField(max_length=50)  # Module name
    action = models.CharField(max_length=50)  # create, read, update, delete, etc.
    
    # Role-based assignment
    super_admin = models.BooleanField(default=False)
    institution_admin = models.BooleanField(default=False)
    lecturer = models.BooleanField(default=False)
    student = models.BooleanField(default=False)
    employee = models.BooleanField(default=False)
    
    class Meta:
        db_table = 'authentication_permission'
        verbose_name = 'Permission'
        verbose_name_plural = 'Permissions'
        indexes = [
            models.Index(fields=['code']),
            models.Index(fields=['module', 'action']),
        ]

    def __str__(self):
        return f"{self.name} ({self.code})"


class RolePermission(TimeStampedModel):
    """
    Role-based permission assignments
    """
    role = models.CharField(
        max_length=20,
        choices=User.ROLE_CHOICES
    )
    permission = models.ForeignKey(
        Permission,
        on_delete=models.CASCADE,
        related_name='role_permissions'
    )
    institution = models.ForeignKey(
        Institution,
        on_delete=models.CASCADE,
        related_name='role_permissions',
        null=True,
        blank=True  # Null for global permissions
    )
    is_active = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'authentication_role_permission'
        verbose_name = 'Role Permission'
        verbose_name_plural = 'Role Permissions'
        unique_together = ['role', 'permission', 'institution']
        indexes = [
            models.Index(fields=['role', 'is_active']),
            models.Index(fields=['permission', 'is_active']),
            models.Index(fields=['institution', 'is_active']),
        ]

    def __str__(self):
        return f"{self.role} - {self.permission.name}"


class UserSession(TimeStampedModel):
    """
    User session tracking for security
    """
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='auth_sessions'
    )
    session_key = models.CharField(max_length=255, unique=True)
    
    # Session Details
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField(blank=True)
    device_fingerprint = models.CharField(max_length=255, blank=True)
    geolocation = models.JSONField(null=True, blank=True)
    
    # Status
    is_active = models.BooleanField(default=True)
    last_activity = models.DateTimeField(auto_now=True)
    expires_at = models.DateTimeField()
    
    # Security
    is_suspicious = models.BooleanField(default=False)
    security_flags = models.JSONField(default=list, blank=True)
    
    class Meta:
        db_table = 'authentication_user_session'
        verbose_name = 'User Session'
        verbose_name_plural = 'User Sessions'
        indexes = [
            models.Index(fields=['user', 'is_active']),
            models.Index(fields=['session_key']),
            models.Index(fields=['ip_address']),
            models.Index(fields=['expires_at']),
            models.Index(fields=['is_suspicious']),
        ]

    def __str__(self):
        return f"{self.user.email} - {self.ip_address}"

    @property
    def is_expired(self):
        """Check if session is expired"""
        return timezone.now() > self.expires_at

    def extend_session(self, hours=24):
        """Extend session expiration"""
        self.expires_at = timezone.now() + timezone.timedelta(hours=hours)
        self.save(update_fields=['expires_at'])


class SecurityEvent(TimeStampedModel):
    """
    Security events for monitoring and alerting
    """
    EVENT_TYPES = [
        ('brute_force', 'Brute Force Attack'),
        ('suspicious_login', 'Suspicious Login'),
        ('account_lockout', 'Account Lockout'),
        ('privilege_escalation', 'Privilege Escalation'),
        ('data_access_violation', 'Data Access Violation'),
        ('unauthorized_api', 'Unauthorized API Access'),
        ('session_hijack', 'Session Hijack Attempt'),
        ('malicious_request', 'Malicious Request'),
        ('rate_limit_exceeded', 'Rate Limit Exceeded'),
        ('anomaly_detected', 'Anomaly Detected'),
    ]

    SEVERITY_LEVELS = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='security_events'
    )
    institution = models.ForeignKey(
        Institution,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='security_events'
    )
    
    event_type = models.CharField(max_length=50, choices=EVENT_TYPES)
    severity = models.CharField(max_length=20, choices=SEVERITY_LEVELS)
    description = models.TextField()
    
    # Event Details
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    device_fingerprint = models.CharField(max_length=255, blank=True)
    geolocation = models.JSONField(null=True, blank=True)
    
    # Risk Assessment
    risk_score = models.IntegerField(default=0)  # 0-100
    confidence_score = models.IntegerField(default=0)  # 0-100
    
    # Response
    is_blocked = models.BooleanField(default=False)
    block_reason = models.CharField(max_length=255, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='resolved_security_events'
    )
    
    # Additional Data
    metadata = models.JSONField(default=dict, blank=True)
    
    class Meta:
        db_table = 'authentication_security_event'
        verbose_name = 'Security Event'
        verbose_name_plural = 'Security Events'
        indexes = [
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['institution', 'created_at']),
            models.Index(fields=['event_type']),
            models.Index(fields=['severity']),
            models.Index(fields=['risk_score']),
            models.Index(fields=['is_blocked']),
        ]

    def __str__(self):
        return f"{self.event_type} - {self.severity} - {self.user}"
