"""
Alerts tasks for Attendrix - Background processing for notifications and alerts
"""
from celery import shared_task
from django.utils import timezone
from django.db.models import Q, Count
from django.core.mail import send_mail
from django.conf import settings
from datetime import datetime, timedelta
from apps.core.models import ActivityLog
from apps.alerts.models import (
    Alert, Notification, NotificationTemplate, NotificationQueue,
    NotificationPreference, AlertRule
)
from apps.users.models import User
import logging

logger = logging.getLogger(__name__)


@shared_task
def process_notification_queue(institution_id):
    """
    Process pending notifications in queue
    """
    try:
        # Get pending notifications
        pending_notifications = NotificationQueue.objects.filter(
            institution_id=institution_id,
            status='pending',
            next_attempt_at__lte=timezone.now()
        ).order_by('-priority', 'created_at')
        
        processed_count = 0
        
        for queue_entry in pending_notifications:
            notification = queue_entry.notification
            success = False
            
            # Try each channel in priority order
            for channel in queue_entry.channel_priority:
                try:
                    if channel == 'email':
                        success = notification.send_email()
                    elif channel == 'sms':
                        success = notification.send_sms()
                    elif channel == 'push':
                        success = notification.send_push()
                    elif channel == 'in_app':
                        # In-app notifications are already created
                        success = True
                    
                    if success:
                        break
                        
                except Exception as e:
                    logger.error(f"Error sending {channel} notification {notification.id}: {e}")
            
            if success:
                queue_entry.mark_as_sent()
                processed_count += 1
            else:
                queue_entry.increment_attempts()
                
                # Mark as failed if max attempts reached
                if queue_entry.attempts >= queue_entry.max_attempts:
                    queue_entry.mark_as_failed("Max attempts reached")
        
        logger.info(f"Processed {processed_count} notifications for institution {institution_id}")
        return processed_count
        
    except Exception as e:
        logger.error(f"Error processing notification queue: {e}")
        return 0


@shared_task
def send_bulk_notifications(notification_data):
    """
    Send bulk notifications
    """
    try:
        institution_id = notification_data['institution_id']
        created_by_id = notification_data['created_by_id']
        
        # Get recipients
        recipients = _get_bulk_notification_recipients(notification_data)
        
        if not recipients:
            logger.warning("No recipients found for bulk notification")
            return 0
        
        notifications_created = 0
        
        # Create notifications for each recipient
        for recipient in recipients:
            # Check notification preferences
            preferences = _get_user_notification_preferences(recipient)
            
            if _should_send_notification(notification_data, preferences):
                notification = Notification.objects.create(
                    institution_id=institution_id,
                    recipient=recipient,
                    title=notification_data['title'],
                    message=notification_data['message'],
                    notification_type=notification_data['notification_type'],
                    priority=notification_data['priority'],
                    actions=notification_data.get('actions', []),
                    metadata=notification_data.get('metadata', {}),
                    expires_at=notification_data.get('expires_at')
                )
                
                # Add to queue for processing
                channels = _get_delivery_channels(notification_data, preferences)
                if channels:
                    NotificationQueue.objects.create(
                        institution_id=institution_id,
                        notification=notification,
                        priority=notification_data['priority'],
                        channel_priority=channels
                    )
                
                notifications_created += 1
        
        logger.info(f"Created {notifications_created} bulk notifications")
        return notifications_created
        
    except Exception as e:
        logger.error(f"Error sending bulk notifications: {e}")
        return 0


def _get_bulk_notification_recipients(notification_data):
    """Get recipients for bulk notification"""
    recipients = []
    
    # Direct recipients
    if notification_data.get('recipient_ids'):
        recipients.extend(User.objects.filter(
            id__in=notification_data['recipient_ids'],
            is_active=True
        ))
    
    # Role-based recipients
    if notification_data.get('role_filter'):
        recipients.extend(User.objects.filter(
            role__in=notification_data['role_filter'],
            is_active=True
        ))
    
    # Department-based recipients
    if notification_data.get('department_ids'):
        from apps.departments.models import Department
        departments = Department.objects.filter(
            id__in=notification_data['department_ids']
        )
        
        for dept in departments:
            recipients.extend(User.objects.filter(
                department=dept,
                is_active=True
            ))
    
    # Course-based recipients
    if notification_data.get('course_ids'):
        from apps.courses.models import Course, CourseEnrollment
        courses = Course.objects.filter(
            id__in=notification_data['course_ids']
        )
        
        for course in courses:
            enrolled_users = User.objects.filter(
                courseenrollments__course=course,
                courseenrollments__status='enrolled',
                is_active=True
            )
            recipients.extend(enrolled_users)
    
    # Remove duplicates
    return list(set(recipients))


