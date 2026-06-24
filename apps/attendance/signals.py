"""
Attendance signals for Attendrix
"""
from django.db.models.signals import post_save, pre_save, post_delete
from django.dispatch import receiver
from django.utils import timezone
from apps.attendance.models import AttendanceSession, AttendanceRecord, AttendanceAlert
from apps.core.models import ActivityLog, SecurityLog
from apps.attendance.tasks import generate_attendance_analytics, detect_attendance_anomalies
import logging

logger = logging.getLogger(__name__)


@receiver(post_save, sender=AttendanceSession)
def attendance_session_post_save(sender, instance, created, **kwargs):
    """
    Handle attendance session post-save operations
    """
    if created:
        # Log session creation
        ActivityLog.objects.create(
            user=instance.created_by,
            institution=instance.institution,
            action_type='create',
            action_description=f'Attendance session created: {instance.title}',
            severity='low'
        )
        
        # Schedule reminder if session is in the future
        if instance.start_time > timezone.now():
            from apps.attendance.tasks import send_attendance_reminders
            # Schedule reminder for 15 minutes before session
            reminder_time = instance.start_time - timezone.timedelta(minutes=15)
            if reminder_time > timezone.now():
                send_attendance_reminders.apply_async(eta=reminder_time)
    else:
        # Log session update
        ActivityLog.objects.create(
            user=instance.updated_by,
            institution=instance.institution,
            action_type='update',
            action_description=f'Attendance session updated: {instance.title}',
            severity='low'
        )
        
        # Check if session was activated/deactivated
        if hasattr(instance, '_old_is_active'):
            if instance._old_is_active != instance.is_active:
                action = 'activated' if instance.is_active else 'deactivated'
                ActivityLog.objects.create(
                    user=instance.updated_by,
                    institution=instance.institution,
                    action_type='update',
                    action_description=f'Attendance session {action}: {instance.title}',
                    severity='medium'
                )


@receiver(pre_save, sender=AttendanceSession)
def attendance_session_pre_save(sender, instance, **kwargs):
    """
    Handle attendance session pre-save operations
    """
    if instance.pk:
        # Store old value for comparison
        try:
            old_instance = AttendanceSession.objects.get(pk=instance.pk)
            instance._old_is_active = old_instance.is_active
        except AttendanceSession.DoesNotExist:
            pass


@receiver(post_save, sender=AttendanceRecord)
def attendance_record_post_save(sender, instance, created, **kwargs):
    """
    Handle attendance record post-save operations
    """
    if created:
        # Log attendance marking
        ActivityLog.objects.create(
            user=instance.student,
            institution=instance.institution,
            action_type='attendance_mark',
            action_description=f'Attendance marked for {instance.session.title}',
            ip_address=instance.ip_address,
            user_agent=instance.user_agent,
            device_fingerprint=instance.device_fingerprint,
            severity='low'
        )
        
        # Update session statistics
        session = instance.session
        stats = session.attendance_records.filter(is_deleted=False).aggregate(
            present=Count('id', filter=Q(status='present')),
            absent=Count('id', filter=Q(status='absent')),
            late=Count('id', filter=Q(status='late')),
            excused=Count('id', filter=Q(status='excused'))
        )
        
        session.total_present = stats['present'] or 0
        session.total_absent = stats['absent'] or 0
        session.total_late = stats['late'] or 0
        session.total_excused = stats['excused'] or 0
        session.save()
        
        # Check for suspicious activity
        if instance.is_suspicious:
            # Log security event
            SecurityLog.objects.create(
                user=instance.student,
                institution=instance.institution,
                event_type='suspicious_activity',
                event_description=f'Suspicious attendance detected for {instance.student.get_full_name()}',
                ip_address=instance.ip_address,
                user_agent=instance.user_agent,
                device_fingerprint=instance.device_fingerprint,
                risk_score=100 - instance.verification_score,
                metadata={
                    'record_id': instance.id,
                    'verification_score': instance.verification_score,
                    'security_flags': instance.security_flags
                }
            )
            
            # Create alert
            AttendanceAlert.objects.get_or_create(
                institution=instance.institution,
                student=instance.student,
                session=instance.session,
                alert_type='suspicious_activity',
                severity='warning',
                defaults={
                    'title': 'Suspicious Attendance Detected',
                    'description': f'Suspicious attendance pattern detected for {instance.student.get_full_name()}',
                    'alert_data': {
                        'record_id': instance.id,
                        'verification_score': instance.verification_score,
                        'security_flags': instance.security_flags
                    }
                }
            )
        
        # Trigger anomaly detection for the student
        detect_attendance_anomalies.delay(instance.institution.id)
        
    else:
        # Log record update
        ActivityLog.objects.create(
            user=instance.updated_by,
            institution=instance.institution,
            action_type='update',
            action_description=f'Attendance record updated for {instance.student.get_full_name()}',
            severity='low'
        )


