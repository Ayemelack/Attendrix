"""
Alerts serializers for Attendrix API
"""
from rest_framework import serializers
from django.utils import timezone
from apps.alerts.models import (
    Alert, Notification, NotificationTemplate, NotificationPreference,
    NotificationQueue, AlertRule
)
from apps.users.serializers import UserSerializer
from apps.courses.serializers import CourseSerializer
from apps.departments.serializers import DepartmentSerializer


class AlertSerializer(serializers.ModelSerializer):
    """
    Alert serializer
    """
    student_info = UserSerializer(source='student', read_only=True)
    course_info = CourseSerializer(source='course', read_only=True)
    department_info = DepartmentSerializer(source='department', read_only=True)
    acknowledged_by_info = UserSerializer(source='acknowledged_by', read_only=True)
    resolved_by_info = UserSerializer(source='resolved_by', read_only=True)
    escalated_to_info = UserSerializer(source='escalated_to', read_only=True)
    
    class Meta:
        model = Alert
        fields = [
            'id', 'title', 'description', 'alert_type', 'severity', 'status',
            'student', 'student_info', 'course', 'course_info', 'department', 'department_info',
            'alert_data', 'threshold_value', 'actual_value',
            'send_email', 'send_sms', 'send_push', 'send_in_app',
            'email_recipients', 'email_subject', 'email_template',
            'sms_recipients', 'sms_message',
            'is_active', 'acknowledged', 'acknowledged_by', 'acknowledged_by_info', 'acknowledged_at',
            'resolved', 'resolved_by', 'resolved_by_info', 'resolved_at', 'resolution_notes',
            'escalation_level', 'escalated_to', 'escalated_to_info', 'escalated_at',
            'auto_resolve', 'auto_resolve_at', 'auto_resolve_conditions',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'acknowledged', 'acknowledged_by', 'acknowledged_at',
            'resolved', 'resolved_by', 'resolved_at',
            'escalation_level', 'escalated_to', 'escalated_at',
            'created_at', 'updated_at'
        ]

    def create(self, validated_data):
        """Create alert with notification processing"""
        alert = super().create(validated_data)
        
        # Process notifications based on settings
        if alert.send_in_app:
            self._create_in_app_notifications(alert)
        
        if alert.send_email:
            self._queue_email_notifications(alert)
        
        if alert.send_sms:
            self._queue_sms_notifications(alert)
        
        if alert.send_push:
            self._queue_push_notifications(alert)
        
        return alert

    def _create_in_app_notifications(self, alert):
        """Create in-app notifications"""
        recipients = self._get_recipients(alert)
        
        for recipient in recipients:
            Notification.objects.create(
                institution=alert.institution,
                recipient=recipient,
                title=alert.title,
                message=alert.description,
                notification_type='alert',
                priority=alert.severity,
                metadata={
                    'alert_id': alert.id,
                    'alert_type': alert.alert_type
                }
            )

    def _queue_email_notifications(self, alert):
        """Queue email notifications"""
        recipients = self._get_recipients(alert)
        
        for recipient in recipients:
            # Create notification queue entry
            notification = Notification.objects.create(
                institution=alert.institution,
                recipient=recipient,
                title=alert.title,
                message=alert.description,
                notification_type='alert',
                priority=alert.severity,
                metadata={
                    'alert_id': alert.id,
                    'alert_type': alert.alert_type
                }
            )
            
            NotificationQueue.objects.create(
                institution=alert.institution,
                notification=notification,
                priority=alert.severity,
                channel_priority=['email']
            )

    def _queue_sms_notifications(self, alert):
        """Queue SMS notifications"""
        recipients = self._get_recipients(alert)
        
        for recipient in recipients:
            notification = Notification.objects.create(
                institution=alert.institution,
                recipient=recipient,
                title=alert.title,
                message=alert.description,
                notification_type='alert',
                priority=alert.severity,
                metadata={
                    'alert_id': alert.id,
                    'alert_type': alert.alert_type
                }
            )
            
            NotificationQueue.objects.create(
                institution=alert.institution,
                notification=notification,
                priority=alert.severity,
                channel_priority=['sms']
            )

    def _queue_push_notifications(self, alert):
        """Queue push notifications"""
        recipients = self._get_recipients(alert)
        
        for recipient in recipients:
            notification = Notification.objects.create(
                institution=alert.institution,
                recipient=recipient,
                title=alert.title,
                message=alert.description,
                notification_type='alert',
                priority=alert.severity,
                metadata={
                    'alert_id': alert.id,
                    'alert_type': alert.alert_type
                }
            )
            
            NotificationQueue.objects.create(
                institution=alert.institution,
                notification=notification,
                priority=alert.severity,
                channel_priority=['push']
            )

    def _get_recipients(self, alert):
        """Get alert recipients based on target configuration"""
        recipients = []
        
        # Add specific student if targeted
        if alert.student:
            recipients.append(alert.student)
        
        # Add course students if course is targeted
        if alert.course:
            from apps.courses.models import CourseEnrollment
            course_students = User.objects.filter(
                courseenrollments__course=alert.course,
                courseenrollments__status='enrolled'
            )
            recipients.extend(course_students)
        
        # Add department users if department is targeted
        if alert.department:
            dept_users = User.objects.filter(department=alert.department)
            recipients.extend(dept_users)
        
        # Add email recipients
        if alert.email_recipients:
            from apps.users.models import User
            email_users = User.objects.filter(email__in=alert.email_recipients)
            recipients.extend(email_users)
        
        # Remove duplicates and return
        return list(set(recipients))


