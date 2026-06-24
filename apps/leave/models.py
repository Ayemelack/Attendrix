"""
Leave management models for Attendrix - Complete leave workflow system
"""
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from apps.core.models import TimeStampedModel, SoftDeleteModel, AuditModel, TenantModel
from apps.institutions.models import Institution
from apps.users.models import User
from apps.departments.models import Department
from apps.courses.models import Course
from apps.scheduling.models import Schedule
import uuid


class LeaveType(TimeStampedModel, SoftDeleteModel, AuditModel, TenantModel):
    """
    Leave type definitions
    """
    LEAVE_CATEGORIES = [
        ('sick', 'Sick Leave'),
        ('personal', 'Personal Leave'),
        ('vacation', 'Vacation Leave'),
        ('maternity', 'Maternity Leave'),
        ('paternity', 'Paternity Leave'),
        ('bereavement', 'Bereavement Leave'),
        ('study', 'Study Leave'),
        ('unpaid', 'Unpaid Leave'),
        ('compensatory', 'Compensatory Leave'),
        ('sabbatical', 'Sabbatical Leave'),
        ('military', 'Military Leave'),
        ('jury_duty', 'Jury Duty'),
        ('other', 'Other'),
    ]

    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    category = models.CharField(max_length=20, choices=LEAVE_CATEGORIES)
    
    # Leave Policies
    max_days_per_year = models.IntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(365)]
    )
    max_consecutive_days = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(365)]
    )
    requires_approval = models.BooleanField(default=True)
    requires_documentation = models.BooleanField(default=False)
    
    # Eligibility
    eligible_roles = models.JSONField(default=list)  # List of roles that can use this leave type
    min_employment_months = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0)]
    )
    
    # Accrual Settings
    accrual_frequency = models.CharField(
        max_length=20,
        choices=[
            ('none', 'No Accrual'),
            ('monthly', 'Monthly'),
            ('quarterly', 'Quarterly'),
        ],
        default='monthly'
    )
    accrual_rate = models.FloatField(
        default=0.0,
        validators=[MinValueValidator(0.0), MaxValueValidator(30.0)]
    )
    carry_forward_allowed = models.BooleanField(default=False)
    max_carry_forward_days = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(365)]
    )
    
    # Restrictions
    blackout_periods = models.JSONField(default=list)  # Periods when leave cannot be taken
    advance_notice_days = models.IntegerField(
        default=1,
        validators=[MinValueValidator(0), MaxValueValidator(90)]
    )
    
    # Status
    is_active = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'leave_leave_type'
        verbose_name = 'Leave Type'
        verbose_name_plural = 'Leave Types'
        unique_together = ['institution', 'name']
        indexes = [
            models.Index(fields=['institution', 'category']),
            models.Index(fields=['is_active']),
        ]

    def __str__(self):
        return f"{self.name} - {self.category}"


class LeaveBalance(TimeStampedModel, TenantModel):
    """
    Leave balance tracking for users
    """
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='leave_balances'
    )
    leave_type = models.ForeignKey(
        LeaveType,
        on_delete=models.CASCADE,
        related_name='leave_balances'
    )
    
    # Balance Information
    accrued_days = models.FloatField(default=0.0)
    used_days = models.FloatField(default=0.0)
    pending_days = models.FloatField(default=0.0)
    available_days = models.FloatField(default=0.0)
    
    # Carry Forward
    carried_forward_days = models.FloatField(default=0.0)
    carry_forward_expiry = models.DateField(null=True, blank=True)
    
    # Period Information
    period_start = models.DateField()
    period_end = models.DateField()
    
    # Last Updated
    last_updated = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'leave_leave_balance'
        verbose_name = 'Leave Balance'
        verbose_name_plural = 'Leave Balances'
        unique_together = ['user', 'leave_type', 'period_start', 'period_end']
        indexes = [
            models.Index(fields=['user', 'period_start', 'period_end']),
            models.Index(fields=['leave_type']),
        ]

    def __str__(self):
        return f"{self.user.get_full_name()} - {self.leave_type.name}: {self.available_days} days"

    def save(self, *args, **kwargs):
        # Calculate available days
        self.available_days = self.accrued_days - self.used_days - self.pending_days
        super().save(*args, **kwargs)

    def can_request_leave(self, days):
        """Check if user can request leave"""
        return self.available_days >= days

    def deduct_leave(self, days):
        """Deduct leave from balance"""
        self.used_days += days
        self.available_days -= days
        self.save()

    def add_pending_leave(self, days):
        """Add pending leave request"""
        self.pending_days += days
        self.available_days -= days
        self.save()

    def approve_pending_leave(self, days):
        """Approve pending leave request"""
        self.pending_days -= days
        self.used_days += days
        self.save()

    def reject_pending_leave(self, days):
        """Reject pending leave request"""
        self.pending_days -= days
        self.available_days += days
        self.save()


