"""
Alerts signals for Attendrix
"""
from django.db.models.signals import post_save, pre_save, post_delete
from django.dispatch import receiver
from django.utils import timezone
from apps.alerts.models import (
    Alert, Notification, NotificationTemplate, NotificationPreference,
    NotificationQueue, AlertRule
)
from apps.alerts.tasks import (
    process_notification_queue, evaluate_alert_rules,
    send_bulk_notifications
)
from apps.core.models import ActivityLog
import logging

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Alert)
def alert_post_save(sender, instance, created, **kwargs):
    """
    Handle alert post-save operations
    """
    if created:
        # Log alert creation
        ActivityLog.objects.create(
            user=instance.created_by,
            institution=instance.institution,
            action_type='create',
            action_description=f'Alert created: {instance.title}',
            severity='medium'
        )
        
        # Process notifications based on alert settings
        if instance.send_in_app:
            _create_in_app_notifications(instance)
        
        if instance.send_email:
            _queue_email_notifications(instance)
        
        if instance.send_sms:
            _queue_sms_notifications(instance)
        
        if instance.send_push:
            _queue_push_notifications(instance)
        
        # Check for auto-resolution conditions
        if instance.auto_resolve and instance.auto_resolve_conditions:
            _check_auto_resolution(instance)
        
        # Log severity-based actions
        if instance.severity in ['critical', 'urgent']:
            _handle_critical_alert(instance)
    
    else:
        # Log alert update
        ActivityLog.objects.create(
            user=instance.updated_by,
            institution=instance.institution,
            action_type='update',
            action_description=f'Alert updated: {instance.title}',
            severity='low'
        )


@receiver(post_save, sender=Notification)
def notification_post_save(sender, instance, created, **kwargs):
    """
    Handle notification post-save operations
    """
    if created:
        # Log notification creation
        ActivityLog.objects.create(
            user=None,  # Notifications can be system-generated
            institution=instance.institution,
            action_type='create',
            action_description=f'Notification created: {instance.title}',
            severity='low',
            metadata={
                'notification_id': instance.id,
                'recipient_id': instance.recipient.id,
                'notification_type': instance.notification_type
            }
        )
        
        # Add to queue for processing if delivery channels are specified
        channels = []
        if hasattr(instance, '_send_email') and instance._send_email:
            channels.append('email')
        if hasattr(instance, '_send_sms') and instance._send_sms:
            channels.append('sms')
        if hasattr(instance, '_send_push') and instance._send_push:
            channels.append('push')
        
        if channels:
            NotificationQueue.objects.create(
                institution=instance.institution,
                notification=instance,
                priority=instance.priority,
                channel_priority=channels
            )


@receiver(post_save, sender=NotificationTemplate)
def notification_template_post_save(sender, instance, created, **kwargs):
    """
    Handle notification template post-save operations
    """
    if created:
        # Log template creation
        ActivityLog.objects.create(
            user=instance.created_by,
            institution=instance.institution,
            action_type='create',
            action_description=f'Notification template created: {instance.name}',
            severity='low'
        )
    
    # Update usage if template is used
    if hasattr(instance, '_mark_as_used'):
        instance.usage_count += 1
        instance.last_used = timezone.now()
        instance.save()


@receiver(post_save, sender=NotificationPreference)
def notification_preference_post_save(sender, instance, created, **kwargs):
    """
    Handle notification preference post-save operations
    """
    if created:
        # Log preference creation
        ActivityLog.objects.create(
            user=instance.user,
            institution=instance.institution,
            action_type='create',
            action_description=f'Notification preferences created for {instance.user.get_full_name()}',
            severity='low'
        )
    else:
        # Log preference update
        ActivityLog.objects.create(
            user=instance.user,
            institution=instance.institution,
            action_type='update',
            action_description=f'Notification preferences updated for {instance.user.get_full_name()}',
            severity='low'
        )


@receiver(post_save, sender=NotificationQueue)
def notification_queue_post_save(sender, instance, created, **kwargs):
    """
    Handle notification queue post-save operations
    """
    if created:
        # Log queue entry creation
        ActivityLog.objects.create(
            user=None,
            institution=instance.institution,
            action_type='create',
            action_description=f'Notification queued: {instance.notification.title}',
            severity='low',
            metadata={
                'queue_id': instance.id,
                'notification_id': instance.notification.id,
                'priority': instance.priority,
                'channels': instance.channel_priority
            }
        )
        
        # Trigger queue processing if needed
        if instance.priority == 'urgent':
            # Process immediately for urgent notifications
            process_notification_queue.delay(instance.institution.id)


@receiver(post_save, sender=AlertRule)
def alert_rule_post_save(sender, instance, created, **kwargs):
    """
    Handle alert rule post-save operations
    """
    if created:
        # Log rule creation
        ActivityLog.objects.create(
            user=instance.created_by,
            institution=instance.institution,
            action_type='create',
            action_description=f'Alert rule created: {instance.name}',
            severity='low'
        )
        
        # Trigger rule evaluation if active
        if instance.is_active:
            evaluate_alert_rules.delay(instance.institution.id)
    
    else:
        # Log rule update
        ActivityLog.objects.create(
            user=instance.updated_by,
            institution=instance.institution,
            action_type='update',
            action_description=f'Alert rule updated: {instance.name}',
            severity='low'
        )


def _create_in_app_notifications(alert):
    """Create in-app notifications for alert"""
    recipients = _get_alert_recipients(alert)
    
    for recipient in recipients:
        # Check user preferences
        try:
            preferences = NotificationPreference.objects.get(
                user=recipient,
                institution=alert.institution
            )
            
            # Check if user wants in-app notifications
            if preferences.push_enabled and preferences.push_alerts:
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
                    },
                    _send_in_app=True
                )
        except NotificationPreference.DoesNotExist:
            # Create default notification if no preferences exist
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
                },
                _send_in_app=True
            )


