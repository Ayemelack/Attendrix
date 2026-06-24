"""
User models for Attendrix - Custom user model with role-based access control
"""
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.core.validators import RegexValidator, EmailValidator
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from apps.core.models import TimeStampedModel, SoftDeleteModel, AuditModel, TenantModel
from apps.institutions.models import Institution
import uuid


class UserManager(BaseUserManager):
    """
    Custom user manager for User model
    """
    def create_user(self, email, password=None, **extra_fields):
        """Create and save a regular user"""
        if not email:
            raise ValueError('Users must have an email address')
        
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        """Create and save a superuser"""
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('role', 'super_admin')
        extra_fields.setdefault('is_active', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin, TimeStampedModel):
    """
    Custom user model with role-based access control
    """
    ROLE_CHOICES = [
        ('super_admin', 'Super Admin'),
        ('institution_admin', 'Institution Admin'),
        ('lecturer', 'Lecturer'),
        ('student', 'Student'),
        ('employee', 'Employee'),
    ]

    GENDER_CHOICES = [
        ('male', 'Male'),
        ('female', 'Female'),
        ('other', 'Other'),
        ('prefer_not_to_say', 'Prefer not to say'),
    ]

    # Basic Information
    email = models.EmailField(unique=True, validators=[EmailValidator()])
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    
    # Institutional Information
    institution = models.ForeignKey(
        Institution,
        on_delete=models.CASCADE,
        related_name='users',
        null=True,
        blank=True  # Null for super admins
    )
    
    # Personal Information
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=20, choices=GENDER_CHOICES, blank=True)
    phone = models.CharField(
        max_length=20,
        blank=True,
        validators=[RegexValidator(r'^\+?1?\d{9,15}$', 'Enter a valid phone number')]
    )
    address = models.TextField(blank=True)
    
    # Academic/Professional Information
    employee_id = models.CharField(max_length=50, blank=True, unique=True)
    student_id = models.CharField(max_length=50, blank=True, unique=True)
    department = models.ForeignKey(
        'departments.Department',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='users'
    )
    designation = models.CharField(max_length=100, blank=True)
    specialization = models.CharField(max_length=200, blank=True)
    
    # System Information
    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    is_verified = models.BooleanField(default=False)
    last_login = models.DateTimeField(null=True, blank=True)
    last_active = models.DateTimeField(null=True, blank=True)
    
    # Security
    password_changed_at = models.DateTimeField(null=True, blank=True)
    failed_login_attempts = models.IntegerField(default=0)
    locked_until = models.DateTimeField(null=True, blank=True)
    two_factor_enabled = models.BooleanField(default=False)
    two_factor_secret = models.CharField(max_length=255, blank=True)
    
    # Preferences
    timezone = models.CharField(max_length=50, default='UTC')
    language = models.CharField(max_length=10, default='en')
    email_notifications = models.BooleanField(default=True)
    sms_notifications = models.BooleanField(default=False)
    
    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name', 'role']

    class Meta:
        db_table = 'users_user'
        verbose_name = 'User'
        verbose_name_plural = 'Users'
        indexes = [
            models.Index(fields=['email']),
            models.Index(fields=['institution', 'role']),
            models.Index(fields=['role', 'is_active']),
            models.Index(fields=['employee_id']),
            models.Index(fields=['student_id']),
            models.Index(fields=['last_active']),
        ]

    def __str__(self):
        return f"{self.get_full_name()} ({self.email})"

    @property
    def get_full_name(self):
        """Return user's full name"""
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def get_short_name(self):
        """Return user's short name"""
        return self.first_name

    def email_user(self, subject, message, from_email=None, **kwargs):
        """Send email to user"""
        send_mail(
            subject,
            message,
            from_email or settings.DEFAULT_FROM_EMAIL,
            [self.email],
            **kwargs
        )

    def is_institution_admin(self):
        """Check if user is institution admin"""
        return self.role == 'institution_admin'

    def is_lecturer(self):
        """Check if user is lecturer"""
        return self.role == 'lecturer'

    def is_student(self):
        """Check if user is student"""
        return self.role == 'student'

    def is_employee(self):
        """Check if user is employee"""
        return self.role == 'employee'

    def is_super_admin(self):
        """Check if user is super admin"""
        return self.role == 'super_admin'

    @property
    def is_account_locked(self):
        """Check if account is locked"""
        return self.locked_until and timezone.now() < self.locked_until

    def lock_account(self, minutes=30):
        """Lock user account"""
        self.locked_until = timezone.now() + timezone.timedelta(minutes=minutes)
        self.save()

    def unlock_account(self):
        """Unlock user account"""
        self.locked_until = None
        self.failed_login_attempts = 0
        self.save()

    def increment_failed_login(self):
        """Increment failed login attempts"""
        self.failed_login_attempts += 1
        if self.failed_login_attempts >= settings.MAX_LOGIN_ATTEMPTS:
            self.lock_account()
        self.save()

    def reset_failed_login(self):
        """Reset failed login attempts"""
        self.failed_login_attempts = 0
        self.save()

    def update_last_active(self):
        """Update last active timestamp"""
        self.last_active = timezone.now()
        self.save(update_fields=['last_active'])


