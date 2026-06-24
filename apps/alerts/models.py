"""
Alerts models for Attendrix - Smart notification and alert system
"""
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from django.core.exceptions import ValidationError
from apps.core.models import TimeStampedModel, SoftDeleteModel, AuditModel, TenantModel
from apps.institutions.models import Institution
from apps.users.models import User
from apps.courses.models import Course
from apps.departments.models import Department
import uuid


class Alert(TimeStampedModel, SoftDeleteModel, AuditModel, TenantModel):
    """
    System alerts for various events and notifications
    """
    ALERT_TYPES = [
        ('attendance_low', 'Low Attendance'),
        ('attendance_absenteeism', 'Chronic Absenteeism'),
        ('suspicious_activity', 'Suspicious Activity'),
        ('pattern_anomaly', 'Pattern Anomaly'),
        ('dropout_risk', 'Dropout Risk'),
        ('performance_decline', 'Performance Decline'),
        ('proxy_detection', 'Proxy Detection'),
        ('schedule_conflict', 'Schedule Conflict'),
        ('system_maintenance', 'System Maintenance'),
        ('security_breach', 'Security Breach'),
        ('deadline_missed', 'Deadline Missed'),
        ('quota_exceeded', 'Quota Exceeded'),
        ('api_error', 'API Error'),
        ('data_integrity', 'Data Integrity'),
        ('custom', 'Custom Alert'),
    ]

    SEVERITY_LEVELS = [
        ('info', 'Info'),
        ('warning', 'Warning'),
        ('critical', 'Critical'),
        ('urgent', 'Urgent'),
    ]

    STATUS_CHOICES = [
        ('active', 'Active'),
        ('acknowledged', 'Acknowledged'),
        ('resolved', 'Resolved'),
        ('dismissed', 'Dismissed'),
    ]

    title = models.CharField(max_length=200)
    description = models.TextField()
    alert_type = models.CharField(max_length=30, choices=ALERT_TYPES)
    severity = models.CharField(max_length=10, choices=SEVERITY_LEVELS)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    
    # Target Information
    student = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='alerts',
        null=True,
        blank=True,
        limit_choices_to={'role': 'student'}
    )
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name='alerts',
        null=True,
        blank=True
    )
    department = models.ForeignKey(
        Department,
        on_delete=models.CASCADE,
        related_name='alerts',
        null=True,
        blank=True
    )
    
    # Alert Data
    alert_data = models.JSONField(default=dict, blank=True)
    threshold_value = models.FloatField(null=True, blank=True)
    actual_value = models.FloatField(null=True, blank=True)
    
    # Notification Settings
    send_email = models.BooleanField(default=True)
    send_sms = models.BooleanField(default=False)
    send_push = models.BooleanField(default=True)
    send_in_app = models.BooleanField(default=True)
    
    # Email Configuration
    email_recipients = models.JSONField(default=list, blank=True)
    email_subject = models.CharField(max_length=200, blank=True)
    email_template = models.CharField(max_length=50, default='default_alert')
    
    # SMS Configuration
    sms_recipients = models.JSONField(default=list, blank=True)
    sms_message = models.TextField(blank=True)
    
    # Status Tracking
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
    
    # Escalation
    escalation_level = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(5)]
    )
    escalated_to = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='escalated_alerts'
    )
    escalated_at = models.DateTimeField(null=True, blank=True)
    
    # Auto-resolution
    auto_resolve = models.BooleanField(default=False)
    auto_resolve_at = models.DateTimeField(null=True, blank=True)
    auto_resolve_conditions = models.JSONField(default=dict, blank=True)
    
    class Meta:
        db_table = 'alerts_alert'
        verbose_name = 'Alert'
        verbose_name_plural = 'Alerts'
        indexes = [
            models.Index(fields=['institution', 'is_active']),
            models.Index(fields=['alert_type']),
            fields=['severity']],
            fields=['status']],
            fields=['student']],
            fields=['course']],
            fields=['acknowledged']],
            fields=['resolved']],
            fields=['escalation_level']],
        ]

    def __str__(self):
        return f"{self.title} - {self.severity}"

    def escalate(self, user, reason=''):
        """Escalate alert to higher level"""
        self.escalation_level += 1
        self.escalated_to = user
        self.escalated_at = timezone.now()
        self.save()
        
        # Log escalation
        from apps.core.models import ActivityLog
        ActivityLog.objects.create(
            user=user,
            institution=self.institution,
            action_type='escalate',
            action_description=f'Alert escalated: {self.title}',
            severity='high',
            metadata={
                'alert_id': self.id,
                'escalation_level': self.escalation_level,
                'reason': reason
            }
        )

    def acknowledge(self, user):
        """Acknowledge alert"""
        self.acknowledged = True
        self.acknowledged_by = user
        self.acknowledged_at = timezone.now()
        self.save()
        
        # Log acknowledgment
        from apps.core.models import ActivityLog
        ActivityLog.objects.create(
            user=user,
            institution=self.institution,
            action_type='acknowledge',
            action_description=f'Alert acknowledged: {self.title}',
            severity='low',
            metadata={
                'alert_id': self.id
            }
        )

    def resolve(self, user, notes=''):
        """Resolve alert"""
        self.resolved = True
        self.resolved_by = user
        self.resolved_at = timezone.now()
        self.resolution_notes = notes
        self.is_active = False
        self.save()
        
        # Log resolution
        from apps.core.models import ActivityLog
        ActivityLog.objects.create(
            user=user,
            institution=self.institution,
            action_type='resolve',
            action_description=f'Alert resolved: {self.title}',
            severity='medium',
            metadata={
                'alert_id': self.id,
                'resolution_notes': notes
            }
        )

    def dismiss(self, user):
        """Dismiss alert"""
        self.status = 'dismissed'
        self.is_active = False
        self.save()
        
        # Log dismissal
        from apps.core.models import ActivityLog
        ActivityLog.objects.create(
            user=user,
            institution=self.institution,
            action_type='dismiss',
            action_description=f'Alert dismissed: {self.title}',
            severity='low',
            metadata={
                'alert_id': self.id
            }
        )


