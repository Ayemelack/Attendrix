"""
Scheduling tasks for Attendrix - Background processing for scheduling engine
"""
from celery import shared_task
from django.utils import timezone
from django.db.models import Q, Count
from datetime import datetime, timedelta
from apps.core.models import ActivityLog
from apps.scheduling.models import (
    Schedule, ScheduleOccurrence, ScheduleConflict, ScheduleAnalytics,
    ScheduleTemplate, ScheduleAdjustment
)
from apps.alerts.models import Alert, Notification
from apps.communication.models import Announcement
import logging

logger = logging.getLogger(__name__)


@shared_task
def generate_schedule_occurrences(schedule_id):
    """
    Generate occurrences for recurring schedules
    """
    try:
        schedule = Schedule.objects.get(id=schedule_id)
        
        if schedule.recurrence_type == 'none':
            logger.info(f"Schedule {schedule_id} is not recurring")
            return
        
        # Delete existing occurrences
        schedule.occurrences.all().delete()
        
        # Generate new occurrences based on recurrence pattern
        occurrences = []
        current_date = schedule.start_date
        
        while current_date <= schedule.end_date:
            # Check if this date should have an occurrence
            if _should_create_occurrence(schedule, current_date):
                occurrence = ScheduleOccurrence.objects.create(
                    institution=schedule.institution,
                    parent_schedule=schedule,
                    occurrence_date=current_date,
                    start_time=schedule.start_time,
                    end_time=schedule.end_time,
                    created_by=schedule.created_by
                )
                occurrences.append(occurrence)
            
            # Move to next date based on recurrence
            current_date = _get_next_occurrence_date(schedule, current_date)
            
            # Check max occurrences limit
            if schedule.max_occurrences and len(occurrences) >= schedule.max_occurrences:
                break
        
        logger.info(f"Generated {len(occurrences)} occurrences for schedule {schedule_id}")
        
        # Detect conflicts for new occurrences
        detect_schedule_conflicts_for_schedule.delay(schedule_id)
        
        return len(occurrences)
        
    except Schedule.DoesNotExist:
        logger.error(f"Schedule {schedule_id} not found")
        return 0
    except Exception as e:
        logger.error(f"Error generating occurrences for schedule {schedule_id}: {e}")
        return 0


def _should_create_occurrence(schedule, date):
    """
    Check if an occurrence should be created for a specific date
    """
    # Check if date is a holiday
    from apps.institutions.models import HolidayCalendar
    if HolidayCalendar.objects.filter(
        institution=schedule.institution,
        date=date,
        affects_attendance=True
    ).exists():
        return False
    
    # Check recurrence pattern
    if schedule.recurrence_type == 'daily':
        return True
    elif schedule.recurrence_type == 'weekly':
        preferred_days = schedule.recurrence_pattern.get('days', [1, 2, 3, 4, 5])  # Mon-Fri default
        return date.weekday() in preferred_days
    elif schedule.recurrence_type == 'biweekly':
        # Every other week
        week_number = date.isocalendar()[1]
        return week_number % 2 == 0
    elif schedule.recurrence_type == 'monthly':
        # Same day of month
        return date.day == schedule.start_date.day
    elif schedule.recurrence_type == 'custom':
        # Custom pattern logic
        return _check_custom_recurrence(schedule, date)
    
    return False


def _get_next_occurrence_date(schedule, current_date):
    """
    Get the next occurrence date based on recurrence type
    """
    if schedule.recurrence_type == 'daily':
        return current_date + timedelta(days=1)
    elif schedule.recurrence_type == 'weekly':
        return current_date + timedelta(days=7)
    elif schedule.recurrence_type == 'biweekly':
        return current_date + timedelta(days=14)
    elif schedule.recurrence_type == 'monthly':
        # Add one month
        if current_date.month == 12:
            return current_date.replace(year=current_date.year + 1, month=1)
        else:
            return current_date.replace(month=current_date.month + 1)
    elif schedule.recurrence_type == 'custom':
        # Custom pattern logic
        return _get_next_custom_date(schedule, current_date)
    
    return current_date + timedelta(days=1)


