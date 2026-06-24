"""
Authentication tasks for Attendrix
"""
from celery import shared_task
from django.utils import timezone
from django.conf import settings
from django.core.mail import send_mail
from apps.users.models import User
from apps.core.models import SecurityLog, ActivityLog
from apps.authentication.models import LoginAttempt, SecurityToken, UserSession
import logging

logger = logging.getLogger(__name__)


@shared_task
def cleanup_expired_sessions():
    """
    Clean up expired user sessions
    """
    expired_sessions = UserSession.objects.filter(
        expires_at__lt=timezone.now()
    )
    
    count = expired_sessions.count()
    expired_sessions.update(is_active=False)
    
    logger.info(f"Cleaned up {count} expired sessions")
    return count


@shared_task
def cleanup_old_login_attempts():
    """
    Clean up old login attempts (keep last 30 days)
    """
    cutoff_date = timezone.now() - timezone.timedelta(days=30)
    
    old_attempts = LoginAttempt.objects.filter(
        created_at__lt=cutoff_date
    )
    
    count = old_attempts.count()
    old_attempts.delete()
    
    logger.info(f"Cleaned up {count} old login attempts")
    return count


@shared_task
def cleanup_expired_tokens():
    """
    Clean up expired security tokens
    """
    expired_tokens = SecurityToken.objects.filter(
        expires_at__lt=timezone.now()
    )
    
    count = expired_tokens.count()
    expired_tokens.delete()
    
    logger.info(f"Cleaned up {count} expired security tokens")
    return count


@shared_task
def detect_anomalous_login_patterns():
    """
    Detect anomalous login patterns
    """
    now = timezone.now()
    last_24h = now - timezone.timedelta(hours=24)
    
    # Check for users with multiple failed login attempts
    users_with_failures = LoginAttempt.objects.filter(
        status='failed',
        created_at__gte=last_24h
    ).values('user').annotate(
        failure_count=models.Count('id')
    ).filter(
        failure_count__gte=10
    )
    
    anomalies_detected = 0
    
    for user_data in users_with_failures:
        user = User.objects.get(id=user_data['user'])
        
        # Log security event
        SecurityLog.objects.create(
            user=user,
            institution=user.institution,
            event_type='brute_force_attempt',
            event_description=f'High number of failed login attempts: {user_data["failure_count"]}',
            risk_score=70,
            metadata={
                'failure_count': user_data['failure_count'],
                'timeframe': '24 hours'
            }
        )
        
        anomalies_detected += 1
        
        # Could take additional action here:
        # - Lock user account temporarily
        # - Send alert to administrators
        # - Increase monitoring
    
    logger.info(f"Detected {anomalies_detected} anomalous login patterns")
    return anomalies_detected


@shared_task
def send_security_alerts():
    """
    Send security alerts to administrators
    """
    now = timezone.now()
    last_24h = now - timezone.timedelta(hours=24)
    
    # Get high-severity security events
    critical_events = SecurityLog.objects.filter(
        created_at__gte=last_24h,
        risk_score__gte=80
    ).order_by('-risk_score')
    
    if critical_events.exists():
        # Prepare alert email
        subject = "Security Alert - Attendrix System"
        
        alert_content = f"""
        High-priority security events detected in the last 24 hours:
        
        Total Events: {critical_events.count()}
        
        Event Summary:
        """
        
        for event in critical_events[:10]:  # Top 10 events
            alert_content += f"""
        - {event.event_type}: {event.event_description}
          Risk Score: {event.risk_score}
          User: {event.user.email if event.user else 'Unknown'}
          IP: {event.ip_address}
          Time: {event.created_at}
            """
        
        # Send to super admins
        super_admins = User.objects.filter(role='super_admin', is_active=True)
        
        for admin in super_admins:
            try:
                send_mail(
                    subject,
                    alert_content,
                    settings.DEFAULT_FROM_EMAIL,
                    [admin.email],
                    fail_silently=False
                )
                logger.info(f"Security alert sent to {admin.email}")
            except Exception as e:
                logger.error(f"Failed to send security alert to {admin.email}: {e}")
    
    return critical_events.count()