class Notification(TimeStampedModel, TenantModel):
    """
    Individual notification messages
    """
    NOTIFICATION_TYPES = [
        ('attendance_reminder', 'Attendance Reminder'),
        ('deadline_reminder', 'Deadline Reminder'),
        ('alert', 'Alert'),
        ('announcement', 'Announcement'),
        ('message', 'Message'),
        ('system_update', 'System Update'),
        ('grade_posted', 'Grade Posted'),
        ('schedule_change', 'Schedule Change'),
        ('leave_approved', 'Leave Approved'),
        ('survey_invitation', 'Survey Invitation'),
        ('achievement_unlocked', 'Achievement Unlocked'),
        ('custom', 'Custom'),
    ]

    PRIORITY_LEVELS = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ]

    recipient = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='notifications'
    )
    
    title = models.CharField(max_length=200)
    message = models.TextField()
    notification_type = models.CharField(max_length=30, choices=NOTIFICATION_TYPES)
    priority = models.CharField(max_length=10, choices=PRIORITY_LEVELS, default='medium')
    
    # Delivery Status
    email_sent = models.BooleanField(default=False)
    sms_sent = models.BooleanField(default=False)
    push_sent = models.BooleanField(default=False)
    in_app_read = models.BooleanField(default=False)
    
    # Email Details
    email_sent_at = models.DateTimeField(null=True, blank=True)
    email_error = models.TextField(blank=True)
    
    # SMS Details
    sms_sent_at = models.DateTimeField(null=True, blank=True)
    sms_error = models.TextField(blank=True)
    
    # Push Notification Details
    push_sent_at = models.DateTimeField(null=True, blank=True)
    push_error = models.TextField(blank=True)
    
    # Read Status
    read_at = models.DateTimeField(null=True, blank=True)
    read_receipt_sent = models.BooleanField(default=False)
    
    # Action Buttons
    actions = models.JSONField(default=list, blank=True)  # Action buttons for user to click
    
    # Metadata
    metadata = models.JSONField(default=dict, blank=True)
    
    # Expiration
    expires_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'alerts_notification'
        verbose_name = 'Notification'
        verbose_name_plural = 'Notifications'
        indexes = [
            models.Index(fields=['recipient', 'created_at']),
            models.Index(fields=['notification_type']],
            fields=['priority']],
            fields=['in_app_read']],
            fields=['expires_at']],
        ]

    def __str__(self):
        return f"{self.title} - {self.recipient.get_full_name()}"

    def mark_as_read(self):
        """Mark notification as read"""
        self.in_app_read = True
        self.read_at = timezone.now()
        self.save()

    def send_email(self):
        """Send email notification"""
        try:
            from django.core.mail import send_mail
            from django.conf import settings
            
            subject = self.title
            message = self.message
            recipient_email = self.recipient.email
            
            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [recipient_email],
                fail_silently=False
            )
            
            self.email_sent = True
            self.email_sent_at = timezone.now()
            self.save()
            
            return True
            
        except Exception as e:
            self.email_error = str(e)
            self.save()
            return False

    def send_sms(self):
        """Send SMS notification"""
        # This would integrate with an SMS service
        # For now, just mark as sent
        self.sms_sent = True
        self.sms_sent_at = timezone.now()
        self.save()
        return True

    def send_push(self):
        """Send push notification"""
        # This would integrate with a push notification service
        # For now, just mark as sent
        self.push_sent = True
        self.push_sent_at = timezone.now()
        self.save()
        return True

    def is_expired(self):
        """Check if notification has expired"""
        return self.expires_at and timezone.now() > self.expires_at