def _check_custom_recurrence(schedule, date):
    """
    Check custom recurrence pattern
    """
    pattern = schedule.recurrence_pattern
    
    # Example custom patterns
    if pattern.get('type') == 'weekdays':
        return date.weekday() < 5  # Monday-Friday
    elif pattern.get('type') == 'weekends':
        return date.weekday() >= 5  # Saturday-Sunday
    elif pattern.get('type') == 'specific_days':
        return date.weekday() in pattern.get('days', [])
    
    return False


def _get_next_custom_date(schedule, current_date):
    """
    Get next date for custom recurrence
    """
    pattern = schedule.recurrence_pattern
    
    if pattern.get('type') == 'weekdays':
        # Find next weekday
        next_date = current_date + timedelta(days=1)
        while next_date.weekday() >= 5:
            next_date += timedelta(days=1)
        return next_date
    elif pattern.get('type') == 'weekends':
        # Find next weekend day
        next_date = current_date + timedelta(days=1)
        while next_date.weekday() < 5:
            next_date += timedelta(days=1)
        return next_date
    
    return current_date + timedelta(days=1)


@shared_task
def detect_schedule_conflicts_for_schedule(schedule_id):
    """
    Detect conflicts for a specific schedule
    """
    try:
        schedule = Schedule.objects.get(id=schedule_id)
        conflicts = schedule.detect_conflicts()
        
        # Create conflict records for new conflicts
        for conflict_data in conflicts:
            if conflict_data['type'] in ['lecturer_conflict', 'room_conflict']:
                ScheduleConflict.objects.get_or_create(
                    institution=schedule.institution,
                    schedule_1=schedule,
                    schedule_2_id=conflict_data['conflict_id'],
                    conflict_date=schedule.start_date,
                    conflict_time_start=schedule.start_time,
                    conflict_time_end=schedule.end_time,
                    defaults={
                        'conflict_type': conflict_data['type'].replace('_conflict', ''),
                        'severity': 'high',
                        'description': conflict_data['details']
                    }
                )
        
        return len(conflicts)
        
    except Schedule.DoesNotExist:
        logger.error(f"Schedule {schedule_id} not found")
        return 0
    except Exception as e:
        logger.error(f"Error detecting conflicts for schedule {schedule_id}: {e}")
        return 0


@shared_task
def detect_all_schedule_conflicts():
    """
    Detect conflicts for all active schedules
    """
    total_conflicts = 0
    
    # Get all active schedules
    schedules = Schedule.objects.filter(
        is_active=True,
        is_cancelled=False,
        start_date__gte=timezone.now().date()
    )
    
    for schedule in schedules:
        conflicts = detect_schedule_conflicts_for_schedule.delay(schedule.id)
        total_conflicts += conflicts.get() or 0
    
    logger.info(f"Detected {total_conflicts} total conflicts")
    return total_conflicts