def _queue_email_notifications(alert):
    """Queue email notifications for alert"""
    recipients = _get_alert_recipients(alert)
    
    for recipient in recipients:
        # Check user preferences
        try:
            preferences = NotificationPreference.objects.get(
                user=recipient,
                institution=alert.institution
            )
            
            # Check if user wants email notifications
            if preferences.email_enabled and preferences.email_alerts:
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
                    },
                    _send_email=True
                )
                
                NotificationQueue.objects.create(
                    institution=alert.institution,
                    notification=notification,
                    priority=alert.severity,
                    channel_priority=['email']
                )
        except NotificationPreference.DoesNotExist:
            # Create default notification if no preferences exist
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
                },
                _send_email=True
            )
            
            NotificationQueue.objects.create(
                institution=alert.institution,
                notification=notification,
                priority=alert.severity,
                channel_priority=['email']
            )


def _queue_sms_notifications(alert):
    """Queue SMS notifications for alert"""
    recipients = _get_alert_recipients(alert)
    
    for recipient in recipients:
        # Check user preferences
        try:
            preferences = NotificationPreference.objects.get(
                user=recipient,
                institution=alert.institution
            )
            
            # Check if user wants SMS notifications
            if preferences.sms_enabled and preferences.sms_alerts:
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
                    },
                    _send_sms=True
                )
                
                NotificationQueue.objects.create(
                    institution=alert.institution,
                    notification=notification,
                    priority=alert.severity,
                    channel_priority=['sms']
                )
        except NotificationPreference.DoesNotExist:
            # SMS requires explicit opt-in, so skip if no preferences
            pass


def _queue_push_notifications(alert):
    """Queue push notifications for alert"""
    recipients = _get_alert_recipients(alert)
    
    for recipient in recipients:
        # Check user preferences
        try:
            preferences = NotificationPreference.objects.get(
                user=recipient,
                institution=alert.institution
            )
            
            # Check if user wants push notifications
            if preferences.push_enabled and preferences.push_alerts:
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
                    },
                    _send_push=True
                )
                
                NotificationQueue.objects.create(
                    institution=alert.institution,
                    notification=notification,
                    priority=alert.severity,
                    channel_priority=['push']
                )
        except NotificationPreference.DoesNotExist:
            # Create default notification if no preferences exist
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
                },
                _send_push=True
            )
            
            NotificationQueue.objects.create(
                institution=alert.institution,
                notification=notification,
                priority=alert.severity,
                channel_priority=['push']
            )


def _get_alert_recipients(alert):
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
        email_users = User.objects.filter(email__in=alert.email_recipients)
        recipients.extend(email_users)
    
    # Remove duplicates and return
    return list(set(recipients))


def _check_auto_resolution(alert):
    """Check if alert should be auto-resolved"""
    conditions = alert.auto_resolve_conditions
    
    if not conditions:
        return
    
    # Check various auto-resolution conditions
    should_resolve = False
    
    # Example: Auto-resolve if threshold is no longer exceeded
    if conditions.get('threshold_check'):
        # This would check if the condition that triggered the alert is still valid
        # For now, just log the check
        logger.info(f"Checking auto-resolution conditions for alert {alert.id}")
    
    # Example: Auto-resolve after time period
    if conditions.get('time_based'):
        time_minutes = conditions.get('time_minutes', 60)
        resolve_time = alert.created_at + timedelta(minutes=time_minutes)
        
        if timezone.now() >= resolve_time:
            should_resolve = True
    
    if should_resolve:
        alert.resolve(None, "Auto-resolved based on conditions")


def _handle_critical_alert(alert):
    """
    Handle critical/urgent alerts with special processing
    """
    # Immediate notification processing
    process_notification_queue.delay(alert.institution.id)
    
    # Check for escalation rules
    if alert.escalation_level == 0:  # Not yet escalated
        # Check if immediate escalation is needed
        _check_immediate_escalation(alert)
    
    # Create system log entry
    logger.critical(f"Critical alert triggered: {alert.title} - {alert.description}")


def _check_immediate_escalation(alert):
    """
    Check if critical alert needs immediate escalation
    """
    # Look for escalation rules that apply to this alert type
    escalation_rules = AlertRule.objects.filter(
        institution=alert.institution,
        alert_type=alert.alert_type,
        is_active=True,
        auto_escalate=True,
        escalation_threshold=1  # Immediate escalation
    )
    
    for rule in escalation_rules:
        # Check if rule applies to this alert
        if _rule_applies_to_alert(rule, alert):
            escalation_user = _get_escalation_user(alert, rule)
            
            if escalation_user:
                alert.escalate(escalation_user, "Immediate escalation for critical alert")
                break


def _rule_applies_to_alert(rule, alert):
    """
    Check if alert rule applies to specific alert
    """
    # Check target matching
    if rule.target_users.filter(id=alert.student.id if alert.student else None).exists():
        return True
    
    if rule.target_courses.filter(id=alert.course.id if alert.course else None).exists():
        return True
    
    if rule.target_departments.filter(id=alert.department.id if alert.department else None).exists():
        return True
    
    return False


def _get_escalation_user(alert, rule):
    """
    Get user to escalate alert to based on rule
    """
    if rule.escalation_role:
        from apps.users.models import User
        escalation_users = User.objects.filter(
            institution=alert.institution,
            role=rule.escalation_role,
            is_active=True
        ).order_by('last_login')  # Most recently active first
        
        return escalation_users.first()
    
    return None


# Import Q for database queries
from django.db.models import Q