class NotificationTemplate(TimeStampedModel, TenantModel):
    """
    Reusable notification templates
    """
    TEMPLATE_TYPES = [
        ('attendance_reminder', 'Attendance Reminder'),
        ('low_attendance', 'Low Attendance'),
        ('schedule_change', 'Schedule Change'),
        ('grade_posted', 'Grade Posted'),
        ('leave_approved', 'Leave Approved'),
        ('survey_invitation', 'Survey Invitation'),
        ('achievement_unlocked', 'Achievement Unlocked'),
        ('system_maintenance', 'System Maintenance'),
        ('security_alert', 'Security Alert'),
        ('custom', 'Custom'),
    ]

    name = models.CharField(max_length=100)
    template_type = models.CharField(max_length=30, choices=TEMPLATE_TYPES)
    subject_template = models.CharField(max_length=200)
    message_template = models.TextField()
    
    # Template Variables
    variables = models.JSONField(default=dict, blank=True)  # Available variables
    
    # Styling
    email_html_template = models.TextField(blank=True)
    sms_template = models.TextField(blank=True)
    
    # Settings
    is_active = models.BooleanField(default=True)
    is_default = models.BooleanField(default=False)
    
    # Usage Tracking
    usage_count = models.IntegerField(default=0)
    last_used = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'alerts_notification_template'
        verbose_name = 'Notification Template'
        verbose_name_plural = 'Notification Templates'
        unique_together = ['institution', 'template_type', 'name']
        indexes = [
            models.Index(fields=['template_type']),
            fields=['is_active']],
        ]

    def __str__(self):
        return f"{self.name} - {self.template_type}"

    def render(self, context):
        """Render template with context"""
        # Replace variables in templates
        subject = self.subject_template
        message = self.message_template
        
        for variable, value in context.items():
            placeholder = f"{{{variable}}}"
            subject = subject.replace(placeholder, str(value))
            message = message.replace(placeholder, str(value))
        
        return subject, message


class NotificationPreference(TimeStampedModel, TenantModel):
    """
    User notification preferences
    """
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='notification_preferences'
    )
    
    # Email Preferences
    email_enabled = models.BooleanField(default=True)
    email_attendance_reminders = models.BooleanField(default=True)
    email_alerts = models.BooleanField(default=True)
    email_announcements = models.BooleanField(default=True)
    email_grades = models.BooleanField(default=True)
    email_schedule_changes = models.BooleanField(default=True)
    
    # SMS Preferences
    sms_enabled = models.BooleanField(default=False)
    sms_attendance_reminders = models.BooleanField(default=False)
    sms_alerts = models.BooleanField(default=False)
    
    # Push Notification Preferences
    push_enabled = models.BooleanField(default=True)
    push_attendance_reminders = models.BooleanField(default=True)
    push_alerts = models.BooleanField(default=True)
    push_announcements = models.BooleanField(default=True)
    
    # Quiet Hours
    quiet_hours_enabled = models.BooleanField(default=True)
    quiet_hours_start = models.TimeField(default='22:00:00')
    quiet_hours_end = models.TimeField(default='08:00:00')
    
    # Frequency Controls
    max_notifications_per_hour = models.IntegerField(default=10)
    max_notifications_per_day = models.IntegerField(default=50)
    
    # Channel Preferences
    preferred_channels = models.JSONField(default=['in_app', 'email'])
    
    class Meta:
        db_table = 'alerts_notification_preference'
        verbose_name = 'Notification Preference'
        verbose_name_plural = 'Notification Preferences'
        unique_together = ['institution', 'user']

    def __str__(self):
        return f"Preferences for {self.user.get_full_name()}"


