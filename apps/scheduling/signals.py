"""
Scheduling signals for Attendrix
"""
from django.db.models.signals import post_save, pre_save, post_delete
from django.dispatch import receiver
from django.utils import timezone
from apps.scheduling.models import Schedule, ScheduleOccurrence, ScheduleConflict
from apps.core.models import ActivityLog, SecurityLog
from apps.alerts.models import Alert, Notification
from apps.scheduling.tasks import generate_schedule_occurrences, detect_schedule_conflicts_for_schedule
import logging

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Schedule)
def schedule_post_save(sender, instance, created, **kwargs):
    """
    Handle schedule post-save operations
    """
    if created:
        # Log creation
        ActivityLog.objects.create(
            user=instance.created_by,
            institution=instance.institution,
            action_type='create',
            action_description=f'Schedule created: {instance.title}',
            severity='low'
        )
        
        # Generate occurrences if recurring
        if instance.recurrence_type != 'none':
            generate_schedule_occurrences.delay(instance.id)
        
        # Detect conflicts
        detect_schedule_conflicts_for_schedule.delay(instance.id)
    else:
        # Log update
        ActivityLog.objects.create(
            user=instance.updated_by,
            institution=instance.institution,
            action_type='update',
            action_description=f'Schedule updated: {instance.title}',
            severity='low'
        )
        
        # Regenerate occurrences if recurrence changed
        if instance.recurrence_type != 'none':
            generate_schedule_occurrences.delay(instance.id)


@receiver(pre_save, sender=Schedule)
def schedule_pre_save(sender, instance, **kwargs):
    """
    Handle schedule pre-save operations
    """
    if instance.pk:
        # Get original schedule
        try:
            original = Schedule.objects.get(pk=instance.pk)
            
            # Check if critical fields changed
            critical_fields = ['start_date', 'end_date', 'start_time', 'end_time', 'lecturer', 'room']
            fields_changed = []
            
            for field in critical_fields:
                if getattr(original, field) != getattr(instance, field):
                    fields_changed.append(field)
            
            if fields_changed:
                # Log the change for audit
                instance._fields_changed = fields_changed
                
        except Schedule.DoesNotExist:
            pass


@receiver(post_save, sender=ScheduleOccurrence)
def occurrence_post_save(sender, instance, created, **kwargs):
    """
    Handle schedule occurrence post-save operations
    """
    if created:
        # Log creation
        ActivityLog.objects.create(
            user=instance.created_by,
            institution=instance.institution,
            action_type='create',
            action_description=f'Schedule occurrence created for {instance.parent_schedule.title}',
            severity='low'
        )
    else:
        # Log update
        ActivityLog.objects.create(
            user=instance.updated_by,
            institution=instance.institution,
            action_type='update',
            action_description=f'Schedule occurrence updated for {instance.parent_schedule.title}',
            severity='low'
        )


@receiver(post_save, sender=ScheduleConflict)
def conflict_post_save(sender, instance, created, **kwargs):
    """
    Handle schedule conflict post-save operations
    """
    if created:
        # Log conflict creation
        ActivityLog.objects.create(
            user=instance.created_by,
            institution=instance.institution,
            action_type='create',
            action_description=f'Schedule conflict detected: {instance.conflict_type}',
            severity='medium'
        )
        
        # Create alert for high severity conflicts
        if instance.severity in ['high', 'critical']:
            Alert.objects.create(
                institution=instance.institution,
                title=f'Schedule Conflict: {instance.conflict_type}',
                message=instance.description,
                alert_type='schedule_conflict',
                severity=instance.severity,
                metadata={
                    'conflict_id': instance.id,
                    'schedule_1': instance.schedule_1.id,
                    'schedule_2': instance.schedule_2.id,
                    'conflict_date': str(instance.conflict_date)
                }
            )
            
            # Notify involved lecturers
            if instance.schedule_1.lecturer:
                Notification.objects.create(
                    user=instance.schedule_1.lecturer,
                    institution=instance.institution,
                    title='Schedule Conflict Detected',
                    message=f'Your schedule "{instance.schedule_1.title}" has a conflict',
                    notification_type='schedule_conflict',
                    metadata={
                        'conflict_id': instance.id,
                        'schedule_id': instance.schedule_1.id
                    }
                )
            
            if instance.schedule_2.lecturer:
                Notification.objects.create(
                    user=instance.schedule_2.lecturer,
                    institution=instance.institution,
                    title='Schedule Conflict Detected',
                    message=f'Your schedule "{instance.schedule_2.title}" has a conflict',
                    notification_type='schedule_conflict',
                    metadata={
                        'conflict_id': instance.id,
                        'schedule_id': instance.schedule_2.id
                    }
                )
    
    elif instance.status == 'resolved' and instance.resolved_by:
        # Log resolution
        ActivityLog.objects.create(
            user=instance.resolved_by,
            institution=instance.institution,
            action_type='update',
            action_description=f'Schedule conflict resolved: {instance.conflict_type}',
            severity='medium'
        )


@receiver(post_delete, sender=Schedule)
def schedule_post_delete(sender, instance, **kwargs):
    """
    Handle schedule post-delete operations
    """
    # Log deletion
    ActivityLog.objects.create(
        user=getattr(instance, 'deleted_by', None),
        institution=instance.institution,
        action_type='delete',
        action_description=f'Schedule deleted: {instance.title}',
        severity='medium'
    )
    
    # Clean up related conflicts
    ScheduleConflict.objects.filter(
        Q(schedule_1=instance) | Q(schedule_2=instance)
    ).delete()