def _get_user_notification_preferences(user):
    """Get user's notification preferences"""
    preference, created = NotificationPreference.objects.get_or_create(
        user=user,
        institution=user.institution
    )
    return preference


def _should_send_notification(notification_data, preferences):
    """Check if notification should be sent based on preferences"""
    notification_type = notification_data['notification_type']
    priority = notification_data['priority']
    
    # Check quiet hours
    if preferences.quiet_hours_enabled:
        current_time = timezone.now().time()
        start_time = preferences.quiet_hours_start
        end_time = preferences.quiet_hours_end
        
        # Handle overnight quiet hours (e.g., 22:00 to 08:00)
        if start_time > end_time:
            if current_time >= start_time or current_time <= end_time:
                # Only allow urgent notifications during quiet hours
                if priority != 'urgent':
                    return False
        else:
            # Same day quiet hours
            if start_time <= current_time <= end_time:
                # Only allow urgent notifications during quiet hours
                if priority != 'urgent':
                    return False
    
    # Check frequency limits
    if _exceeds_frequency_limits(user, preferences):
        return False
    
    return True


def _exceeds_frequency_limits(user, preferences):
    """Check if user has exceeded notification frequency limits"""
    now = timezone.now()
    
    # Check hourly limit
    hour_ago = now - timedelta(hours=1)
    hour_count = Notification.objects.filter(
        recipient=user,
        created_at__gte=hour_ago
    ).count()
    
    if hour_count >= preferences.max_notifications_per_hour:
        return True
    
    # Check daily limit
    day_ago = now - timedelta(days=1)
    day_count = Notification.objects.filter(
        recipient=user,
        created_at__gte=day_ago
    ).count()
    
    if day_count >= preferences.max_notifications_per_day:
        return True
    
    return False


def _get_delivery_channels(notification_data, preferences):
    """Get delivery channels based on notification data and preferences"""
    channels = []
    
    # Check if user wants email notifications
    if notification_data.get('send_email') and preferences.email_enabled:
        # Check specific email preferences
        notification_type = notification_data['notification_type']
        
        if (notification_type == 'attendance_reminder' and preferences.email_attendance_reminders) or \
           (notification_type == 'alert' and preferences.email_alerts) or \
           (notification_type == 'announcement' and preferences.email_announcements) or \
           (notification_type == 'grade_posted' and preferences.email_grades) or \
           (notification_type == 'schedule_change' and preferences.email_schedule_changes):
            channels.append('email')
    
    # Check SMS notifications
    if notification_data.get('send_sms') and preferences.sms_enabled:
        notification_type = notification_data['notification_type']
        
        if (notification_type == 'attendance_reminder' and preferences.sms_attendance_reminders) or \
           (notification_type == 'alert' and preferences.sms_alerts):
            channels.append('sms')
    
    # Check push notifications
    if notification_data.get('send_push') and preferences.push_enabled:
        notification_type = notification_data['notification_type']
        
        if (notification_type == 'attendance_reminder' and preferences.push_attendance_reminders) or \
           (notification_type == 'alert' and preferences.push_alerts) or \
           (notification_type == 'announcement' and preferences.push_announcements):
            channels.append('push')
    
    # Always include in-app
    channels.append('in_app')
    
    return channels


