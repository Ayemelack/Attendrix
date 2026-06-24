"""
Department models for institutional organization
"""
from django.db import models
from django.core.validators import RegexValidator
from django.utils import timezone
from apps.core.models import TimeStampedModel, SoftDeleteModel, AuditModel, TenantModel
from apps.institutions.models import Institution
from apps.users.models import User
import uuid


class Department(TimeStampedModel, SoftDeleteModel, AuditModel, TenantModel):
    """
    Department model for institutional organization
    """
    DEPARTMENT_TYPES = [
        ('academic', 'Academic'),
        ('administrative', 'Administrative'),
        ('support', 'Support'),
        ('research', 'Research'),
        ('technical', 'Technical'),
        ('other', 'Other'),
    ]

    name = models.CharField(max_length=200)
    code = models.CharField(
        max_length=20,
        validators=[RegexValidator(r'^[A-Z0-9]+$', 'Only uppercase letters and numbers allowed')]
    )
    department_type = models.CharField(max_length=20, choices=DEPARTMENT_TYPES)
    description = models.TextField(blank=True)
    
    # Hierarchy
    parent_department = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sub_departments'
    )
    level = models.IntegerField(default=0)  # 0 for root departments
    
    # Contact Information
    office_location = models.CharField(max_length=200, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    
    # Leadership
    head_of_department = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='headed_departments',
        limit_choices_to={'role': 'lecturer'}
    )
    deputy_head = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='deputy_headed_departments',
        limit_choices_to={'role': 'lecturer'}
    )
    
    # Capacity and Resources
    max_students = models.IntegerField(default=100)
    max_lecturers = models.IntegerField(default=20)
    current_students = models.IntegerField(default=0)
    current_lecturers = models.IntegerField(default=0)
    
    # Status
    is_active = models.BooleanField(default=True)
    established_date = models.DateField(null=True, blank=True)
    
    class Meta:
        db_table = 'departments_department'
        verbose_name = 'Department'
        verbose_name_plural = 'Departments'
        unique_together = ['institution', 'code']
        indexes = [
            models.Index(fields=['institution', 'code']),
            models.Index(fields=['parent_department']),
            models.Index(fields=['department_type']),
            models.Index(fields=['head_of_department']),
            models.Index(fields=['level']),
        ]

    def __str__(self):
        return f"{self.name} ({self.code})"

    def save(self, *args, **kwargs):
        # Set level based on parent
        if self.parent_department:
            self.level = self.parent_department.level + 1
        else:
            self.level = 0
        super().save(*args, **kwargs)

    @property
    def has_capacity_for_students(self):
        """Check if department has capacity for more students"""
        return self.current_students < self.max_students

    @property
    def has_capacity_for_lecturers(self):
        """Check if department has capacity for more lecturers"""
        return self.current_lecturers < self.max_lecturers

    @property
    def student_capacity_percentage(self):
        """Calculate student capacity percentage"""
        if self.max_students == 0:
            return 0
        return (self.current_students / self.max_students) * 100

    @property
    def lecturer_capacity_percentage(self):
        """Calculate lecturer capacity percentage"""
        if self.max_lecturers == 0:
            return 0
        return (self.current_lecturers / self.max_lecturers) * 100