class NotificationQueue(TimeStampedModel, TenantModel):
    """
    Queue for processing notifications
    """
    PRIORITY_LEVELS = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ]

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('sent', 'Sent'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]

    notification = models.ForeignKey(
        Notification,
        on_delete=models.CASCADE,
        related_name='queue_entries'
    )
    
    priority = models.CharField(max_length=10, choices=PRIORITY_LEVELS)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Processing Details
    attempts = models.IntegerField(default=0)
    max_attempts = models.IntegerField(default=3)
    next_attempt_at = models.DateTimeField(null=True, blank=True)
    
    # Error Handling
    error_message = models.TextField(blank=True)
    last_error_at = models.DateTimeField(null=True, blank=True)
    
    # Channel Priority Order
    channel_priority = models.JSONField(default=['push', 'in_app', 'email', 'sms'])
    
    class Meta:
        db_table = 'alerts_notification_queue'
        verbose_name = 'Notification Queue'
        verbose_name_plural = 'Notification Queues'
        indexes = [
            models.Index(fields=['status', 'next_attempt_at']),
            models.Index(fields=['priority']),
            fields=['notification']],
        ]

    def __str__(self):
        return f"Queue for {self.notification.title}"

    def increment_attempts(self):
        """Increment attempt count and schedule next attempt"""
        self.attempts += 1
        self.next_attempt_at = timezone.now() + timedelta(minutes=5 * self.attempts)
        self.save()

    def mark_as_sent(self):
        """Mark as successfully sent"""
        self.status = 'sent'
        self.save()

    def mark_as_failed(self, error_message):
        """Mark as failed"""
        self.status = 'failed'
        self.error_message = error_message
        self.last_error_at = timezone.now()
        self.save()


