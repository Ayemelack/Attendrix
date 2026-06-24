"""
Authentication signals for Attendrix
"""
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.utils import timezone
from apps.users.models import User, UserProfile
from apps.authentication.models import LoginAttempt, SecurityEvent
from apps.core.models import ActivityLog, SecurityLog
import logging

logger = logging.getLogger(__name__)


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """
    Create user profile when user is created
    """
    if created:
        UserProfile.objects.get_or_create(user=instance)
        logger.info(f"Created profile for user: {instance.email}")


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    """
    Save user profile when user is saved
    """
    if hasattr(instance, 'profile'):
        instance.profile.save()


@receiver(user_logged_in)
def log_user_login(sender, request, user, **kwargs):
    """
    Log successful user login
    """
    ip_address = get_client_ip(request)
    user_agent = request.META.get('HTTP_USER_AGENT', '')
    
    # Log activity
    ActivityLog.objects.create(
        user=user,
        institution=user.institution,
        action_type='login',
        action_description='User logged in successfully',
        ip_address=ip_address,
        user_agent=user_agent,
        severity='low'
    )
    
    # Update last login
    user.last_login = timezone.now()
    user.update_last_active()
    user.save(update_fields=['last_login'])
    
    logger.info(f"User logged in: {user.email} from {ip_address}")


@receiver(user_logged_out)
def log_user_logout(sender, request, user, **kwargs):
    """
    Log user logout
    """
    if user:
        ip_address = get_client_ip(request)
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        
        # Log activity
        ActivityLog.objects.create(
            user=user,
            institution=user.institution,
            action_type='logout',
            action_description='User logged out',
            ip_address=ip_address,
            user_agent=user_agent,
            severity='low'
        )
        
        logger.info(f"User logged out: {user.email}")


@receiver(pre_save, sender=User)
def track_password_changes(sender, instance, **kwargs):
    """
    Track password changes for security
    """
    if instance.pk:
        try:
            old_user = User.objects.get(pk=instance.pk)
            if old_user.password != instance.password:
                # Password is being changed
                instance.password_changed_at = timezone.now()
                
                # Log security event
                SecurityLog.objects.create(
                    user=instance,
                    institution=instance.institution,
                    event_type='password_change',
                    event_description='User password was changed',
                    risk_score=20,
                    metadata={'password_changed_at': instance.password_changed_at}
                )
                
                logger.info(f"Password changed for user: {instance.email}")
        except User.DoesNotExist:
            pass


@receiver(post_save, sender=LoginAttempt)
def monitor_suspicious_activity(sender, instance, created, **kwargs):
    """
    Monitor for suspicious login activity
    """
    if created and instance.status == 'failed':
        # Check for brute force attempts
        recent_failures = LoginAttempt.objects.filter(
            user=instance.user,
            status='failed',
            created_at__gte=timezone.now() - timezone.timedelta(minutes=30)
        ).count()
        
        if recent_failures >= 5:
            # Potential brute force attack
            SecurityEvent.objects.create(
                user=instance.user,
                institution=instance.institution,
                event_type='brute_force',
                severity='high',
                description=f'Brute force attack detected: {recent_failures} failed attempts',
                ip_address=instance.ip_address,
                risk_score=80,
                metadata={
                    'failed_attempts': recent_failures,
                    'timeframe': '30 minutes'
                }
            )
            
            logger.warning(f"Brute force attack detected for user: {instance.user.email if instance.user else 'Unknown'}")


@receiver(post_save, sender=SecurityEvent)
def handle_security_events(sender, instance, created, **kwargs):
    """
    Handle security events for alerting and response
    """
    if created:
        if instance.severity in ['high', 'critical']:
            # High severity security event - take immediate action
            
            # Log to security log
            SecurityLog.objects.create(
                user=instance.user,
                institution=instance.institution,
                event_type='security_event',
                event_description=instance.description,
                ip_address=instance.ip_address,
                risk_score=instance.risk_score,
                metadata={
                    'security_event_id': instance.id,
                    'event_type': instance.event_type,
                    'severity': instance.severity
                }
            )
            
            # Could trigger additional security measures here
            # - Block IP address
            # - Lock user account
            # - Send alerts to administrators
            # - Enable additional monitoring
            
            logger.error(f"High severity security event: {instance.event_type} - {instance.description}")


def get_client_ip(request):
    """
    Get client IP address from request
    """
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


@receiver(post_save, sender=User)
def monitor_account_locks(sender, instance, **kwargs):
    """
    Monitor account lock events
    """
    if hasattr(instance, '_was_locked'):
        if instance._was_locked and not instance.is_account_locked:
            # Account was unlocked
            ActivityLog.objects.create(
                user=instance,
                institution=instance.institution,
                action_type='update',
                action_description='User account was unlocked',
                severity='medium'
            )
            
            logger.info(f"Account unlocked: {instance.email}")


# Signal to track if user was locked before save
@receiver(pre_save, sender=User)
def track_lock_status(sender, instance, **kwargs):
    """
    Track account lock status changes
    """
    if instance.pk:
        try:
            old_user = User.objects.get(pk=instance.pk)
            instance._was_locked = old_user.is_account_locked
        except User.DoesNotExist:
            instance._was_locked = False