class NotificationSerializer(serializers.ModelSerializer):
    """
    Notification serializer
    """
    recipient_info = UserSerializer(source='recipient', read_only=True)
    
    class Meta:
        model = Notification
        fields = [
            'id', 'recipient', 'recipient_info', 'title', 'message',
            'notification_type', 'priority',
            'email_sent', 'sms_sent', 'push_sent', 'in_app_read',
            'email_sent_at', 'email_error', 'sms_sent_at', 'sms_error',
            'push_sent_at', 'push_error', 'read_at', 'read_receipt_sent',
            'actions', 'metadata', 'expires_at',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'email_sent', 'sms_sent', 'push_sent', 'in_app_read',
            'email_sent_at', 'sms_sent_at', 'push_sent_at', 'read_at',
            'created_at', 'updated_at'
        ]

    def update(self, instance, validated_data):
        """Update notification with read status handling"""
        if 'in_app_read' in validated_data and validated_data['in_app_read']:
            if not instance.in_app_read:
                instance.mark_as_read()
        
        return super().update(instance, validated_data)


class NotificationTemplateSerializer(serializers.ModelSerializer):
    """
    Notification template serializer
    """
    class Meta:
        model = NotificationTemplate
        fields = [
            'id', 'name', 'template_type', 'subject_template', 'message_template',
            'variables', 'email_html_template', 'sms_template',
            'is_active', 'is_default', 'usage_count', 'last_used',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['usage_count', 'last_used', 'created_at', 'updated_at']

    def create(self, validated_data):
        """Create notification template"""
        template = super().create(validated_data)
        
        # Log template creation
        from apps.core.models import ActivityLog
        ActivityLog.objects.create(
            user=self.context['request'].user,
            institution=template.institution,
            action_type='create',
            action_description=f'Notification template created: {template.name}',
            severity='low'
        )
        
        return template

    def update(self, instance, validated_data):
        """Update notification template"""
        template = super().update(instance, validated_data)
        
        # Log template update
        from apps.core.models import ActivityLog
        ActivityLog.objects.create(
            user=self.context['request'].user,
            institution=template.institution,
            action_type='update',
            action_description=f'Notification template updated: {template.name}',
            severity='low'
        )
        
        return template


class NotificationPreferenceSerializer(serializers.ModelSerializer):
    """
    Notification preference serializer
    """
    user_info = UserSerializer(source='user', read_only=True)
    
    class Meta:
        model = NotificationPreference
        fields = [
            'id', 'user', 'user_info',
            'email_enabled', 'email_attendance_reminders', 'email_alerts',
            'email_announcements', 'email_grades', 'email_schedule_changes',
            'sms_enabled', 'sms_attendance_reminders', 'sms_alerts',
            'push_enabled', 'push_attendance_reminders', 'push_alerts', 'push_announcements',
            'quiet_hours_enabled', 'quiet_hours_start', 'quiet_hours_end',
            'max_notifications_per_hour', 'max_notifications_per_day',
            'preferred_channels',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']

    def validate(self, attrs):
        """Validate notification preferences"""
        # Validate quiet hours
        if attrs.get('quiet_hours_enabled'):
            start_time = attrs.get('quiet_hours_start')
            end_time = attrs.get('quiet_hours_end')
            
            if start_time and end_time:
                if start_time == end_time:
                    raise serializers.ValidationError("Quiet hours start and end time cannot be the same")
        
        # Validate notification limits
        max_per_hour = attrs.get('max_notifications_per_hour', 10)
        max_per_day = attrs.get('max_notifications_per_day', 50)
        
        if max_per_hour < 0:
            raise serializers.ValidationError("Max notifications per hour cannot be negative")
        
        if max_per_day < 0:
            raise serializers.ValidationError("Max notifications per day cannot be negative")
        
        if max_per_hour > max_per_day:
            raise serializers.ValidationError("Max notifications per hour cannot exceed max per day")
        
        return attrs


class NotificationQueueSerializer(serializers.ModelSerializer):
    """
    Notification queue serializer
    """
    notification_info = NotificationSerializer(source='notification', read_only=True)
    
    class Meta:
        model = NotificationQueue
        fields = [
            'id', 'notification', 'notification_info', 'priority', 'status',
            'attempts', 'max_attempts', 'next_attempt_at',
            'error_message', 'last_error_at', 'channel_priority',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'attempts', 'next_attempt_at', 'error_message', 'last_error_at',
            'created_at', 'updated_at'
        ]


class AlertRuleSerializer(serializers.ModelSerializer):
    """
    Alert rule serializer
    """
    target_users_info = UserSerializer(source='target_users', many=True, read_only=True)
    target_departments_info = DepartmentSerializer(source='target_departments', many=True, read_only=True)
    target_courses_info = CourseSerializer(source='target_courses', many=True, read_only=True)
    escalated_to_info = UserSerializer(source='escalated_to', read_only=True)
    
    class Meta:
        model = AlertRule
        fields = [
            'id', 'name', 'description', 'rule_type',
            'trigger_events', 'trigger_conditions',
            'alert_type', 'severity',
            'threshold_value', 'threshold_operator',
            'pattern_type', 'pattern_parameters',
            'schedule_type', 'schedule_parameters',
            'target_roles', 'target_users', 'target_users_info',
            'target_departments', 'target_departments_info',
            'target_courses', 'target_courses_info',
            'is_active', 'last_triggered', 'trigger_count',
            'auto_resolve', 'auto_escalate', 'escalation_threshold', 'escalation_role',
            'escalated_to', 'escalated_to_info',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'last_triggered', 'trigger_count', 'escalated_to',
            'created_at', 'updated_at'
        ]

    def validate(self, attrs):
        """Validate alert rule"""
        rule_type = attrs.get('rule_type')
        
        # Validate threshold rules
        if rule_type == 'threshold':
            if not attrs.get('threshold_value'):
                raise serializers.ValidationError("Threshold value is required for threshold-based rules")
        
        # Validate pattern rules
        if rule_type == 'pattern':
            if not attrs.get('pattern_type'):
                raise serializers.ValidationError("Pattern type is required for pattern-based rules")
        
        # Validate schedule rules
        if rule_type == 'schedule':
            if not attrs.get('schedule_type'):
                raise serializers.ValidationError("Schedule type is required for schedule-based rules")
        
        # Validate event rules
        if rule_type == 'event':
            if not attrs.get('trigger_events'):
                raise serializers.ValidationError("Trigger events are required for event-based rules")
        
        return attrs

    def create(self, validated_data):
        """Create alert rule"""
        rule = super().create(validated_data)
        
        # Log rule creation
        from apps.core.models import ActivityLog
        ActivityLog.objects.create(
            user=self.context['request'].user,
            institution=rule.institution,
            action_type='create',
            action_description=f'Alert rule created: {rule.name}',
            severity='low'
        )
        
        return rule

    def update(self, instance, validated_data):
        """Update alert rule"""
        rule = super().update(instance, validated_data)
        
        # Log rule update
        from apps.core.models import ActivityLog
        ActivityLog.objects.create(
            user=self.context['request'].user,
            institution=rule.institution,
            action_type='update',
            action_description=f'Alert rule updated: {rule.name}',
            severity='low'
        )
        
        return rule


class BulkNotificationSerializer(serializers.Serializer):
    """
    Bulk notification serializer
    """
    title = serializers.CharField(max_length=200)
    message = serializers.TextField()
    notification_type = serializers.ChoiceField(choices=Notification.NOTIFICATION_TYPES)
    priority = serializers.ChoiceField(choices=Notification.PRIORITY_LEVELS, default='medium')
    
    # Recipients
    recipient_ids = serializers.ListField(child=serializers.UUIDField(), required=False)
    role_filter = serializers.ListField(child=serializers.CharField(), required=False)
    department_ids = serializers.ListField(child=serializers.UUIDField(), required=False)
    course_ids = serializers.ListField(child=serializers.UUIDField(), required=False)
    
    # Delivery options
    send_email = serializers.BooleanField(default=True)
    send_sms = serializers.BooleanField(default=False)
    send_push = serializers.BooleanField(default=True)
    
    # Scheduling
    send_immediately = serializers.BooleanField(default=True)
    scheduled_at = serializers.DateTimeField(required=False)
    
    # Additional options
    expires_at = serializers.DateTimeField(required=False)
    actions = serializers.JSONField(default=list)
    metadata = serializers.JSONField(default=dict)
    
    def validate(self, attrs):
        """Validate bulk notification"""
        # Check recipients
        recipients = attrs.get('recipient_ids', [])
        role_filter = attrs.get('role_filter', [])
        department_ids = attrs.get('department_ids', [])
        course_ids = attrs.get('course_ids', [])
        
        if not any([recipients, role_filter, department_ids, course_ids]):
            raise serializers.ValidationError("At least one recipient filter must be specified")
        
        # Validate scheduling
        if not attrs.get('send_immediately') and not attrs.get('scheduled_at'):
            raise serializers.ValidationError("Scheduled time is required when not sending immediately")
        
        # Validate scheduled time
        scheduled_at = attrs.get('scheduled_at')
        if scheduled_at and scheduled_at <= timezone.now():
            raise serializers.ValidationError("Scheduled time must be in the future")
        
        return attrs


class AlertActionSerializer(serializers.Serializer):
    """
    Alert action serializer
    """
    action = serializers.ChoiceField(choices=[
        ('acknowledge', 'Acknowledge'),
        ('resolve', 'Resolve'),
        ('escalate', 'Escalate'),
        ('dismiss', 'Dismiss'),
    ])
    notes = serializers.CharField(required=False, allow_blank=True, max_length=500)
    escalation_user_id = serializers.UUIDField(required=False)
    
    def validate(self, attrs):
        """Validate alert action"""
        action = attrs.get('action')
        
        if action == 'escalate' and not attrs.get('escalation_user_id'):
            raise serializers.ValidationError("Escalation user ID is required for escalate action")
        
        if action in ['resolve', 'dismiss'] and not attrs.get('notes'):
            raise serializers.ValidationError("Notes are required for resolve and dismiss actions")
        
        return attrs


class NotificationStatsSerializer(serializers.Serializer):
    """
    Notification statistics serializer
    """
    start_date = serializers.DateField()
    end_date = serializers.DateField()
    notification_type = serializers.CharField(required=False)
    recipient_id = serializers.UUIDField(required=False)
    
    def validate(self, attrs):
        """Validate statistics parameters"""
        start_date = attrs.get('start_date')
        end_date = attrs.get('end_date')
        
        if start_date and end_date:
            if start_date > end_date:
                raise serializers.ValidationError("Start date cannot be after end date")
            
            # Check date range is not too large
            if (end_date - start_date).days > 365:
                raise serializers.ValidationError("Date range cannot exceed 1 year")
        
        return attrs


class AlertRuleTestSerializer(serializers.Serializer):
    """
    Alert rule test serializer
    """
    test_context = serializers.JSONField()
    dry_run = serializers.BooleanField(default=True)
    
    def validate_test_context(self, value):
        """Validate test context"""
        required_fields = ['event_type', 'value']
        
        for field in required_fields:
            if field not in value:
                raise serializers.ValidationError(f"Test context must include {field}")
        
        return value