class AlertRule(TimeStampedModel, SoftDeleteModel, AuditModel, TenantModel):
    """
    Automated alert rules and triggers
    """
    RULE_TYPES = [
        ('threshold', 'Threshold Based'),
        ('pattern', 'Pattern Based'),
        ('schedule', 'Schedule Based'),
        ('event', 'Event Based'),
        ('composite', 'Composite'),
    ]
    
    TRIGGER_EVENTS = [
        ('attendance_marked', 'Attendance Marked'),
        ('session_created', 'Session Created'),
        ('session_closed', 'Session Closed'),
        ('grade_posted', 'Grade Posted'),
        ('user_login', 'User Login'),
        ('user_logout', 'User Logout'),
        ('schedule_change', 'Schedule Change'),
        ('leave_request', 'Leave Request'),
        ('survey_response', 'Survey Response'),
    ]

    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    rule_type = models.CharField(max_length=20, choices=RULE_TYPES)
    
    # Trigger Configuration
    trigger_events = models.JSONField(default=list)  # List of events that trigger this rule
    trigger_conditions = models.JSONField(default=dict)  # Conditions to evaluate
    
    # Alert Configuration
    alert_type = models.CharField(max_length=30, choices=Alert.ALERT_TYPES)
    severity = models.CharField(max_length=10, choices=Alert.SEVERITY_LEVELS)
    
    # Thresholds
    threshold_value = models.FloatField(null=True, blank=True)
    threshold_operator = models.CharField(
        max_length=10,
        choices=[
            ('greater_than', 'Greater Than'),
            ('less_than', 'Less Than'),
            ('equals', 'Equals'),
            ('not_equals', 'Not Equals'),
            ('greater_equal', 'Greater or Equal'),
            ('less_equal', 'Less or Equal'),
        ],
        default='greater_than'
    )
    
    # Pattern Configuration
    pattern_type = models.CharField(
        max_length=20,
        choices=[
            ('consecutive', 'Consecutive'),
            ('trend', 'Trend'),
            ('variance', 'Variance'),
            ('outlier', 'Outlier'),
        ],
        blank=True
    )
    pattern_parameters = models.JSONField(default=dict, blank=True)
    
    # Schedule Configuration
    schedule_type = models.CharField(
        max_length=20,
        choices=[
            ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
        ('custom', 'Custom'),
        ],
        blank=True
    )
    schedule_parameters = models.JSONField(default=dict, blank=True)
    
    # Target Configuration
    target_roles = models.JSONField(default=list)  # List of roles to target
    target_users = models.ManyToManyField(
        User,
        blank=True,
        related_name='alert_rules'
    )
    target_departments = models.ManyToManyField(
        Department,
        blank=True,
        related_name='alert_rules'
    )
    target_courses = models.ManyToManyField(
        Course,
        blank=True,
        related_name='alert_rules'
    )
    
    # Status
    is_active = models.BooleanField(default=True)
    last_triggered = models.DateTimeField(null=True, blank=True)
    trigger_count = models.IntegerField(default=0)
    
    # Actions
    auto_resolve = models.BooleanField(default=False)
    auto_escalate = models.BooleanField(default=False)
    escalation_threshold = models.IntegerField(default=3)
    escalation_role = models.CharField(
        max_length=20,
        choices=[
            ('lecturer', 'Lecturer'),
            ('department_head', 'Department Head'),
            ('institution_admin', 'Institution Admin'),
            ('super_admin', 'Super Admin'),
        ],
        blank=True
    )
    
    class Meta:
        db_table = 'alerts_alert_rule'
        verbose_name = 'Alert Rule'
        verbose_name_plural = 'Alert Rules'
        indexes = [
            models.Index(fields=['is_active']),
            fields=['rule_type']],
            fields=['alert_type']],
            fields=['last_triggered']],
        ]

    def __str__(self):
        return f"{self.name} - {self.rule_type}"

    def evaluate_condition(self, context):
        """Evaluate rule condition against context"""
        if self.rule_type == 'threshold':
            return self._evaluate_threshold_condition(context)
        elif self.rule_type == 'pattern':
            return self._evaluate_pattern_condition(context)
        elif self.rule_type == 'schedule':
            return self._evaluate_schedule_condition(context)
        elif self.rule_type == 'event':
            return self._evaluate_event_condition(context)
        elif self.rule_type == 'composite':
            return self._evaluate_composite_condition(context)
        
        return False

    def _evaluate_threshold_condition(self, context):
        """Evaluate threshold-based condition"""
        if self.threshold_value is None:
            return False
        
        value = context.get('value')
        if value is None:
            return False
        
        operators = {
            'greater_than': lambda a, b: a > b,
            'less_than': lambda a, b: a < b,
            'equals': lambda a, b: a == b,
            'not_equals': lambda a, b: a != b,
            'greater_equal': lambda a, b: a >= b,
            'less_equal': lambda a, b: a <= b,
        }
        
        operator = operators.get(self.threshold_operator)
        return operator(value, self.threshold_value)

    def _evaluate_pattern_condition(self, context):
        """Evaluate pattern-based condition"""
        # This would implement pattern matching logic
        # For now, return False
        return False

    def _evaluate_schedule_condition(self, context):
        """Evaluate schedule-based condition"""
        # This would implement schedule-based logic
        # For now, return False
        return False

    def _evaluate_event_condition(self, context):
        """Evaluate event-based condition"""
        event_type = context.get('event_type')
        return event_type in self.trigger_events

    def _evaluate_composite_condition(self, context):
        """Evaluate composite condition"""
        # This would combine multiple conditions
        # For now, return False
        return False

    def trigger_alert(self, context):
        """Trigger alert based on rule"""
        if self.evaluate_condition(context):
            # Create alert
            Alert.objects.create(
                institution=self.institution,
                title=f"Alert: {self.name}",
                description=self.description,
                alert_type=self.alert_type,
                severity=self.severity,
                alert_data=context
            )
            
            # Update rule statistics
            self.last_triggered = timezone.now()
            self.trigger_count += 1
            self.save()
            
            # Handle auto-escalation
            if self.auto_escalate and self.trigger_count >= self.escalation_threshold:
                self._escalate_alert()
            
            return True
        
        return False

    def _escalate_alert(self):
        """Escalate alert based on configuration"""
        if self.escalation_role:
            # Get users with escalation role
            from apps.users.models import User
            escalation_users = User.objects.filter(
                institution=self.institution,
                role=self.escalation_role,
                is_active=True
            )
            
            if escalation_users.exists():
                # Escalate to first available user
                escalation_user = escalation_users.first()
                latest_alert = Alert.objects.filter(
                    institution=self.institution,
                    alert_type=self.alert_type,
                    is_active=True
                ).order_by('-created_at').first()
                
                if latest_alert:
                    latest_alert.escalate(escalation_user)
                    self.escalated_to = escalation_user
                    self.save()