@receiver(post_delete, sender=ScheduleOccurrence)
def occurrence_post_delete(sender, instance, **kwargs):
    """
    Handle schedule occurrence post-delete operations
    """
    # Log deletion
    ActivityLog.objects.create(
        user=getattr(instance, 'deleted_by', None),
        institution=instance.institution,
        action_type='delete',
        action_description=f'Schedule occurrence deleted for {instance.parent_schedule.title}',
        severity='low'
    )


@receiver(post_save, sender=Schedule)
def detect_conflicts_on_save(sender, instance, **kwargs):
    """
    Detect conflicts when schedule is saved
    """
    # Only detect conflicts for active schedules
    if instance.is_active and not instance.is_cancelled:
        # Use delay to avoid blocking the save operation
        detect_schedule_conflicts_for_schedule.delay(instance.id)


@receiver(post_save, sender=Schedule)
def notify_schedule_changes(sender, instance, created, **kwargs):
    """
    Notify users of schedule changes
    """
    if not created and hasattr(instance, '_fields_changed'):
        # Schedule was updated with critical field changes
        fields_changed = instance._fields_changed
        
        # Notify lecturer
        if instance.lecturer:
            Notification.objects.create(
                user=instance.lecturer,
                institution=instance.institution,
                title='Schedule Updated',
                message=f'Your schedule "{instance.title}" has been updated',
                notification_type='schedule_update',
                metadata={
                    'schedule_id': instance.id,
                    'changed_fields': fields_changed
                }
            )
        
        # Notify enrolled students
        if instance.course:
            enrolled_students = instance.course.enrollments.filter(status='enrolled')
            for enrollment in enrolled_students:
                Notification.objects.create(
                    user=enrollment.student,
                    institution=instance.institution,
                    title='Schedule Updated',
                    message=f'Your class "{instance.title}" has been updated',
                    notification_type='schedule_update',
                    metadata={
                        'schedule_id': instance.id,
                        'changed_fields': fields_changed
                    }
                )


@receiver(post_save, sender=Schedule)
def auto_optimize_schedule(sender, instance, created, **kwargs):
    """
    Auto-optimize schedule based on preferences
    """
    if created and instance.lecturer:
        # Check if schedule conflicts with lecturer preferences
        from apps.scheduling.models import SchedulePreference
        
        try:
            preferences = SchedulePreference.objects.get(
                user=instance.lecturer,
                institution=instance.institution
            )
            
            # Check for preference conflicts
            conflicts = []
            
            # Check preferred days
            if preferences.preferred_days and instance.start_date.weekday() not in preferences.preferred_days:
                conflicts.append('Not in preferred days')
            
            # Check preferred time range
            if (preferences.preferred_start_time and preferences.preferred_end_time and
                (instance.start_time < preferences.preferred_start_time or 
                 instance.end_time > preferences.preferred_end_time)):
                conflicts.append('Outside preferred time range')
            
            # Check unavailable times
            for unavailable in preferences.unavailable_times:
                if _time_conflicts_with_unavailable(instance.start_time, instance.end_time, unavailable):
                    conflicts.append('Conflicts with unavailable time')
            
            if conflicts:
                # Create notification about preference conflicts
                Notification.objects.create(
                    user=instance.lecturer,
                    institution=instance.institution,
                    title='Schedule Preference Conflict',
                    message=f'Your schedule "{instance.title}" conflicts with your preferences: {", ".join(conflicts)}',
                    notification_type='schedule_preference_conflict',
                    metadata={
                        'schedule_id': instance.id,
                        'conflicts': conflicts
                    }
                )
        
        except SchedulePreference.DoesNotExist:
            pass


def _time_conflicts_with_unavailable(start_time, end_time, unavailable):
    """
    Check if schedule time conflicts with unavailable time slot
    """
    # unavailable format: {'start': '09:00', 'end': '11:00'}
    unavailable_start = timezone.datetime.strptime(unavailable['start'], '%H:%M').time()
    unavailable_end = timezone.datetime.strptime(unavailable['end'], '%H:%M').time()
    
    return (start_time < unavailable_end and end_time > unavailable_start)


@receiver(post_save, sender=ScheduleConflict)
def auto_resolve_simple_conflicts(sender, instance, created, **kwargs):
    """
    Attempt to auto-resolve simple conflicts
    """
    if created and instance.auto_resolvable:
        # Try to auto-resolve based on conflict type
        if instance.conflict_type == 'room':
            # Try to find alternative room
            from apps.departments.models import DepartmentResource
            
            alternative_rooms = DepartmentResource.objects.filter(
                institution=instance.institution,
                resource_type='classroom',
                is_active=True
            ).exclude(
                id=instance.schedule_1.room.id
            )
            
            # Check if alternative room is available
            for room in alternative_rooms:
                if not Schedule.objects.filter(
                    institution=instance.institution,
                    room=room,
                    start_date=instance.conflict_date,
                    start_time__lt=instance.conflict_time_end,
                    end_time__gt=instance.conflict_time_start,
                    is_active=True,
                    is_cancelled=False
                ).exists():
                    # Update schedule with new room
                    instance.schedule_1.room = room
                    instance.schedule_1.save()
                    
                    # Mark conflict as resolved
                    instance.status = 'resolved'
                    instance.resolution_notes = f'Auto-resolved: Changed room to {room.name}'
                    instance.resolved_at = timezone.now()
                    instance.save()
                    
                    # Log auto-resolution
                    ActivityLog.objects.create(
                        user=None,
                        institution=instance.institution,
                        action_type='update',
                        action_description=f'Auto-resolved room conflict for {instance.schedule_1.title}',
                        severity='low'
                    )
                    
                    break