class LeaveRequest(TimeStampedModel, SoftDeleteModel, AuditModel, TenantModel):
    """
    Leave request management
    """
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('pending', 'Pending Approval'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('cancelled', 'Cancelled'),
        ('completed', 'Completed'),
    ]

    PRIORITY_LEVELS = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='leave_requests'
    )
    leave_type = models.ForeignKey(
        LeaveType,
        on_delete=models.CASCADE,
        related_name='leave_requests'
    )
    
    # Leave Details
    start_date = models.DateField()
    end_date = models.DateField()
    total_days = models.IntegerField()
    half_day = models.BooleanField(default=False)
    half_day_part = models.CharField(
        max_length=10,
        choices=[
            ('morning', 'Morning'),
            ('afternoon', 'Afternoon'),
        ],
        blank=True
    )
    
    # Request Information
    reason = models.TextField()
    priority = models.CharField(max_length=10, choices=PRIORITY_LEVELS, default='medium')
    
    # Contact Information
    contact_phone = models.CharField(max_length=20, blank=True)
    contact_email = models.EmailField(blank=True)
    emergency_contact = models.TextField(blank=True)
    
    # Documentation
    supporting_documents = models.JSONField(default=list)  # List of document IDs
    medical_certificate = models.FileField(
        upload_to='leave_documents/medical/',
        blank=True,
        null=True
    )
    
    # Approval Workflow
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    approver = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_leave_requests'
    )
    approval_date = models.DateTimeField(null=True, blank=True)
    approval_notes = models.TextField(blank=True)
    
    # Delegation
    delegated_approver = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='delegated_leave_requests'
    )
    
    # Comments
    requester_comments = models.TextField(blank=True)
    approver_comments = models.TextField(blank=True)
    
    class Meta:
        db_table = 'leave_leave_request'
        verbose_name = 'Leave Request'
        verbose_name_plural = 'Leave Requests'
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['leave_type']),
            models.Index(fields=['start_date', 'end_date']),
            models.Index(fields=['status', 'priority']),
            models.Index(fields=['approver']),
        ]

    def __str__(self):
        return f"{self.user.get_full_name()} - {self.leave_type.name} - {self.status}"

    def clean(self):
        """Validate leave request"""
        if self.start_date > self.end_date:
            raise ValidationError("Start date cannot be after end date")
        
        # Calculate total days
        if self.start_date == self.end_date and self.half_day:
            self.total_days = 0.5
        else:
            # Calculate business days (excluding weekends)
            from datetime import timedelta
            current_date = self.start_date
            days_count = 0
            
            while current_date <= self.end_date:
                if current_date.weekday() < 5:  # Monday to Friday
                    days_count += 1
                current_date += timedelta(days=1)
            
            self.total_days = days_count

    def save(self, *args, **kwargs):
        # Calculate total days before saving
        self.clean()
        super().save(*args, **kwargs)

    def approve(self, approver, notes=''):
        """Approve leave request"""
        self.status = 'approved'
        self.approver = approver
        self.approval_date = timezone.now()
        self.approver_comments = notes
        
        # Update leave balance
        try:
            balance = LeaveBalance.objects.get(
                user=self.user,
                leave_type=self.leave_type,
                period_start__lte=self.start_date,
                period_end__gte=self.end_date
            )
            balance.approve_pending_leave(self.total_days)
        except LeaveBalance.DoesNotExist:
            # Create balance if it doesn't exist
            pass
        
        self.save()

    def reject(self, approver, notes=''):
        """Reject leave request"""
        self.status = 'rejected'
        self.approver = approver
        self.approval_date = timezone.now()
        self.approver_comments = notes
        
        # Update leave balance
        try:
            balance = LeaveBalance.objects.get(
                user=self.user,
                leave_type=self.leave_type,
                period_start__lte=self.start_date,
                period_end__gte=self.end_date
            )
            balance.reject_pending_leave(self.total_days)
        except LeaveBalance.DoesNotExist:
            # Create balance if it doesn't exist
            pass
        
        self.save()

    def cancel(self):
        """Cancel leave request"""
        self.status = 'cancelled'
        
        # Update leave balance
        try:
            balance = LeaveBalance.objects.get(
                user=self.user,
                leave_type=self.leave_type,
                period_start__lte=self.start_date,
                period_end__gte=self.end_date
            )
            balance.reject_pending_leave(self.total_days)
        except LeaveBalance.DoesNotExist:
            # Create balance if it doesn't exist
            pass
        
        self.save()