@receiver(post_delete, sender=AttendanceRecord)
def attendance_record_post_delete(sender, instance, **kwargs):
    """
    Handle attendance record post-delete operations
    """
    # Log deletion
    ActivityLog.objects.create(
        user=getattr(instance, 'deleted_by', None),
        institution=instance.institution,
        action_type='delete',
        action_description=f'Attendance record deleted for {instance.student.get_full_name()}',
        severity='medium'
    )
    
    # Update session statistics
    session = instance.session
    stats = session.attendance_records.filter(is_deleted=False).aggregate(
        present=Count('id', filter=Q(status='present')),
        absent=Count('id', filter=Q(status='absent')),
        late=Count('id', filter=Q(status='late')),
        excused=Count('id', filter=Q(status='excused'))
    )
    
    session.total_present = stats['present'] or 0
    session.total_absent = stats['absent'] or 0
    session.total_late = stats['late'] or 0
    session.total_excused = stats['excused'] or 0
    session.save()


@receiver(post_save, sender=AttendanceAlert)
def attendance_alert_post_save(sender, instance, created, **kwargs):
    """
    Handle attendance alert post-save operations
    """
    if created:
        # Log alert creation
        ActivityLog.objects.create(
            user=instance.created_by,
            institution=instance.institution,
            action_type='create',
            action_description=f'Attendance alert created: {instance.title}',
            severity='medium'
        )
        
        # Send notification to relevant users
        if instance.student:
            # Notify student if it's about them
            if instance.alert_type in ['low_attendance', 'pattern_anomaly']:
                from apps.alerts.models import Notification
                Notification.objects.create(
                    user=instance.student,
                    institution=instance.institution,
                    title=instance.title,
                    message=instance.description,
                    notification_type='attendance_alert',
                    metadata={
                        'alert_id': instance.id,
                        'alert_type': instance.alert_type
                    }
                )
        
        # Notify lecturers and admins
        if instance.alert_type in ['suspicious_activity', 'proxy_detection']:
            from apps.alerts.models import Notification
            from apps.users.models import User
            
            # Notify course lecturer
            if instance.session and instance.session.lecturer:
                Notification.objects.create(
                    user=instance.session.lecturer,
                    institution=instance.institution,
                    title=instance.title,
                    message=instance.description,
                    notification_type='attendance_alert',
                    metadata={
                        'alert_id': instance.id,
                        'alert_type': instance.alert_type
                    }
                )
            
            # Notify institution admins
            admins = User.objects.filter(
                institution=instance.institution,
                role='institution_admin'
            )
            
            for admin in admins:
                Notification.objects.create(
                    user=admin,
                    institution=instance.institution,
                    title=instance.title,
                    message=instance.description,
                    notification_type='attendance_alert',
                    metadata={
                        'alert_id': instance.id,
                        'alert_type': instance.alert_type
                    }
                )