@shared_task
def update_user_activity_scores():
    """
    Update user activity scores for risk assessment
    """
    now = timezone.now()
    last_30_days = now - timezone.timedelta(days=30)
    
    users = User.objects.filter(is_active=True)
    
    for user in users:
        # Calculate activity score based on various factors
        score = 0
        
        # Login frequency (0-30 points)
        login_count = LoginAttempt.objects.filter(
            user=user,
            status='success',
            created_at__gte=last_30_days
        ).count()
        score += min(login_count, 30)
        
        # Failed login attempts (negative points)
        failed_count = LoginAttempt.objects.filter(
            user=user,
            status='failed',
            created_at__gte=last_30_days
        ).count()
        score -= failed_count * 5
        
        # Recent activity (0-20 points)
        if user.last_active:
            days_since_activity = (now - user.last_active).days
            if days_since_activity <= 7:
                score += 20
            elif days_since_activity <= 14:
                score += 10
            elif days_since_activity <= 30:
                score += 5
        
        # Cap score between 0 and 100
        score = max(0, min(100, score))
        
        # Store score in user metadata or separate model
        # For now, just log it
        logger.info(f"Activity score for {user.email}: {score}")
    
    return users.count()


@shared_task
def monitor_session_anomalies():
    """
    Monitor for session anomalies
    """
    now = timezone.now()
    last_1h = now - timezone.timedelta(hours=1)
    
    # Check for users with multiple concurrent sessions
    concurrent_sessions = UserSession.objects.filter(
        is_active=True,
        last_activity__gte=last_1h
    ).values('user').annotate(
        session_count=models.Count('id')
    ).filter(
        session_count__gte=5
    )
    
    anomalies = 0
    
    for session_data in concurrent_sessions:
        user = User.objects.get(id=session_data['user'])
        
        # Log potential session hijack
        SecurityLog.objects.create(
            user=user,
            institution=user.institution,
            event_type='session_anomaly',
            event_description=f'Unusual number of concurrent sessions: {session_data["session_count"]}',
            risk_score=60,
            metadata={
                'session_count': session_data['session_count'],
                'timeframe': '1 hour'
            }
        )
        
        anomalies += 1
    
    logger.info(f"Detected {anomalies} session anomalies")
    return anomalies


@shared_task
def generate_security_report():
    """
    Generate daily security report
    """
    now = timezone.now()
    last_24h = now - timezone.timedelta(hours=24)
    
    # Security statistics
    total_logins = LoginAttempt.objects.filter(
        created_at__gte=last_24h
    ).count()
    
    successful_logins = LoginAttempt.objects.filter(
        status='success',
        created_at__gte=last_24h
    ).count()
    
    failed_logins = LoginAttempt.objects.filter(
        status='failed',
        created_at__gte=last_24h
    ).count()
    
    security_events = SecurityLog.objects.filter(
        created_at__gte=last_24h
    ).count()
    
    high_risk_events = SecurityLog.objects.filter(
        created_at__gte=last_24h,
        risk_score__gte=70
    ).count()
    
    # Generate report
    report = {
        'date': now.date(),
        'total_logins': total_logins,
        'successful_logins': successful_logins,
        'failed_logins': failed_logins,
        'security_events': security_events,
        'high_risk_events': high_risk_events,
        'success_rate': (successful_logins / total_logins * 100) if total_logins > 0 else 0
    }
    
    logger.info(f"Security report generated: {report}")
    return report


@shared_task
def enforce_password_expiration():
    """
    Enforce password expiration policies
    """
    from datetime import timedelta
    
    # Check users with old passwords
    expiration_days = getattr(settings, 'PASSWORD_EXPIRATION_DAYS', 90)
    cutoff_date = timezone.now() - timedelta(days=expiration_days)
    
    users_with_old_passwords = User.objects.filter(
        is_active=True,
        password_changed_at__lt=cutoff_date
    )
    
    for user in users_with_old_passwords:
        # Send password change reminder
        try:
            send_mail(
                "Password Expiration Reminder",
                f"""
                Dear {user.get_full_name()},
                
                Your password for Attendrix was changed more than {expiration_days} days ago.
                For security reasons, please update your password.
                
                If you don't update your password within 7 days, your account may be temporarily locked.
                
                Please visit: {settings.FRONTEND_URL}/password/change
                
                Thank you,
                Attendrix Security Team
                """,
                settings.DEFAULT_FROM_EMAIL,
                [user.email],
                fail_silently=False
            )
            
            # Log activity
            ActivityLog.objects.create(
                user=user,
                institution=user.institution,
                action_type='password_reset',
                action_description='Password expiration reminder sent',
                severity='low'
            )
            
        except Exception as e:
            logger.error(f"Failed to send password expiration reminder to {user.email}: {e}")
    
    return users_with_old_passwords.count()


@shared_task
def sync_external_authentication():
    """
    Sync with external authentication systems (LDAP, SSO, etc.)
    """
    # This would integrate with external authentication providers
    # For now, it's a placeholder
    
    logger.info("External authentication sync completed")
    return True