class LeaveApproval(TimeStampedModel, TenantModel):
    """
    Leave approval workflow tracking
    """
    APPROVAL_TYPES = [
        ('initial', 'Initial Approval'),
        ('delegated', 'Delegated Approval'),
        ('escalated', 'Escalated Approval'),
        ('final', 'Final Approval'),
    ]

    DECISION_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('escalated', 'Escalated'),
    ]

    leave_request = models.ForeignKey(
        LeaveRequest,
        on_delete=models.CASCADE,
        related_name='approvals'
    )
    approver = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='leave_approvals'
    )
    approval_type = models.CharField(max_length=20, choices=APPROVAL_TYPES)
    decision = models.CharField(max_length=20, choices=DECISION_CHOICES, default='pending')
    
    # Approval Details
    comments = models.TextField(blank=True)
    decision_date = models.DateTimeField(null=True, blank=True)
    
    # Delegation
    delegated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='delegated_approvals'
    )
    delegation_reason = models.TextField(blank=True)
    
    # Escalation
    escalated_to = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='escalated_approvals'
    )
    escalation_reason = models.TextField(blank=True)
    
    class Meta:
        db_table = 'leave_leave_approval'
        verbose_name = 'Leave Approval'
        verbose_name_plural = 'Leave Approvals'
        indexes = [
            models.Index(fields=['leave_request', 'approver']),
            models.Index(fields=['decision']),
            models.Index(fields=['approval_type']),
            models.Index(fields=['decision_date']),
        ]

    def __str__(self):
        return f"{self.leave_request.user.get_full_name()} - {self.approver.get_full_name()} - {self.decision}"

    def approve(self, comments=''):
        """Approve leave request"""
        self.decision = 'approved'
        self.decision_date = timezone.now()
        self.comments = comments
        self.save()

    def reject(self, comments=''):
        """Reject leave request"""
        self.decision = 'rejected'
        self.decision_date = timezone.now()
        self.comments = comments
        self.save()

    def escalate(self, escalated_to, reason=''):
        """Escalate approval"""
        self.decision = 'escalated'
        self.escalated_to = escalated_to
        self.escalation_reason = reason
        self.decision_date = timezone.now()
        self.save()


class LeaveCalendar(TimeStampedModel, TenantModel):
    """
    Leave calendar for tracking leave across the institution
    """
    calendar_type = models.CharField(
        max_length=20,
        choices=[
            ('department', 'Department'),
            ('course', 'Course'),
            ('institution', 'Institution'),
            ('personal', 'Personal'),
        ]
    )
    
    # Calendar Details
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    
    # Association
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='leave_calendars',
        null=True,
        blank=True
    )
    department = models.ForeignKey(
        Department,
        on_delete=models.CASCADE,
        related_name='leave_calendars',
        null=True,
        blank=True
    )
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name='leave_calendars',
        null=True,
        blank=True
    )
    
    # Calendar Settings
    is_public = models.BooleanField(default=False)
    show_weekends = models.BooleanField(default=True)
    show_holidays = models.BooleanField(default=True)
    
    # View Settings
    default_view = models.CharField(
        max_length=20,
        choices=[
            ('month', 'Month'),
            ('week', 'Week'),
            ('day', 'Day'),
        ],
        default='month'
    )
    
    class Meta:
        db_table = 'leave_leave_calendar'
        verbose_name = 'Leave Calendar'
        verbose_name_plural = 'Leave Calendars'
        indexes = [
            models.Index(fields=['calendar_type']),
            models.Index(fields=['user']),
            models.Index(fields=['department']),
            models.Index(fields=['course']),
            models.Index(fields=['is_public']),
        ]

    def __str__(self):
        return f"{self.name} - {self.calendar_type}"


class LeaveHoliday(TimeStampedModel, TenantModel):
    """
    Holidays and institutional holidays that affect leave calculations
    """
    HOLIDAY_TYPES = [
        ('national', 'National Holiday'),
        ('institutional', 'Institutional Holiday'),
        ('religious', 'Religious Holiday'),
        ('custom', 'Custom Holiday'),
    ]

    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    holiday_type = models.CharField(max_length=20, choices=HOLIDAY_TYPES)
    date = models.DateField()
    
    # Recurrence
    is_recurring = models.BooleanField(default=False)
    recurrence_pattern = models.JSONField(default=dict, blank=True)  # Yearly, monthly, etc.
    
    # Impact
    affects_leave = models.BooleanField(default=True)
    affects_attendance = models.BooleanField(default=True)
    
    # Customization
    color = models.CharField(max_length=7, default='#FF0000')  # Hex color code
    icon = models.CharField(max_length=50, blank=True)
    
    class Meta:
        db_table = 'leave_leave_holiday'
        verbose_name = 'Leave Holiday'
        verbose_name_plural = 'Leave Holidays'
        indexes = [
            models.Index(fields=['institution', 'date']),
            models.Index(fields=['holiday_type']),
            models.Index(fields=['is_recurring']),
        ]

    def __str__(self):
        return f"{self.name} - {self.date}"