@shared_task
def evaluate_alert_rules(institution_id):
    """
    Evaluate all active alert rules
    """
    try:
        # Get active rules
        active_rules = AlertRule.objects.filter(
            institution_id=institution_id,
            is_active=True,
            is_deleted=False
        )
        
        rules_evaluated = 0
        alerts_triggered = 0
        
        for rule in active_rules:
            try:
                # Get context data for rule evaluation
                context = _get_rule_context(rule)
                
                if context:
                    # Evaluate rule condition
                    if rule.evaluate_condition(context):
                        # Trigger alert
                        alert_created = rule.trigger_alert(context)
                        if alert_created:
                            alerts_triggered += 1
                    
                    rules_evaluated += 1
                
            except Exception as e:
                logger.error(f"Error evaluating alert rule {rule.id}: {e}")
        
        logger.info(f"Evaluated {rules_evaluated} rules, triggered {alerts_triggered} alerts for institution {institution_id}")
        return alerts_triggered
        
    except Exception as e:
        logger.error(f"Error evaluating alert rules: {e}")
        return 0


def _get_rule_context(rule):
    """
    Get context data for rule evaluation
    """
    context = {}
    
    # Handle different rule types
    if rule.rule_type == 'threshold':
        context = _get_threshold_context(rule)
    elif rule.rule_type == 'event':
        context = _get_event_context(rule)
    elif rule.rule_type == 'schedule':
        context = _get_schedule_context(rule)
    elif rule.rule_type == 'pattern':
        context = _get_pattern_context(rule)
    
    return context


def _get_threshold_context(rule):
    """Get context for threshold-based rules"""
    context = {}
    
    # Example: Attendance threshold
    if rule.alert_type == 'attendance_low':
        from apps.attendance.models import AttendanceAnalytics
        
        # Get recent attendance analytics
        recent_analytics = AttendanceAnalytics.objects.filter(
            institution=rule.institution,
            analytics_type='student',
            reference_date=timezone.now().date() - timedelta(days=1)
        ).aggregate(
            avg_attendance=Avg('attendance_rate'),
            min_attendance=Avg('attendance_rate', function='MIN')
        )
        
        context.update({
            'event_type': 'attendance_threshold_check',
            'value': recent_analytics.get('avg_attendance', 0),
            'min_value': recent_analytics.get('min_attendance', 0)
        })
    
    return context


def _get_event_context(rule):
    """Get context for event-based rules"""
    context = {}
    
    # This would check for recent events that match trigger_events
    # For now, return empty context
    context.update({
        'event_type': 'check_events',
        'value': 0
    })
    
    return context


def _get_schedule_context(rule):
    """Get context for schedule-based rules"""
    context = {}
    
    # This would check if scheduled conditions are met
    # For now, return empty context
    context.update({
        'event_type': 'schedule_check',
        'value': 0
    })
    
    return context


def _get_pattern_context(rule):
    """Get context for pattern-based rules"""
    context = {}
    
    # This would analyze patterns and return context
    # For now, return empty context
    context.update({
        'event_type': 'pattern_check',
        'value': 0
    })
    
    return context


@shared_task
def cleanup_expired_notifications():
    """
    Clean up expired notifications and queue entries
    """
    try:
        from apps.institutions.models import Institution
        institutions = Institution.objects.filter(is_active=True)
        
        cleaned_count = 0
        
        for institution in institutions:
            # Clean up expired notifications
            expired_notifications = Notification.objects.filter(
                institution=institution,
                expires_at__lt=timezone.now()
            ).delete()
            
            cleaned_count += expired_notifications
            
            # Clean up old queue entries (older than 7 days)
            cutoff_date = timezone.now() - timedelta(days=7)
            old_queue_entries = NotificationQueue.objects.filter(
                institution=institution,
                created_at__lt=cutoff_date,
                status__in=['sent', 'failed']
            ).delete()
            
            cleaned_count += old_queue_entries
        
        logger.info(f"Cleaned up {cleaned_count} expired notifications and queue entries")
        return cleaned_count
        
    except Exception as e:
        logger.error(f"Error cleaning up expired notifications: {e}")
        return 0