@shared_task
def generate_daily_schedule_analytics():
    """
    Generate daily schedule analytics
    """
    try:
        today = timezone.now().date()
        
        # Get all institutions
        from apps.institutions.models import Institution
        institutions = Institution.objects.filter(is_active=True)
        
        for institution in institutions:
            # Calculate metrics
            total_schedules = Schedule.objects.filter(
                institution=institution,
                start_date=today,
                is_active=True,
                is_cancelled=False
            ).count()
            
            active_schedules = Schedule.objects.filter(
                institution=institution,
                start_date=today,
                is_active=True,
                is_published=True,
                is_cancelled=False
            ).count()
            
            cancelled_schedules = total_schedules - active_schedules
            
            # Room utilization
            occupied_rooms = Schedule.objects.filter(
                institution=institution,
                start_date=today,
                room__isnull=False,
                is_active=True,
                is_cancelled=False
            ).values('room').distinct().count()
            
            total_rooms = institution.resources.filter(
                resource_type='classroom',
                is_active=True
            ).count()
            
            room_utilization = (occupied_rooms / total_rooms * 100) if total_rooms > 0 else 0
            
            # Lecturer workload
            lecturer_hours = Schedule.objects.filter(
                institution=institution,
                start_date=today,
                lecturer__isnull=False,
                is_active=True,
                is_cancelled=False
            ).aggregate(
                total_hours=Count('id') * 1.0  # Assuming 1 hour per schedule
            )['total_hours'] or 0
            
            # Conflict metrics
            total_conflicts = ScheduleConflict.objects.filter(
                institution=institution,
                conflict_date=today
            ).count()
            
            resolved_conflicts = ScheduleConflict.objects.filter(
                institution=institution,
                conflict_date=today,
                status='resolved'
            ).count()
            
            conflict_resolution_rate = (resolved_conflicts / total_conflicts * 100) if total_conflicts > 0 else 0
            
            # Create or update analytics record
            analytics, created = ScheduleAnalytics.objects.update_or_create(
                institution=institution,
                date=today,
                defaults={
                    'total_schedules': total_schedules,
                    'active_schedules': active_schedules,
                    'cancelled_schedules': cancelled_schedules,
                    'total_rooms': total_rooms,
                    'occupied_rooms': occupied_rooms,
                    'room_utilization_percentage': room_utilization,
                    'total_lecturer_hours': lecturer_hours,
                    'average_lecturer_workload': lecturer_hours / institution.users.filter(role='lecturer').count() if institution.users.filter(role='lecturer').count() > 0 else 0,
                    'total_conflicts': total_conflicts,
                    'resolved_conflicts': resolved_conflicts,
                    'conflict_resolution_rate': conflict_resolution_rate,
                }
            )
            
            logger.info(f"Generated analytics for {institution.name} on {today}")
        
        return institutions.count()
        
    except Exception as e:
        logger.error(f"Error generating daily schedule analytics: {e}")
        return 0


@shared_task
def send_schedule_reminders():
    """
    Send reminders for upcoming schedules
    """
    try:
        tomorrow = timezone.now().date() + timedelta(days=1)
        
        # Get schedules for tomorrow
        tomorrow_schedules = Schedule.objects.filter(
            start_date=tomorrow,
            is_active=True,
            is_published=True,
            is_cancelled=False
        )
        
        reminders_sent = 0
        
        for schedule in tomorrow_schedules:
            # Send reminder to lecturer
            if schedule.lecturer:
                Notification.objects.create(
                    user=schedule.lecturer,
                    institution=schedule.institution,
                    title='Schedule Reminder',
                    message=f'Reminder: You have a schedule "{schedule.title}" tomorrow at {schedule.start_time}',
                    notification_type='schedule_reminder',
                    metadata={
                        'schedule_id': schedule.id,
                        'date': str(tomorrow),
                        'time': str(schedule.start_time)
                    }
                )
                reminders_sent += 1
            
            # Send reminder to enrolled students
            if schedule.course:
                enrolled_students = schedule.course.enrollments.filter(status='enrolled')
                for enrollment in enrolled_students:
                    Notification.objects.create(
                        user=enrollment.student,
                        institution=schedule.institution,
                        title='Schedule Reminder',
                        message=f'Reminder: You have a class "{schedule.title}" tomorrow at {schedule.start_time}',
                        notification_type='schedule_reminder',
                        metadata={
                            'schedule_id': schedule.id,
                            'date': str(tomorrow),
                            'time': str(schedule.start_time)
                        }
                    )
                    reminders_sent += 1
        
        logger.info(f"Sent {reminders_sent} schedule reminders for {tomorrow}")
        return reminders_sent
        
    except Exception as e:
        logger.error(f"Error sending schedule reminders: {e}")
        return 0