@receiver(post_save, sender=AttendanceSession)
def generate_session_analytics(sender, instance, created, **kwargs):
    """
    Generate analytics when session is completed
    """
    if not created and not instance.is_active and instance.actual_end_time:
        # Session was closed, generate analytics
        generate_attendance_analytics.delay(instance.id)


@receiver(post_save, sender=AttendanceRecord)
def check_attendance_thresholds(sender, instance, created, **kwargs):
    """
    Check attendance thresholds and trigger alerts
    """
    if created:
        # Get attendance settings
        try:
            settings = AttendanceSettings.objects.get(institution=instance.institution)
            
            # Check student's attendance rate
            student_records = AttendanceRecord.objects.filter(
                student=instance.student,
                is_deleted=False
            )
            
            total_records = student_records.count()
            if total_records >= 5:  # Only check after 5 records
                present_count = student_records.filter(status='present').count()
                attendance_rate = (present_count / total_records) * 100
                
                # Check if below threshold
                if attendance_rate < settings.low_attendance_threshold:
                    # Create low attendance alert
                    AttendanceAlert.objects.get_or_create(
                        institution=instance.institution,
                        student=instance.student,
                        alert_type='low_attendance',
                        severity='warning',
                        defaults={
                            'title': 'Low Attendance Warning',
                            'description': f'Student attendance rate is {attendance_rate:.1f}% (below {settings.low_attendance_threshold}% threshold)',
                            'threshold_value=settings.low_attendance_threshold,
                            'actual_value': attendance_rate,
                            'alert_data': {
                                'attendance_rate': attendance_rate,
                                'total_records': total_records,
                                'present_count': present_count
                            }
                        }
                    )
        
        except AttendanceSettings.DoesNotExist:
            pass


@receiver(post_save, sender=AttendanceRecord)
def update_student_engagement_score(sender, instance, created, **kwargs):
    """
    Update student engagement score based on attendance
    """
    if created:
        # Get student's recent attendance
        recent_records = AttendanceRecord.objects.filter(
            student=instance.student,
            marked_at__gte=timezone.now() - timedelta(days=30),
            is_deleted=False
        )
        
        if recent_records.exists():
            # Calculate engagement score
            total_records = recent_records.count()
            present_count = recent_records.filter(status='present').count()
            on_time_count = recent_records.filter(
                status='present',
                minutes_late=0
            ).count()
            
            attendance_score = (present_count / total_records) * 100
            punctuality_score = (on_time_count / total_records) * 100
            engagement_score = (attendance_score * 0.7 + punctuality_score * 0.3)
            
            # Update user profile or create engagement metric
            try:
                from apps.users.models import UserProfile
                profile, created = UserProfile.objects.get_or_create(
                    user=instance.student
                )
                
                # Store engagement score in metadata or separate model
                # For now, just log it
                logger.info(f"Updated engagement score for {instance.student.get_full_name()}: {engagement_score:.2f}")
                
            except Exception as e:
                logger.error(f"Error updating engagement score: {e}")


@receiver(post_save, sender=AttendanceSession)
def monitor_session_health(sender, instance, created, **kwargs):
    """
    Monitor session health and performance
    """
    if not created and instance.is_active:
        # Check if session has been active too long
        active_duration = timezone.now() - instance.start_time
        max_duration = timedelta(hours=4)  # 4 hours max
        
        if active_duration > max_duration:
            # Create alert for long-running session
            AttendanceAlert.objects.create(
                institution=instance.institution,
                alert_type='suspicious_activity',
                severity='warning',
                title='Long-Running Attendance Session',
                description=f'Session "{instance.title}" has been active for {active_duration.total_seconds()/3600:.1f} hours',
                session=instance,
                alert_data={
                    'active_duration': active_duration.total_seconds(),
                    'max_duration': max_duration.total_seconds()
                }
            )


# Import Q for database queries
from django.db.models import Q, Count
