from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, MaxValueValidator
from apps.institutions.models import Institution

User = get_user_model()


class LeaveType(models.Model):
    """Leave types with policies"""
    institution = models.ForeignKey(Institution, on_delete=models.CASCADE, related_name='leave_types')
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    requires_approval = models.BooleanField(default=True)
    max_days_per_request = models.PositiveIntegerField(default=5)
    max_days_per_year = models.PositiveIntegerField(default=30)
    requires_document = models.BooleanField(default=False)
    is_paid = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Leave Type'
        verbose_name_plural = 'Leave Types'
        unique_together = ['institution', 'name']
    
    def __str__(self):
        return f"{self.name} - {self.institution.name}"


class LeaveBalance(models.Model):
    """Leave balance for users"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='leave_balances')
    leave_type = models.ForeignKey(LeaveType, on_delete=models.CASCADE, related_name='balances')
    balance_days = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    used_days = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    year = models.PositiveIntegerField()
    last_updated = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Leave Balance'
        verbose_name_plural = 'Leave Balances'
        unique_together = ['user', 'leave_type', 'year']
    
    @property
    def remaining_days(self):
        return self.balance_days - self.used_days
    
    def __str__(self):
        return f"{self.user.username} - {self.leave_type.name} ({self.year})"


class LeaveRequest(models.Model):
    """Leave requests"""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('cancelled', 'Cancelled'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='leave_requests')
    leave_type = models.ForeignKey(LeaveType, on_delete=models.CASCADE, related_name='requests')
    start_date = models.DateField()
    end_date = models.DateField()
    total_days = models.DecimalField(max_digits=5, decimal_places=2)
    reason = models.TextField()
    attachment = models.FileField(upload_to='leave_attachments/', blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    approver = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_leaves')
    approver_comments = models.TextField(blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Leave Request'
        verbose_name_plural = 'Leave Requests'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user.username} - {self.leave_type.name} ({self.status})"
    
    def clean(self):
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValidationError('Start date must be before end date')


class LeaveApproval(models.Model):
    """Leave approval workflow"""
    leave_request = models.ForeignKey(LeaveRequest, on_delete=models.CASCADE, related_name='approvals')
    approver = models.ForeignKey(User, on_delete=models.CASCADE, related_name='leave_approvals')
    status = models.CharField(max_length=20, choices=LeaveRequest.STATUS_CHOICES)
    comments = models.TextField(blank=True)
    approved_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Leave Approval'
        verbose_name_plural = 'Leave Approvals'
        unique_together = ['leave_request', 'approver']
    
    def __str__(self):
        return f"{self.approver.username} - {self.leave_request}"


class LeaveCalendar(models.Model):
    """Leave calendar for institutional planning"""
    institution = models.ForeignKey(Institution, on_delete=models.CASCADE, related_name='leave_calendar')
    date = models.DateField()
    leave_type = models.ForeignKey(LeaveType, on_delete=models.CASCADE, related_name='calendar_entries')
    users_on_leave = models.ManyToManyField(User, related_name='leave_calendar_entries')
    total_users = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Leave Calendar'
        verbose_name_plural = 'Leave Calendar'
        unique_together = ['institution', 'date', 'leave_type']
    
    def __str__(self):
        return f"{self.institution.name} - {self.date} - {self.leave_type.name}"


class LeaveHoliday(models.Model):
    """Institution holidays that don't count as leave days"""
    institution = models.ForeignKey(Institution, on_delete=models.CASCADE, related_name='holidays')
    name = models.CharField(max_length=100)
    date = models.DateField()
    is_recurring = models.BooleanField(default=False)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Leave Holiday'
        verbose_name_plural = 'Leave Holidays'
        unique_together = ['institution', 'date']
    
    def __str__(self):
        return f"{self.name} - {self.institution.name}"


class LeaveAnalytics(models.Model):
    """Leave analytics and statistics"""
    institution = models.ForeignKey(Institution, on_delete=models.CASCADE, related_name='leave_analytics')
    year = models.PositiveIntegerField()
    month = models.PositiveIntegerField(validators=[MinValueValidator(1), MaxValueValidator(12)])
    leave_type = models.ForeignKey(LeaveType, on_delete=models.CASCADE, related_name='analytics')
    total_requests = models.PositiveIntegerField(default=0)
    approved_requests = models.PositiveIntegerField(default=0)
    rejected_requests = models.PositiveIntegerField(default=0)
    pending_requests = models.PositiveIntegerField(default=0)
    total_leave_days = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    average_leave_duration = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Leave Analytics'
        verbose_name_plural = 'Leave Analytics'
        unique_together = ['institution', 'year', 'month', 'leave_type']
    
    @property
    def approval_rate(self):
        if self.total_requests == 0:
            return 0
        return (self.approved_requests / self.total_requests) * 100
    
    def __str__(self):
        return f"{self.institution.name} - {self.year}/{self.month} - {self.leave_type.name}"


class LeavePolicy(models.Model):
    """Institution leave policies"""
    institution = models.ForeignKey(Institution, on_delete=models.CASCADE, related_name='leave_policies')
    name = models.CharField(max_length=100)
    description = models.TextField()
    leave_type = models.ForeignKey(LeaveType, on_delete=models.CASCADE, related_name='policies')
    accrual_rate = models.DecimalField(max_digits=5, decimal_places=2, help_text="Days accrued per month")
    accrual_frequency = models.CharField(max_length=20, choices=[
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
        ('annually', 'Annually'),
    ], default='monthly')
    carry_forward_allowed = models.BooleanField(default=True)
    max_carry_forward_days = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    probation_period_months = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Leave Policy'
        verbose_name_plural = 'Leave Policies'
        unique_together = ['institution', 'name']
    
    def __str__(self):
        return f"{self.name} - {self.institution.name}"