@shared_task
def cleanup_old_occurrences():
    """
    Clean up old schedule occurrences
    """
    try:
        # Delete occurrences older than 6 months
        cutoff_date = timezone.now().date() - timedelta(days=180)
        
        old_occurrences = ScheduleOccurrence.objects.filter(
            occurrence_date__lt=cutoff_date
        )
        
        count = old_occurrences.count()
        old_occurrences.delete()
        
        logger.info(f"Cleaned up {count} old schedule occurrences")
        return count
        
    except Exception as e:
        logger.error(f"Error cleaning up old occurrences: {e}")
        return 0


@shared_task
def optimize_schedule_utilization():
    """
    Analyze and suggest schedule optimizations
    """
    try:
        # Get schedule utilization data
        from apps.institutions.models import Institution
        institutions = Institution.objects.filter(is_active=True)
        
        optimizations = []
        
        for institution in institutions:
            # Analyze room utilization
            room_utilization = ScheduleAnalytics.objects.filter(
                institution=institution,
                date__gte=timezone.now().date() - timedelta(days=30)
            ).aggregate(
                avg_utilization=Avg('room_utilization_percentage')
            )['avg_utilization'] or 0
            
            if room_utilization < 50:
                optimizations.append({
                    'institution': institution.name,
                    'type': 'low_room_utilization',
                    'value': room_utilization,
                    'suggestion': 'Consider consolidating schedules or using fewer rooms'
                })
            
            # Analyze lecturer workload
            overload_count = ScheduleAnalytics.objects.filter(
                institution=institution,
                date__gte=timezone.now().date() - timedelta(days=30)
            ).aggregate(
                avg_overload=Avg('overloaded_lecturers')
            )['avg_overload'] or 0
            
            if overload_count > 2:
                optimizations.append({
                    'institution': institution.name,
                    'type': 'lecturer_overload',
                    'value': overload_count,
                    'suggestion': 'Consider redistributing workload or hiring additional lecturers'
                })
        
        logger.info(f"Generated {len(optimizations)} optimization suggestions")
        return optimizations
        
    except Exception as e:
        logger.error(f"Error in schedule optimization analysis: {e}")
        return []


@shared_task
def sync_schedule_with_external_systems():
    """
    Sync schedules with external systems (LMS, calendar systems)
    """
    try:
        # This would integrate with external systems
        # For now, just log the action
        
        from apps.institutions.models import Institution
        institutions = Institution.objects.filter(is_active=True)
        
        synced_schedules = 0
        
        for institution in institutions:
            # Get schedules that need syncing
            schedules_to_sync = Schedule.objects.filter(
                institution=institution,
                updated_at__gte=timezone.now() - timedelta(hours=1)
            )
            
            for schedule in schedules_to_sync:
                # Sync logic would go here
                synced_schedules += 1
        
        logger.info(f"Synced {synced_schedules} schedules with external systems")
        return synced_schedules
        
    except Exception as e:
        logger.error(f"Error syncing schedules with external systems: {e}")
        return 0


@shared_task
def generate_schedule_reports():
    """
    Generate monthly schedule reports
    """
    try:
        # Get last month's data
        last_month = timezone.now().date() - timedelta(days=30)
        
        from apps.institutions.models import Institution
        institutions = Institution.objects.filter(is_active=True)
        
        reports_generated = 0
        
        for institution in institutions:
            # Generate report data
            analytics = ScheduleAnalytics.objects.filter(
                institution=institution,
                date__gte=last_month
            )
            
            if analytics.exists():
                # Create report summary
                total_schedules = analytics.aggregate(total=Count('id'))['total']
                avg_utilization = analytics.aggregate(avg=Avg('room_utilization_percentage'))['avg'] or 0
                total_conflicts = analytics.aggregate(total=Count('total_conflicts'))['total']
                
                # This would generate a PDF or Excel report
                # For now, just log the summary
                logger.info(f"Report for {institution.name}: {total_schedules} schedules, {avg_utilization:.1f}% utilization, {total_conflicts} conflicts")
                reports_generated += 1
        
        return reports_generated
        
    except Exception as e:
        logger.error(f"Error generating schedule reports: {e}")
        return 0