class UserProfile(TimeStampedModel, TenantModel):
    """
    Extended user profile information
    """
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='profile'
    )
    
    # Personal Details
    bio = models.TextField(blank=True)
    profile_picture = models.ImageField(upload_to='profile_pictures/', blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    place_of_birth = models.CharField(max_length=100, blank=True)
    nationality = models.CharField(max_length=100, blank=True)
    
    # Contact Information
    emergency_contact_name = models.CharField(max_length=100, blank=True)
    emergency_contact_phone = models.CharField(max_length=20, blank=True)
    emergency_contact_relationship = models.CharField(max_length=50, blank=True)
    
    # Academic Information (for students)
    admission_date = models.DateField(null=True, blank=True)
    graduation_date = models.DateField(null=True, blank=True)
    gpa = models.FloatField(null=True, blank=True)
    academic_level = models.CharField(max_length=50, blank=True)
    
    # Professional Information (for employees)
    hire_date = models.DateField(null=True, blank=True)
    employment_type = models.CharField(
        max_length=20,
        choices=[
            ('full_time', 'Full Time'),
            ('part_time', 'Part Time'),
            ('contract', 'Contract'),
            ('intern', 'Intern'),
        ],
        blank=True
    )
    salary = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    # Social Media
    linkedin_url = models.URLField(blank=True)
    twitter_url = models.URLField(blank=True)
    website_url = models.URLField(blank=True)
    
    # Preferences
    theme = models.CharField(
        max_length=20,
        choices=[
            ('light', 'Light'),
            ('dark', 'Dark'),
            ('auto', 'Auto'),
        ],
        default='light'
    )
    dashboard_layout = models.JSONField(default=dict, blank=True)
    
    class Meta:
        db_table = 'users_user_profile'
        verbose_name = 'User Profile'
        verbose_name_plural = 'User Profiles'

    def __str__(self):
        return f"Profile of {self.user.get_full_name()}"


class UserSession(TimeStampedModel):
    """
    User session tracking for security and analytics
    """
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='sessions'
    )
    session_key = models.CharField(max_length=255, unique=True)
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField(blank=True)
    device_fingerprint = models.CharField(max_length=255, blank=True)
    geolocation = models.JSONField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    last_activity = models.DateTimeField(auto_now=True)
    expires_at = models.DateTimeField()
    
    class Meta:
        db_table = 'users_user_session'
        verbose_name = 'User Session'
        verbose_name_plural = 'User Sessions'
        indexes = [
            models.Index(fields=['user', 'is_active']),
            models.Index(fields=['session_key']),
            models.Index(fields=['ip_address']),
            models.Index(fields=['expires_at']),
        ]

    def __str__(self):
        return f"Session for {self.user.email} - {self.ip_address}"


class UserPermission(TimeStampedModel):
    """
    Custom user permissions beyond Django's built-in permissions
    """
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='custom_permissions'
    )
    institution = models.ForeignKey(
        Institution,
        on_delete=models.CASCADE,
        related_name='user_permissions'
    )
    permission = models.CharField(max_length=100)
    granted_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='granted_permissions'
    )
    granted_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'users_user_permission'
        verbose_name = 'User Permission'
        verbose_name_plural = 'User Permissions'
        unique_together = ['user', 'institution', 'permission']
        indexes = [
            models.Index(fields=['user', 'is_active']),
            models.Index(fields=['institution', 'permission']),
        ]

    def __str__(self):
        return f"{self.user.email} - {self.permission}"


class UserActivityLog(TimeStampedModel):
    """
    Detailed user activity logging
    """
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='activity_logs'
    )
    institution = models.ForeignKey(
        Institution,
        on_delete=models.CASCADE,
        related_name='user_activity_logs'
    )
    activity_type = models.CharField(max_length=100)
    description = models.TextField()
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    device_fingerprint = models.CharField(max_length=255, blank=True)
    geolocation = models.JSONField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    
    class Meta:
        db_table = 'users_user_activity_log'
        verbose_name = 'User Activity Log'
        verbose_name_plural = 'User Activity Logs'
        indexes = [
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['institution', 'created_at']),
            models.Index(fields=['activity_type']),
        ]

    def __str__(self):
        return f"{self.user.email} - {self.activity_type}"


class UserDevice(TimeStampedModel):
    """
    User device tracking for security
    """
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='devices'
    )
    device_name = models.CharField(max_length=100)
    device_type = models.CharField(max_length=50)  # mobile, tablet, desktop
    operating_system = models.CharField(max_length=100)
    browser = models.CharField(max_length=100)
    browser_version = models.CharField(max_length=50)
    fingerprint = models.CharField(max_length=255, unique=True)
    is_trusted = models.BooleanField(default=False)
    last_seen = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'users_user_device'
        verbose_name = 'User Device'
        verbose_name_plural = 'User Devices'
        unique_together = ['user', 'fingerprint']
        indexes = [
            models.Index(fields=['user', 'is_trusted']),
            models.Index(fields=['fingerprint']),
            models.Index(fields=['last_seen']),
        ]

    def __str__(self):
        return f"{self.user.email} - {self.device_name}"