class LeaveAnalytics(TimeStampedModel, TenantModel):
    """
    Leave analytics and reporting
    """
    ANALYTICS_TYPES = [
        ('summary', 'Summary'),
        ('trend', 'Trend'),
        ('department', 'Department'),
        ('course', 'Course'),
        ('user', 'User'),
        ('leave_type', 'Leave Type'),
    ]

    analytics_type = models.CharField(max_length=20, choices=ANALYTICS_TYPES)
    reference_id = models.UUIDField(null=True, blank=True)  # User, Department, Course, etc.
    reference_date = models.DateField()
    
    # Leave Statistics
    total_requests = models.IntegerField(default=0)
    approved_requests = models.IntegerField(default=0)
    rejected_requests = models.IntegerField(default=0)
    pending_requests = models.IntegerField(default=0)
    cancelled_requests = models.IntegerField(default=0)
    
    # Day Statistics
    total_leave_days = models.FloatField(default=0.0)
    approved_leave_days = models.FloatField(default=0.0)
    
    # Rates
    approval_rate = models.FloatField(default=0.0)
    rejection_rate = models.FloatField(default=0.0)
    average_days_per_request = models.FloatField(default=0.0)
    
    # Trends
    trend_percentage = models.FloatField(default=0.0)  # Change from previous period
    trend_direction = models.CharField(
        max_length=10,
        choices=[
            ('increasing', 'Increasing'),
            ('decreasing', 'Decreasing'),
            ('stable', 'Stable'),
        ],
        default='stable'
    )
    
    # Additional Data
    metadata = models.JSONField(default=dict, blank=True)
    
    class Meta:
        db_table = 'leave_leave_analytics'
        verbose_name = 'Leave Analytics'
        verbose_name_plural = 'Leave Analytics'
        unique_together = ['institution', 'analytics_type', 'reference_id', 'reference_date']
        indexes = [
            models.Index(fields=['institution', 'analytics_type', 'reference_date']),
            models.Index(fields=['analytics_type']),
            models.Index(fields=['reference_date']),
            models.Index(fields=['trend_direction']),
        ]

    def __str__(self):
        return f"{self.analytics_type.title()} - {self.reference_date}"

    def calculate_rates(self):
        """Calculate approval and rejection rates"""
        if self.total_requests > 0:
            self.approval_rate = (self.approved_requests / self.total_requests) * 100
            self.rejection_rate = (self.rejected_requests / self.total_requests) * 100
        
        if self.approved_requests > 0:
            self.average_days_per_request = self.approved_leave_days / self.approved_requests
        
        self.save()


class LeavePolicy(TimeStampedModel, TenantModel):
    """
    Institution-wide leave policies and settings
    """
    institution = models.OneToOneField(
        Institution,
        on_delete=models.CASCADE,
        related_name='leave_policy'
    )
    
    # General Settings
    max_concurrent_leaves = models.IntegerField(
        default=5,
        validators=[MinValueValidator(1), MaxValueValidator(50)]
    )
    advance_notice_days = models.IntegerField(
        default=3,
        validators=[MinValueValidator(0), MaxValueValidator(90)]
    )
    
    # Approval Workflow
    approval_workflow = models.JSONField(default=dict)  # Multi-step approval configuration
    auto_approve_days = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(30)]
    )
    
    # Calendar Settings
    working_days_only = models.BooleanField(default=True)
    include_weekends = models.BooleanField(default=False)
    exclude_holidays = models.BooleanField(default=True)
    
    # Notification Settings
    notify_requester = models.BooleanField(default=True)
    notify_approver = models.BooleanField(default=True)
    notify_department_head = models.BooleanField(default=False)
    
    # Document Requirements
    require_documents_for_days = models.IntegerField(
        default=3,
        validators=[MinValueValidator(0), MaxValueValidator(30)]
    )
    allowed_document_types = models.JSONField(default=list)
    
    # Carry Forward Settings
    carry_forward_enabled = models.BooleanField(default=True)
    max_carry_forward_days = models.IntegerField(
        default=10,
        validators=[MinValueValidator(0), MaxValueValidator(365)]
    )
    carry_forward_expiry_months = models.IntegerField(
        default=6,
        validators=[MinValueValidator(1), MaxValueValidator(24)]
    )
    
    class Meta:
        db_table = 'leave_leave_policy'
        verbose_name = 'Leave Policy'
        verbose_name_plural = 'Leave Policies'

    def __str__(self):
        return f"Leave Policy for {self.institution.name}"