class DepartmentMembership(TimeStampedModel, AuditModel, TenantModel):
    """
    Department membership for users
    """
    ROLE_CHOICES = [
        ('head', 'Head of Department'),
        ('deputy_head', 'Deputy Head'),
        ('lecturer', 'Lecturer'),
        ('student', 'Student'),
        ('employee', 'Employee'),
        ('assistant', 'Assistant'),
        ('other', 'Other'),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='department_memberships'
    )
    department = models.ForeignKey(
        Department,
        on_delete=models.CASCADE,
        related_name='memberships'
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    title = models.CharField(max_length=100, blank=True)
    join_date = models.DateField(default=timezone.now)
    leave_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'departments_department_membership'
        verbose_name = 'Department Membership'
        verbose_name_plural = 'Department Memberships'
        unique_together = ['user', 'department']
        indexes = [
            models.Index(fields=['user', 'is_active']),
            models.Index(fields=['department', 'role', 'is_active']),
            models.Index(fields=['join_date']),
        ]

    def __str__(self):
        return f"{self.user.get_full_name()} - {self.department.name}"


class DepartmentSettings(TimeStampedModel, TenantModel):
    """
    Department-specific settings
    """
    department = models.OneToOneField(
        Department,
        on_delete=models.CASCADE,
        related_name='settings'
    )
    
    # Attendance Settings
    attendance_threshold = models.IntegerField(default=75)  # Percentage
    auto_mark_absent_minutes = models.IntegerField(default=30)
    allow_late_marking = models.BooleanField(default=True)
    late_marking_cutoff_minutes = models.IntegerField(default=60)
    
    # Leave Settings
    max_leave_days_per_semester = models.IntegerField(default=7)
    require_medical_certificate_days = models.IntegerField(default=3)
    auto_approve_leave_days = models.IntegerField(default=1)
    
    # Grading Settings
    passing_grade = models.FloatField(default=50.0)
    maximum_grade = models.FloatField(default=100.0)
    grade_scale = models.JSONField(default=dict)  # Custom grade scale
    
    # Notification Settings
    enable_attendance_alerts = models.BooleanField(default=True)
    enable_grade_alerts = models.BooleanField(default=True)
    enable_deadline_alerts = models.BooleanField(default=True)
    
    # Reporting Settings
    auto_generate_reports = models.BooleanField(default=True)
    report_frequency = models.CharField(
        max_length=20,
        choices=[
            ('daily', 'Daily'),
            ('weekly', 'Weekly'),
            ('monthly', 'Monthly'),
            ('semester', 'Semester'),
        ],
        default='monthly'
    )
    
    class Meta:
        db_table = 'departments_department_settings'
        verbose_name = 'Department Settings'
        verbose_name_plural = 'Department Settings'

    def __str__(self):
        return f"Settings for {self.department.name}"


class DepartmentResource(TimeStampedModel, SoftDeleteModel, AuditModel, TenantModel):
    """
    Department resources and facilities
    """
    RESOURCE_TYPES = [
        ('classroom', 'Classroom'),
        ('laboratory', 'Laboratory'),
        ('library', 'Library'),
        ('computer_lab', 'Computer Lab'),
        ('conference_room', 'Conference Room'),
        ('office', 'Office'),
        ('equipment', 'Equipment'),
        ('other', 'Other'),
    ]

    name = models.CharField(max_length=200)
    resource_type = models.CharField(max_length=20, choices=RESOURCE_TYPES)
    description = models.TextField(blank=True)
    location = models.CharField(max_length=200)
    capacity = models.IntegerField(default=0)
    
    # Availability
    is_available = models.BooleanField(default=True)
    booking_required = models.BooleanField(default=True)
    booking_advance_days = models.IntegerField(default=7)
    
    # Equipment Details
    equipment_list = models.JSONField(default=list, blank=True)
    specifications = models.JSONField(default=dict, blank=True)
    
    # Maintenance
    last_maintenance = models.DateField(null=True, blank=True)
    next_maintenance = models.DateField(null=True, blank=True)
    maintenance_interval_days = models.IntegerField(default=30)
    
    class Meta:
        db_table = 'departments_department_resource'
        verbose_name = 'Department Resource'
        verbose_name_plural = 'Department Resources'
        indexes = [
            models.Index(fields=['department', 'resource_type']),
            models.Index(fields=['is_available']),
            models.Index(fields=['location']),
        ]

    def __str__(self):
        return f"{self.name} - {self.department.name}"


class DepartmentAnnouncement(TimeStampedModel, SoftDeleteModel, AuditModel, TenantModel):
    """
    Department announcements and notices
    """
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ]

    title = models.CharField(max_length=200)
    content = models.TextField()
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='medium')
    
    # Targeting
    target_roles = models.JSONField(default=list)  # List of roles to target
    target_users = models.ManyToManyField(
        User,
        blank=True,
        related_name='department_announcements'
    )
    
    # Scheduling
    publish_at = models.DateTimeField(default=timezone.now)
    expire_at = models.DateTimeField(null=True, blank=True)
    
    # Engagement
    view_count = models.IntegerField(default=0)
    acknowledgment_required = models.BooleanField(default=False)
    
    class Meta:
        db_table = 'departments_department_announcement'
        verbose_name = 'Department Announcement'
        verbose_name_plural = 'Department Announcements'
        indexes = [
            models.Index(fields=['department', 'publish_at']),
            models.Index(fields=['priority']),
            models.Index(fields=['is_active']),
        ]

    def __str__(self):
        return f"{self.title} - {self.department.name}"

    @property
    def is_expired(self):
        """Check if announcement has expired"""
        return self.expire_at and timezone.now() > self.expire_at

    @property
    def is_published(self):
        """Check if announcement is published"""
        return self.publish_at <= timezone.now() and not self.is_expired


class DepartmentStatistics(TimeStampedModel, TenantModel):
    """
    Department statistics and metrics
    """
    date = models.DateField()
    
    # User Statistics
    total_students = models.IntegerField(default=0)
    active_students = models.IntegerField(default=0)
    total_lecturers = models.IntegerField(default=0)
    active_lecturers = models.IntegerField(default=0)
    
    # Attendance Statistics
    total_sessions = models.IntegerField(default=0)
    total_attendance_records = models.IntegerField(default=0)
    average_attendance_rate = models.FloatField(default=0.0)
    absent_students = models.IntegerField(default=0)
    
    # Performance Statistics
    average_grade = models.FloatField(default=0.0)
    passing_rate = models.FloatField(default=0.0)
    
    # Resource Utilization
    resource_utilization_percentage = models.FloatField(default=0.0)
    
    class Meta:
        db_table = 'departments_department_statistics'
        verbose_name = 'Department Statistics'
        verbose_name_plural = 'Department Statistics'
        unique_together = ['department', 'date']
        indexes = [
            models.Index(fields=['department', 'date']),
            models.Index(fields=['date']),
        ]

    def __str__(self):
        return f"{self.department.name} - {self.date}"