@shared_task
def send_daily_digest():
    """
    Send daily notification digest
    """
    try:
        from apps.institutions.models import Institution
        institutions = Institution.objects.filter(is_active=True)
        
        digests_sent = 0
        
        for institution in institutions:
            # Get users who want daily digest
            users_with_digest = User.objects.filter(
                institution=institution,
                is_active=True,
                notificationpreferences__email_announcements=True
            )
            
            for user in users_with_digest:
                # Get daily statistics
                today = timezone.now().date()
                yesterday = today - timedelta(days=1)
                
                stats = {
                    'new_notifications': Notification.objects.filter(
                        recipient=user,
                        created_at__date=yesterday,
                        in_app_read=False
                    ).count(),
                    'alerts_resolved': Alert.objects.filter(
                        institution=institution,
                        resolved_at__date=yesterday
                    ).count(),
                    'unread_count': Notification.objects.filter(
                        recipient=user,
                        in_app_read=False
                    ).exclude(expires_at__lt=timezone.now()).count()
                }
                
                # Create digest notification
                if stats['new_notifications'] > 0 or stats['unread_count'] > 0:
                    notification = Notification.objects.create(
                        institution=institution,
                        recipient=user,
                        title='Daily Digest',
                        message=_format_daily_digest_message(stats),
                        notification_type='system_update',
                        priority='low'
                    )
                    
                    # Queue for email delivery
                    NotificationQueue.objects.create(
                        institution=institution,
                        notification=notification,
                        priority='low',
                        channel_priority=['email']
                    )
                    
                    digests_sent += 1
        
        logger.info(f"Sent {digests_sent} daily digests")
        return digests_sent
        
    except Exception as e:
        logger.error(f"Error sending daily digest: {e}")
        return 0


def _format_daily_digest_message(stats):
    """Format daily digest message"""
    message = f"Daily Attendance System Digest\n\n"
    
    if stats['new_notifications'] > 0:
        message += f"• {stats['new_notifications']} new notifications yesterday\n"
    
    if stats['alerts_resolved'] > 0:
        message += f"• {stats['alerts_resolved']} alerts resolved yesterday\n"
    
    if stats['unread_count'] > 0:
        message += f"• {stats['unread_count']} unread notifications total\n"
    
    message += f"\nVisit your dashboard to view details."
    
    return message


@shared_task
def check_alert_escalations():
    """
    Check for alerts that need escalation
    """
    try:
        from apps.institutions.models import Institution
        institutions = Institution.objects.filter(is_active=True)
        
        escalations_processed = 0
        
        for institution in institutions:
            # Get active alerts with escalation rules
            alerts_to_check = Alert.objects.filter(
                institution=institution,
                is_active=True,
                status='active',
                escalation_level__lt=5
            ).select_related('alert_rule')
            
            for alert in alerts_to_check:
                # Check if alert has associated rule with auto-escalation
                if hasattr(alert, 'alert_rule') and alert.alert_rule:
                    rule = alert.alert_rule
                    
                    if rule.auto_escalate and alert.trigger_count >= rule.escalation_threshold:
                        # Escalate alert
                        escalation_user = _get_escalation_user(alert, rule)
                        
                        if escalation_user:
                            alert.escalate(escalation_user, f"Auto-escalated after {alert.trigger_count} triggers")
                            escalations_processed += 1
        
        logger.info(f"Processed {escalations_processed} alert escalations")
        return escalations_processed
        
    except Exception as e:
        logger.error(f"Error checking alert escalations: {e}")
        return 0


def _get_escalation_user(alert, rule):
    """Get user to escalate alert to"""
    if rule.escalation_role:
        from apps.users.models import User
        escalation_users = User.objects.filter(
            institution=alert.institution,
            role=rule.escalation_role,
            is_active=True
        ).order_by('last_login')  # Most recently active first
        
        return escalation_users.first()
    
    return None


@shared_task
def update_notification_templates():
    """
    Update notification templates usage statistics
    """
    try:
        from apps.institutions.models import Institution
        institutions = Institution.objects.filter(is_active=True)
        
        templates_updated = 0
        
        for institution in institutions:
            # Update usage counts for templates
            templates = NotificationTemplate.objects.filter(institution=institution)
            
            for template in templates:
                # Count recent usage
                recent_usage = Notification.objects.filter(
                    institution=institution,
                    created_at__gte=timezone.now() - timedelta(days=30),
                    notification_type=template.template_type
                ).count()
                
                if template.usage_count != recent_usage:
                    template.usage_count = recent_usage
                    template.last_used = timezone.now()
                    template.save()
                    templates_updated += 1
        
        logger.info(f"Updated usage statistics for {templates_updated} notification templates")
        return templates_updated
        
    except Exception as e:
        logger.error(f"Error updating notification templates: {e}")
        return 0
