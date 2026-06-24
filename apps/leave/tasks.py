"""
Leave management tasks for Attendrix - Background processing for leave workflow
"""
from celery import shared_task
from django.utils import timezone
from django.db.models import Q, Count, Avg, Sum
from django.db.models.functions import Extract
from datetime import datetime, timedelta
from apps.core.models import ActivityLog
from apps.leave.models import (
    LeaveType, LeaveBalance, LeaveRequest, LeaveApproval,
    LeaveCalendar, LeaveHoliday, LeaveAnalytics, LeavePolicy
)
from apps.alerts.models import Notification, NotificationTemplate
from apps.communication.models import Announcement
from apps.users.models import User
import logging

logger = logging.getLogger(__name__)


@shared_task
def process_leave_balance_accruals(institution_id=None):
    """
    Process leave balance accruals for all users
    """
    try:
        if institution_id:
            institution_filter = Q(institution_id=institution_id)
        else:
            institution_filter = Q()
        
        # Get all active leave types with accrual
        accrual_leave_types = LeaveType.objects.filter(
            institution_filter,
            is_active=True,
            is_deleted=False,
            accrual_frequency__in=['monthly', 'quarterly']
        )
        
        accruals_processed = 0
        
        for leave_type in accrual_leave_types:
            # Get users eligible for this leave type
            eligible_users = User.objects.filter(
                institution_filter,
                role__in=leave_type.eligible_roles,
                is_active=True,
                date_joined__lte=timezone.now() - timedelta(days=leave_type.min_employment_months * 30)
            )
            
            for user in eligible_users:
                # Get or create balance for current period
                current_date = timezone.now().date()
                
                if leave_type.accrual_frequency == 'monthly':
                    period_start = current_date.replace(day=1)
                    period_end = current_date.replace(day=31)
                elif leave_type.accrual_frequency == 'quarterly':
                    # Get current quarter
                    quarter = (current_date.month - 1) // 3 + 1
                    period_start = current_date.replace(month=(quarter - 1) * 3 + 1, day=1)
                    period_end = current_date.replace(month=quarter * 3, day=31)
                else:
                    continue
                
                balance, created = LeaveBalance.objects.get_or_create(
                    user=user,
                    leave_type=leave_type,
                    period_start=period_start,
                    period_end=period_end
                )
                
                # Calculate accrual days
                if leave_type.accrual_frequency == 'monthly':
                    accrual_days = leave_type.accrual_rate
                elif leave_type.accrual_frequency == 'quarterly':
                    accrual_days = leave_type.accrual_rate * 3
                else:
                    accrual_days = 0
                
                if accrual_days > 0:
                    balance.accrued_days += accrual_days
                    balance.available_days += accrual_days
                    balance.save()
                    accruals_processed += 1
        
        logger.info(f"Processed {accruals_processed} leave balance accruals")
        return accruals_processed
        
    except Exception as e:
        logger.error(f"Error processing leave balance accruals: {e}")
        return 0


@shared_task
def generate_leave_analytics(institution_id=None):
    """
    Generate leave analytics for all analytics types
    """
    try:
        if institution_id:
            institution_filter = Q(institution_id=institution_id)
        else:
            institution_filter = Q()
        
        # Get date range
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=30)
        
        analytics_generated = 0
        
        # Generate summary analytics
        _generate_summary_analytics(institution_filter, start_date, end_date)
        analytics_generated += 1
        
        # Generate trend analytics
        _generate_trend_analytics(institution_filter, start_date, end_date)
        analytics_generated += 1
        
        # Generate user analytics
        _generate_user_analytics(institution_filter, start_date, end_date)
        analytics_generated += 1
        
        # Generate department analytics
        _generate_department_analytics(institution_filter, start_date, end_date)
        analytics_generated += 1
        
        # Generate course analytics
        _generate_course_analytics(institution_filter, start_date, end_date)
        analytics_generated += 1
        
        # Generate leave type analytics
        _generate_leave_type_analytics(institution_filter, start_date, end_date)
        analytics_generated += 1
        
        logger.info(f"Generated {analytics_generated} leave analytics")
        return analytics_generated
        
    except Exception as e:
        logger.error(f"Error generating leave analytics: {e}")
        return 0


def _generate_summary_analytics(institution_filter, start_date, end_date):
    """Generate summary analytics"""
    from apps.institutions.models import Institution
    
    institutions = Institution.objects.filter(institution_filter)
    
    for institution in institutions:
        # Calculate overall statistics
        total_requests = LeaveRequest.objects.filter(
            institution=institution,
            created_at__date__gte=start_date,
            created_at__date__lte=end_date,
            is_deleted=False
        ).count()
        
        approved_requests = LeaveRequest.objects.filter(
            institution=institution,
            status='approved',
            created_at__date__gte=start_date,
            created_at__date__lte=end_date,
            is_deleted=False
        ).count()
        
        rejected_requests = LeaveRequest.objects.filter(
            institution=institution,
            status='rejected',
            created_at__date__gte=start_date,
            created_at__date__lte=end_date,
            is_deleted=False
        ).count()
        
        pending_requests = LeaveRequest.objects.filter(
            institution=institution,
            status='pending',
            created_at__date__gte=start_date,
            created_at__date__lte=end_date,
            is_deleted=False
        ).count()
        
        cancelled_requests = LeaveRequest.objects.filter(
            institution=institution,
            status='cancelled',
            created_at__date__gte=start_date,
            created_at__date__lte=end_date,
            is_deleted=False
        ).count()
        
        # Calculate total leave days
        approved_leave_days = LeaveRequest.objects.filter(
            institution=institution,
            status='approved',
            start_date__gte=start_date,
            end_date__lte=end_date,
            is_deleted=False
        ).aggregate(total_days=Sum('total_days'))['total_days'] or 0
        
        # Create or update analytics
        LeaveAnalytics.objects.update_or_create(
            institution=institution,
            analytics_type='summary',
            reference_id=None,
            reference_date=end_date,
            defaults={
                'total_requests': total_requests,
                'approved_requests': approved_requests,
                'rejected_requests': rejected_requests,
                'pending_requests': pending_requests,
                'cancelled_requests': cancelled_requests,
                'total_leave_days': 0.0,
                'approved_leave_days': approved_leave_days,
                'approval_rate': (approved_requests / total_requests * 100) if total_requests > 0 else 0,
                'rejection_rate': (rejected_requests / total_requests * 100) if total_requests > 0 else 0,
                'average_days_per_request': (approved_leave_days / approved_requests) if approved_requests > 0 else 0
            }
        )


def _generate_trend_analytics(institution_filter, start_date, end_date):
    """Generate trend analytics"""
    from apps.institutions.models import Institution
    
    institutions = Institution.objects.filter(institution_filter)
    
    for institution in institutions:
        # Generate analytics for each day in the period
        current_date = start_date
        previous_date = start_date - timedelta(days=30)
        
        while current_date <= end_date:
            # Get current period stats
            current_stats = LeaveRequest.objects.filter(
                institution=institution,
                created_at__date=current_date,
                is_deleted=False
            ).aggregate(
                total=Count('id'),
                approved=Count('id', filter=Q(status='approved')),
                rejected=Count('id', filter=Q(status='rejected'))
            )
            
            # Get previous period stats
            previous_stats = LeaveRequest.objects.filter(
                institution=institution,
                created_at__date=previous_date,
                is_deleted=False
            ).aggregate(
                total=Count('id'),
                approved=Count('id', filter=Q(status='approved')),
                rejected=Count('id', filter=Q(status='rejected'))
            )
            
            # Calculate trend
            if previous_stats['total'] > 0:
                total_trend = ((current_stats['total'] - previous_stats['total']) / previous_stats['total']) * 100
                approved_trend = ((current_stats['approved'] - previous_stats['approved']) / previous_stats['approved']) * 100 if previous_stats['approved'] > 0 else 0
            else:
                total_trend = 0
                approved_trend = 0
            
            # Determine trend direction
            if total_trend > 5:
                trend_direction = 'increasing'
            elif total_trend < -5:
                trend_direction = 'decreasing'
            else:
                trend_direction = 'stable'
            
            # Create or update analytics
            LeaveAnalytics.objects.update_or_create(
                institution=institution,
                analytics_type='trend',
                reference_id=None,
                reference_date=current_date,
                defaults={
                    'total_requests': current_stats['total'],
                    'approved_requests': current_stats['approved'],
                    'rejected_requests': current_stats['rejected'],
                    'pending_requests': 0,
                    'cancelled_requests': 0,
                    'total_leave_days': 0.0,
                    'approved_leave_days': 0.0,
                    'approval_rate': (current_stats['approved'] / current_stats['total'] * 100) if current_stats['total'] > 0 else 0,
                    'rejection_rate': (current_stats['rejected'] / current_stats['total'] * 100) if current_stats['total'] > 0 else 0,
                    'average_days_per_request': 0.0,
                    'trend_percentage': total_trend,
                    'trend_direction': trend_direction
                }
            )
            
            current_date += timedelta(days=1)
            previous_date += timedelta(days=1)


def _generate_user_analytics(institution_filter, start_date, end_date):
    """Generate user-specific analytics"""
    users = User.objects.filter(institution_filter, is_active=True)
    
    for user in users:
        # Calculate user's leave statistics
        user_requests = LeaveRequest.objects.filter(
            user=user,
            created_at__date__gte=start_date,
            created_at__date__lte=end_date,
            is_deleted=False
        )
        
        total_requests = user_requests.count()
        approved_requests = user_requests.filter(status='approved').count()
        rejected_requests = user_requests.filter(status='rejected').count()
        pending_requests = user_requests.filter(status='pending').count()
        
        # Calculate total leave days
        approved_leave_days = user_requests.filter(
            status='approved'
        ).aggregate(total_days=Sum('total_days'))['total_days'] or 0
        
        # Create or update analytics
        LeaveAnalytics.objects.update_or_create(
            institution=user.institution,
            analytics_type='user',
            reference_id=user.id,
            reference_date=end_date,
            defaults={
                'total_requests': total_requests,
                'approved_requests': approved_requests,
                'rejected_requests': rejected_requests,
                'pending_requests': pending_requests,
                'cancelled_requests': 0,
                'total_leave_days': 0.0,
                'approved_leave_days': approved_leave_days,
                'approval_rate': (approved_requests / total_requests * 100) if total_requests > 0 else 0,
                'rejection_rate': (rejected_requests / total_requests * 100) if total_requests > 0 else 0,
                'average_days_per_request': (approved_leave_days / approved_requests) if approved_requests > 0 else 0,
                'trend_percentage': 0.0,
                'trend_direction': 'stable'
            }
        )


def _generate_department_analytics(institution_filter, start_date, end_date):
    """Generate department-specific analytics"""
    from apps.departments.models import Department
    
    departments = Department.objects.filter(institution_filter, is_active=True)
    
    for department in departments:
        # Calculate department's leave statistics
        dept_requests = LeaveRequest.objects.filter(
            user__department=department,
            created_at__date__gte=start_date,
            created_at__date__lte=end_date,
            is_deleted=False
        )
        
        total_requests = dept_requests.count()
        approved_requests = dept_requests.filter(status='approved').count()
        rejected_requests = dept_requests.filter(status='rejected').count()
        pending_requests = dept_requests.filter(status='pending').count()
        
        # Calculate total leave days
        approved_leave_days = dept_requests.filter(
            status='approved'
        ).aggregate(total_days=Sum('total_days'))['total_days'] or 0
        
        # Create or update analytics
        LeaveAnalytics.objects.update_or_create(
            institution=department.institution,
            analytics_type='department',
            reference_id=department.id,
            reference_date=end_date,
            defaults={
                'total_requests': total_requests,
                'approved_requests': approved_requests,
                'rejected_requests': rejected_requests,
                'pending_requests': pending_requests,
                'cancelled_requests': 0,
                'total_leave_days': 0.0,
                'approved_leave_days': approved_leave_days,
                'approval_rate': (approved_requests / total_requests * 100) if total_requests > 0 else 0,
                'rejection_rate': (rejected_requests / total_requests * 100) if total_requests > 0 else 0,
                'average_days_per_request': (approved_leave_days / approved_requests) if approved_requests > 0 else 0,
                'trend_percentage': 0.0,
                'trend_direction': 'stable'
            }
        )


def _generate_course_analytics(institution_filter, start_date, end_date):
    """Generate course-specific analytics"""
    from apps.courses.models import Course
    
    courses = Course.objects.filter(institution_filter, is_deleted=False)
    
    for course in courses:
        # Calculate course's leave statistics
        course_requests = LeaveRequest.objects.filter(
            user__courseenrollments__course=course,
            created_at__date__gte=start_date,
            created_at__date__lte=end_date,
            is_deleted=False
        )
        
        total_requests = course_requests.count()
        approved_requests = course_requests.filter(status='approved').count()
        rejected_requests = course_requests.filter(status='rejected').count()
        pending_requests = course_requests.filter(status='pending').count()
        
        # Calculate total leave days
        approved_leave_days = course_requests.filter(
            status='approved'
        ).aggregate(total_days=Sum('total_days'))['total_days'] or 0
        
        # Create or update analytics
        LeaveAnalytics.objects.update_or_create(
            institution=course.institution,
            analytics_type='course',
            reference_id=course.id,
            reference_date=end_date,
            defaults={
                'total_requests': total_requests,
                'approved_requests': approved_requests,
                'rejected_requests': rejected_requests,
                'pending_requests': pending_requests,
                'cancelled_requests': 0,
                'total_leave_days': 0.0,
                'approved_leave_days': approved_leave_days,
                'approval_rate': (approved_requests / total_requests * 100) if total_requests > 0 else 0,
                'rejection_rate': (rejected_requests / total_requests * 100) if total_requests > 0 else 0,
                'average_days_per_request': (approved_leave_days / approved_requests) if approved_requests > 0 else 0,
                'trend_percentage': 0.0,
                'trend_direction': 'stable'
            }
        )


def _generate_leave_type_analytics(institution_filter, start_date, end_date):
    """Generate leave type-specific analytics"""
    leave_types = LeaveType.objects.filter(institution_filter, is_active=True)
    
    for leave_type in leave_types:
        # Calculate leave type statistics
        type_requests = LeaveRequest.objects.filter(
            leave_type=leave_type,
            created_at__date__gte=start_date,
            created_at__date__lte=end_date,
            is_deleted=False
        )
        
        total_requests = type_requests.count()
        approved_requests = type_requests.filter(status='approved').count()
        rejected_requests = type_requests.filter(status='rejected').count()
        pending_requests = type_requests.filter(status='pending').count()
        
        # Calculate total leave days
        approved_leave_days = type_requests.filter(
            status='approved'
        ).aggregate(total_days=Sum('total_days'))['total_days'] or 0
        
        # Create or update analytics
        LeaveAnalytics.objects.update_or_create(
            institution=leave_type.institution,
            analytics_type='leave_type',
            reference_id=leave_type.id,
            reference_date=end_date,
            defaults={
                'total_requests': total_requests,
                'approved_requests': approved_requests,
                'rejected_requests': rejected_requests,
                'pending_requests': pending_requests,
                'cancelled_requests': 0,
                'total_leave_days': 0.0,
                'approved_leave_days': approved_leave_days,
                'approval_rate': (approved_requests / total_requests * 100) if total_requests > 0 else 0,
                'rejection_rate': (rejected_requests / total_requests * 100) if total_requests > 0 else 0,
                'average_days_per_request': (approved_leave_days / approved_requests) if approved_requests > 0 else 0,
                'trend_percentage': 0.0,
                'trend_direction': 'stable'
            }
        )


@shared_task
def send_leave_notifications(leave_request_id, action, user_id):
    """
    Send notifications for leave request actions
    """
    try:
        leave_request = LeaveRequest.objects.get(id=leave_request_id)
        user = User.objects.get(id=user_id)
        
        # Get notification template
        template = NotificationTemplate.objects.filter(
            institution=leave_request.institution,
            template_type='leave_request',
            is_default=True
        ).first()
        
        if not template:
            # Create default template if none exists
            template = NotificationTemplate.objects.create(
                institution=leave_request.institution,
                template_type='leave_request',
                name='Default Leave Request',
                subject_template='Leave Request {action}',
                message_template='Your leave request has been {action}.'
            )
        
        # Prepare context for template rendering
        context = {
            'user_name': user.get_full_name(),
            'leave_type': leave_request.leave_type.name,
            'start_date': leave_request.start_date,
            'end_date': leave_request.end_date,
            'total_days': leave_request.total_days,
            'reason': leave_request.reason,
            'approver_name': leave_request.approver.get_full_name() if leave_request.approver else None,
            'action': action.title(),
            'institution_name': leave_request.institution.name
        }
        
        # Render template
        subject, message = template.render(context)
        
        # Create notification
        notification = Notification.objects.create(
            institution=leave_request.institution,
            recipient=leave_request.user,
            title=subject,
            message=message,
            notification_type='leave_request',
            priority='medium',
            metadata={
                'leave_request_id': leave_request.id,
                'action': action,
                'user_id': user_id
            }
        )
        
        # Queue for delivery
        from apps.alerts.models import NotificationQueue
        NotificationQueue.objects.create(
            institution=leave_request.institution,
            notification=notification,
            priority='medium',
            channel_priority=['in_app', 'email']
        )
        
        logger.info(f"Sent leave notification for request {leave_request_id}: {action}")
        
    except Exception as e:
        logger.error(f"Error sending leave notification: {e}")


@shared_task
def cleanup_old_leave_data():
    """
    Clean up old leave data
    """
    try:
        # Clean up old leave requests (older than 2 years)
        cutoff_date = timezone.now() - timedelta(days=730)
        
        old_requests = LeaveRequest.objects.filter(
            created_at__lt=cutoff_date,
            is_deleted=False
        )
        
        count = old_requests.count()
        old_requests.update(is_deleted=True)
        
        # Clean up old analytics (older than 1 year)
        analytics_cutoff_date = timezone.now() - timedelta(days=365)
        
        old_analytics = LeaveAnalytics.objects.filter(
            reference_date__lt=analytics_cutoff_date
        )
        
        analytics_count = old_analytics.count()
        old_analytics.delete()
        
        # Clean up old queue entries (older than 30 days)
        queue_cutoff_date = timezone.now() - timedelta(days=30)
        
        old_queue_entries = NotificationQueue.objects.filter(
            created_at__lt=queue_cutoff_date,
            status__in=['sent', 'failed']
        )
        
        queue_count = old_queue_entries.count()
        old_queue_entries.delete()
        
        logger.info(f"Cleaned up old leave data: {count} requests, {analytics_count} analytics, {queue_count} queue entries")
        return count + analytics_count + queue_count
        
    except Exception as e:
        logger.error(f"Error cleaning up old leave data: {e}")
        return 0


@shared_task
def check_leave_conflicts(institution_id, start_date, end_date, user_id=None):
    """
    Check for leave conflicts
    """
    try:
        # Get base query
        requests_query = LeaveRequest.objects.filter(
            institution_id=institution_id,
            status='approved',
            start_date__lte=end_date,
            end_date__gte=start_date,
            is_deleted=False
        )
        
        if user_id:
            # Check conflicts for specific user
            user_requests = requests_query.filter(user_id=user_id)
        else:
            # Check conflicts for all users
            user_requests = requests_query
        
        conflicts = []
        
        for request1 in user_requests:
            for request2 in user_requests:
                if request1.id != request2.id:
                    # Check for date overlap
                    if (request1.start_date <= request2.end_date and 
                        request1.end_date >= request2.start_date):
                        conflicts.append({
                            'request1_id': request1.id,
                            'request2_id': request2.id,
                            'conflict_type': 'date_overlap',
                            'user_id': request1.user.id,
                            'start_date': request1.start_date,
                            'end_date': request1.end_date
                        })
        
        # Remove duplicate conflicts
        unique_conflicts = []
        seen_conflicts = set()
        
        for conflict in conflicts:
            conflict_key = (conflict['user_id'], conflict['start_date'], conflict['end_date'])
            if conflict_key not in seen_conflicts:
                unique_conflicts.append(conflict)
                seen_conflicts.add(conflict_key)
        
        # Log conflicts
        if unique_conflicts:
            logger.warning(f"Found {len(unique_conflicts)} leave conflicts")
            
            # Create alerts for conflicts
            for conflict in unique_conflicts:
                try:
                    user = User.objects.get(id=conflict['user_id'])
                    
                    # Create alert
                    from apps.alerts.models import Alert
                    Alert.objects.get_or_create(
                        institution_id=institution_id,
                        title='Leave Conflict Detected',
                        description=f'Leave request conflicts with another approved leave request',
                        alert_type='schedule_conflict',
                        severity='warning',
                        student=user,
                        alert_data={
                            'conflict_details': conflict
                        }
                    )
                    
                except User.DoesNotExist:
                    pass
        
        return len(unique_conflicts)
        
    except Exception as e:
        logger.error(f"Error checking leave conflicts: {e}")
        return 0


@shared_task
def update_carry_forward_balances():
    """
    Update carry-forward balances
    """
    try:
        from apps.institutions.models import Institution
        institutions = Institution.objects.filter(is_active=True)
        
        updated_balances = 0
        
        for institution in institutions:
            # Get leave policies
            try:
                policy = LeavePolicy.objects.get(institution=institution)
            except LeavePolicy.DoesNotExist:
                continue
            
            if not policy.carry_forward_enabled:
                continue
            
            # Get all leave types with carry forward
            carry_forward_types = LeaveType.objects.filter(
                institution=institution,
                is_active=True,
                carry_forward_allowed=True,
                is_deleted=False
            )
            
            for leave_type in carry_forward_types:
                # Get users with carry forward days
                balances_with_carry_forward = LeaveBalance.objects.filter(
                    institution=institution,
                    leave_type=leave_type,
                    carried_forward_days__gt=0
                )
                
                for balance in balances_with_carry_forward:
                    # Check if carry forward has expired
                    if balance.carry_forward_expiry and balance.carry_forward_expiry < timezone.now().date():
                        # Expired carry forward
                        balance.carried_forward_days = 0
                        balance.available_days -= balance.carried_forward_days
                        balance.save()
                        updated_balances += 1
                    else:
                        # Apply carry forward
                        balance.available_days += balance.carried_forward_days
                        balance.carried_forward_days = 0
                        balance.save()
                        updated_balances += 1
        
        logger.info(f"Updated {updated_balances} carry forward balances")
        return updated_balances
        
    except Exception as e:
        logger.error(f"Error updating carry forward balances: {e}")
        return 0


@shared_task
def send_leave_reminders():
    """
    Send leave reminders for upcoming leave
    """
    try:
        # Get upcoming leave starting in the next 7 days
        start_date = timezone.now().date()
        end_date = start_date + timedelta(days=7)
        
        upcoming_leave = LeaveRequest.objects.filter(
            start_date__gte=start_date,
            start_date__lte=end_date,
            status='approved',
            is_deleted=False
        ).select_related('user', 'leave_type')
        
        reminders_sent = 0
        
        for leave in upcoming_leave:
            # Check if reminder hasn't been sent recently
            last_reminder = Notification.objects.filter(
                recipient=leave.user,
                metadata__leave_request_id=leave.id,
                created_at__gte=timezone.now() - timedelta(hours=24)
            ).exists()
            
            if not last_reminder:
                # Create reminder notification
                days_until = (leave.start_date - timezone.now().date()).days
                
                Notification.objects.create(
                    institution=leave.institution,
                    recipient=leave.user,
                    title=f'Leave Reminder: {leave.leave_type.name}',
                    message=f'Your {leave.leave_type.name} starts in {days_until} days',
                    notification_type='deadline_reminder',
                    priority='medium',
                    metadata={
                        'leave_request_id': leave.id
                    }
                )
                
                # Queue for delivery
                from apps.alerts.models import NotificationQueue
                NotificationQueue.objects.create(
                    institution=leave.institution,
                    notification_id=notification.id,
                    priority='medium',
                    channel_priority=['in_app', 'email']
                )
                
                reminders_sent += 1
        
        logger.info(f"Sent {reminders_sent} leave reminders")
        return reminders_sent
        
    except Exception as e:
        logger.error(f"Error sending leave reminders: {e}")
        return 0


@shared_task
def generate_leave_report(report_data):
    """
    Generate leave report
    """
    try:
        institution_id = report_data['institution_id']
        report_type = report_data['report_type']
        start_date = report_data['start_date']
        end_date = report_data['end_date']
        user_ids = report_data.get('user_ids', [])
        department_ids = report_data.get('department_ids', [])
        leave_type_ids = report_data.get('leave_type_ids', [])
        status = report_data.get('status', 'all')
        format_type = report_data['format']
        include_details = report_data.get('include_details', True)
        include_analytics = report_data.get('include_analytics', True)
        requested_by = report_data['requested_by']
        
        # Get institution
        from apps.institutions.models import Institution
        institution = Institution.objects.get(id=institution_id)
        
        # Build query based on filters
        requests_query = LeaveRequest.objects.filter(
            institution=institution,
            start_date__gte=start_date,
            end_date__lte=end_date,
            is_deleted=False
        )
        
        if user_ids:
            requests_query = requests_query.filter(user_id__in=user_ids)
        
        if department_ids:
            requests_query = requests_query.filter(user__department_id__in=department_ids)
        
        if leave_type_ids:
            requests_query = requests_query.filter(leave_type_id__in=leave_type_ids)
        
        if status != 'all':
            requests_query = requests_query(status=status)
        
        # Get data
        requests = requests_query.select_related(
            'user', 'leave_type', 'approver'
        )
        
        # Generate report based on type
        if report_type == 'summary':
            report_content = _generate_summary_report(requests, institution, start_date, end_date, include_details, include_analytics)
        elif report_type == 'balance':
            report_content = _generate_balance_report(requests, institution, start_date, end_date, user_ids, department_ids)
        elif report_type == 'trend':
            report_content = _generate_trend_report(requests, institution, start_date, end_date)
        elif report_type == 'department':
            report_content = _generate_department_report(requests, institution, start_date, end_date, include_details)
        elif report_type == 'course':
            report_content = _generate_course_report(requests, institution, start_date, end_date, include_details)
        elif report_type == 'user':
            report_content = _generate_user_report(requests, institution, start_date, end_date, user_ids, include_details)
        elif report_type == 'leave_type':
            report_content = _generate_leave_type_report(requests, institution, start_date, end_date, leave_type_ids, include_details)
        
        # Save report
        if format_type == 'json':
            # Return JSON response
            return Response(report_content)
        elif format_type == 'csv':
            # Generate CSV
            return _generate_csv_report(report_content, institution, report_type, start_date, end_date)
        elif format_type == 'pdf':
            # Generate PDF
            return _generate_pdf_report(report_content, institution, report_type, start_date, end_date)
        
        return report_content
        
    except Exception as e:
        logger.error(f"Error generating leave report: {e}")
        return None


def _generate_summary_report(requests, institution, start_date, end_date, include_details, include_analytics):
    """Generate summary report"""
    # Calculate summary statistics
    total_requests = requests.count()
    approved_requests = requests.filter(status='approved').count()
    rejected_requests = requests.filter(status='rejected').count()
    pending_requests = requests.filter(status='pending').count()
    cancelled_requests = requests.filter(status='cancelled').count()
    
    # Calculate leave days
    approved_leave_days = requests.aggregate(
        total_days=Sum('total_days')
    )['total_days'] or 0
    
    # Calculate rates
    approval_rate = (approved_requests / total_requests * 100) if total_requests > 0 else 0
    rejection_rate = (rejected_requests / total_requests * 100) if total_requests > 0 else 0
    average_days_per_request = (approved_leave_days / approved_requests) if approved_requests > 0 else 0
    
    # Build report content
    report_content = {
        'institution': institution.name,
        'period': {
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat()
        },
        'summary': {
            'total_requests': total_requests,
            'approved_requests': approved_requests,
            'rejected_requests': rejected_requests,
            'pending_requests': pending_requests,
            'cancelled_requests': cancelled_requests,
            'total_leave_days': approved_leave_days,
            'approval_rate': round(approval_rate, 2),
            'rejection_rate': round(rejection_rate, 2),
            'average_days_per_request': round(report_data.get('average_days_per_request', average_days_per_request)
        }
    }
    
    if include_details:
        # Add detailed breakdown
        report_content['details'] = []
        
        for request in requests[:100]:  # Limit to 100 requests for summary
            report_content['details'].append({
                'id': request.id,
                'user': request.user.get_full_name(),
                'leave_type': request.leave_type.name,
                'start_date': request.start_date.isoformat(),
                'end_date': request.end_date.isoformat(),
                'total_days': request.total_days,
                'reason': request.reason,
                'status': request.status,
                'priority': request.priority,
                'created_at': request.created_at.isoformat()
            })
    
    if include_analytics:
        # Add analytics
        report_content['analytics'] = _get_analytics_summary(institution, start_date, end_date)
    
    return report_content


def _generate_balance_report(requests, institution, start_date, end_date, user_ids, department_ids):
    """Generate balance report"""
    # Get balances for specified users/departments
    balances_query = LeaveBalance.objects.filter(
        institution=institution,
        period_start__lte=start_date,
        period_end__gte=end_date
    )
    
    if user_ids:
        balances_query = balances_query.filter(user_id__in=user_ids)
    
    if department_ids:
        balances_query = balances_query.filter(user__department_id__in=department_ids)
    
    balances = balances_query.select_related('user', 'leave_type').order_by('user__first_name')
    
    # Build report content
    report_content = {
        'institution': institution.name,
        'period': {
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat()
        },
        'balances': []
    }
    
    for balance in balances:
        report_content['balances'].append({
            'user': balance.user.get_full_name(),
            'leave_type': balance.leave_type.name,
            'accrued_days': balance.accrued_days,
            'used_days': balance.used_days,
            'pending_days': balance.pending_days,
            'available_days': balance.available_days,
            'carried_forward_days': balance.carried_forward_days,
            'period_start': balance.period_start.isoformat(),
            'period_end': balance.period_end.isoformat()
        })
    
    return report_content


def _generate_trend_report(requests, institution, start_date, end_date):
    """Generate trend report"""
    # Get analytics for the period
    analytics = LeaveAnalytics.objects.filter(
        institution=institution,
        analytics_type='trend',
        reference_date__gte=start_date,
        reference_date__lte=end_date
    ).order_by('reference_date')
    
    report_content = {
        'institution': institution.name,
        'period': {
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat()
        },
        'trends': []
    }
    
    for analytic in analytics:
        report_content['trends'].append({
            'date': analytic.reference_date.isoformat(),
            'total_requests': analytic.total_requests,
            'approved_requests': analytic.approved_requests,
            'approval_rate': analytic.approval_rate,
            'trend_percentage': analytic.trend_percentage,
            'trend_direction': analytic.trend_direction
        })
    
    return report_content


def _generate_department_report(requests, institution, start_date, end_date, include_details):
    """Generate department report"""
    # Get department analytics for the period
    analytics = LeaveAnalytics.objects.filter(
        institution=institution,
        analytics_type='department',
        reference_date=end_date
    ).select_related('reference_id')
    
    report_content = {
        'institution': institution.name,
        'period': {
            'start_date': start_date.strftime('%Y-%m-%d'),
            'end_date': end_date.strftime('%Y-%m-%d')
        },
        'departments': []
    }
    
    for analytic in analytics:
        try:
            department = Department.objects.get(id=analytic.reference_id)
            
            report_content['departments'].append({
                'department': department.name,
                'total_requests': analytic.total_requests,
                'approved_requests': analytic.approved_requests,
                'rejection_rate': analytic.rejection_rate,
                'average_days_per_request': analytic.average_days_per_request,
                'trend_percentage': analytic.trend_percentage,
                'trend_direction': analytic.trend_direction
            })
        except Department.DoesNotExist:
            pass
    
    return report_content


def _generate_course_report(requests, institution, start_date, end_date, include_details):
    """Generate course report"""
    # Get course analytics for the period
    analytics = LeaveAnalytics.objects.filter(
        institution=institution,
        analytics_type='course',
        reference_date=end_date
    ).select_related('reference_id')
    
    report_content = {
        'institution': institution.name,
        'period': {
            'start_date': start_date.strftime('%Y-%m-%d'),
            'end_date': end_date.strftime('%Y-%m-%d')
        },
        'courses': []
    }
    
    for analytic in analytics:
        try:
            course = Course.objects.get(id=analytic.reference_id)
            
            report_content['courses'].append({
                'course': course.title,
                'code': course.code,
                'total_requests': analytic.total_requests,
                'approved_requests': analytic.approved_requests,
                'rejection_rate': analytic.rejection_rate,
                'average_days_per_request': analytic.average_days_per_request,
                'trend_percentage': analytic.trend_percentage,
                'trend_direction': analytic.trend_direction
            })
        except Course.DoesNotExist:
            pass
    
    return report_content


def _generate_user_report(requests, institution, start_date, end_date, user_ids, include_details):
    """Generate user report"""
    # Get user analytics for the period
    analytics = LeaveAnalytics.objects.filter(
        institution=institution,
        analytics_type='user',
        reference_date=end_date
    ).filter(reference_id__in=user_ids)
    
    report_content = {
        'institution': institution.name,
        'period': {
            'start_date': start_date.strftime('%Y-%m-%d'),
            'end_date': end_date.strftime('%Y-%m-%d')
        },
        'users': []
    }
    
    for analytic in analytics:
        try:
            user = User.objects.get(id=analytic.reference_id)
            
            report_content['users'].append({
                'user': user.get_full_name(),
                'total_requests': analytic.total_requests,
                'approved_requests': analytic.approved_requests,
                'rejection_rate': analytic.rejection_rate,
                'average_days_per_request': analytic.average_days_per_request,
                'trend_percentage': analytic.trend_percentage,
                'trend_direction': analytic.trend_direction
            })
        except User.DoesNotExist:
            pass
    
    return report_content


def _generate_leave_type_report(requests, institution, start_date, end_date, leave_type_ids, include_details):
    """Generate leave type report"""
    # Get leave type analytics for the period
    analytics = LeaveAnalytics.objects.filter(
        institution=institution,
        analytics_type='leave_type',
        reference_date=end_date
    ).filter(reference_id__in=leave_type_ids)
    
    report_content = {
        'institution': institution.name,
        'period': {
            'start_date': start_date.strftime('%Y-%m-%d'),
            'end_date': end_date.strftime('%Y-%m-%d')
        },
        'leave_types': []
    }
    
    for analytic in analytics:
        try:
            leave_type = LeaveType.objects.get(id=analytic.reference_id)
            
            report_content['leave_types'].append({
                'leave_type': leave_type.name,
                'category': leave_type.category,
                'total_requests': analytic.total_requests,
                'approved_requests': analytic.approved_requests,
                'rejection_rate': analytic.rejection_rate,
                'average_days_per_request': analytic.average_days_per_request,
                'trend_percentage': analytic.trend_percentage,
                'trend_direction': analytic.trend_direction
            })
        except LeaveType.DoesNotExist:
            pass
    
    return report_content


def _get_analytics_summary(institution, start_date, end_date):
    """Get analytics summary for the period"""
    # Get all analytics for the period
    analytics = LeaveAnalytics.objects.filter(
        institution=institution,
        reference_date__gte=start_date,
        reference_date__lte=end_date
    )
    
    # Calculate overall statistics
    total_requests = analytics.aggregate(
        total=Count('id'),
        approved=Count('id', filter=Q(status='approved')),
        rejected=Count('id', filter=Q(status='rejected')),
        pending=Count('id', filter=Q(status='pending')),
        cancelled=Count('id', filter=Q(status='cancelled'))
    )
    
    # Calculate average metrics
    total_leave_days = analytics.aggregate(
        total_days=Sum('approved_leave_days')
    )['total_leave_days'] or 0
    
    avg_approval_rate = (total['approved'] / total['total'] * 100) if total['total'] > 0 else 0
    avg_rejection_rate = (total['rejected'] / total['total'] * 100) if total['total'] > 0 else 0
    
    return {
        'total_requests': total['total'],
        'approved_requests': total['approved'],
        'rejected_requests': total['rejected'],
        'pending_requests': total['pending'],
        'cancelled_requests': total['cancelled'],
        'total_leave_days': total_leave_days,
        'avg_approval_rate': round(avg_approval_rate, 2),
        'avg_rejection_rate': round(avg_rejection_rate, 2)
    }


def _generate_csv_report(report_content, institution, report_type, start_date, end_date):
    """Generate CSV report"""
    import csv
    import io
    from django.http import HttpResponse
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="leave_{report_type}_{start_date}_to_{end_date}.csv"'
    
    writer = csv.writer(response)
    
    # Write header
    if report_type == 'summary':
        writer.writerow([
            'Date', 'Total Requests', 'Approved', 'Rejected', 'Pending', 'Cancelled', 'Total Leave Days', 'Approval Rate', 'Rejection Rate'
        ])
        
        for date in date_range(start_date, end_date):
            # Get analytics for this date
            analytics = LeaveAnalytics.objects.filter(
                institution=institution,
                analytics_type='summary',
                reference_date=date
            ).first()
            
            writer.writerow([
                date.isoformat(),
                analytics.total_requests,
                analytics.approved_requests,
                analytics.rejected_requests,
                analytics.pending_requests,
                analytics.cancelled_requests,
                analytics.approved_leave_days,
                analytics.approval_rate,
                analytics.rejection_rate
            ])
    
    elif report_type == 'balance':
        writer.writerow([
            'User', 'Leave Type', 'Accrued Days', 'Used Days', 'Pending Days', 'Available Days', 'Carried Forward Days', 'Period Start', 'Period End'
        ])
        
        # Add balance data
        for balance in LeaveBalance.objects.filter(
            institution=institution,
            period_start__gte=start_date,
            period_end__lte=end_date
        ):
            writer.writerow([
                balance.user.get_full_name(),
                balance.leave_type.name,
                balance.accrued_days,
                balance.used_days,
                balance.pending_days,
                balance.available_days,
                balance.carried_forward_days,
                balance.period_start.isoformat(),
                balance.period_end.isoformat()
            ])
    
    return response


def _generate_pdf_report(report_content, institution, report_type, start_date, end_date):
    """Generate PDF report"""
    # This would integrate with a PDF library like ReportLab
    # For now, return JSON
    return report_content


@shared_task
def create_default_notification_templates():
    """
    Create default notification templates if they don't exist
    """
    try:
        from apps.institutions.models import Institution
        institutions = Institution.objects.filter(is_active=True)
        
        templates_created = 0
        
        for institution in institutions:
            # Create default templates
            templates = [
                {
                    'name': 'Leave Request - Created',
                    'template_type': 'leave_request',
                    'subject_template': 'Leave Request Created',
                    'message_template': 'Your leave request has been created and is pending approval.',
                    'is_default': True
                },
                {
                    'name': 'Leave Request - Approved',
                    'template_type': 'leave_request',
                    'subject_template': 'Leave Request Approved',
                    'message_template': 'Your leave request has been approved.',
                    'is_default': True
                },
                {
                    'name': 'Leave Request - Rejected',
                    'template_type': 'leave_request',
                    'subject_template': 'Leave Request Rejected',
                    'message_template='Your leave request has been rejected.',
                    'is_default': True
                },
                {
                    'name: 'Leave Request - Cancelled',
                    'template_type': 'leave_request',
                    'subject_template': 'Leave Request Cancelled',
                    'message_template='Your leave request has been cancelled.',
                    'is_default': True
                }
            ]
            
            for template_data in templates:
                template_data['institution_id'] = institution.id
                NotificationTemplate.objects.get_or_create(
                    **template_data
                )
                templates_created += 1
        
        logger.info(f"Created {templates_created} default notification templates")
        return templates_created
        
    except Exception as e:
        logger.error(f"Error creating default notification templates: {e}")
        return 0


@shared_task
def send_daily_leave_digest():
    """
    Send daily leave digest to institution admins
    """
    try:
        from apps.institutions.models import Institution
        institutions = Institution.objects.filter(is_active=True)
        
        digests_sent = 0
        
        for institution in institutions:
            # Get yesterday's statistics
            yesterday = timezone.now().date() - timedelta(days=1)
            
            yesterday_requests = LeaveRequest.objects.filter(
                institution=institution,
                created_at__date=yesterday,
                is_deleted=False
            ).count()
            
            yesterday_approved = LeaveRequest.objects.filter(
                institution=institution,
                status='approved',
                created_at__date=yesterday,
                is_deleted=False
            ).count()
            
            yesterday_rejected = LeaveRequest.objects.filter(
                institution=institution,
                status='rejected',
                created_at__date=yesterday,
                is_deleted=False
            ).count()
            
            # Create digest notification for admins
            if yesterday_requests > 0:
                admins = User.objects.filter(
                    institution=institution,
                    role='institution_admin',
                    is_active=True
                )
                
                for admin in admins:
                    Notification.objects.create(
                        institution=institution,
                        recipient=admin,
                        title=f'Daily Leave Digest - {yesterday.strftime("%B %d, %Y")}',
                        message=f'Yesterday: {yesterday_requests} requests, {yesterday_approved} approved, {yesterday_rejected} rejected',
                        notification_type='system_update',
                        priority='low',
                        metadata={
                            'date': yesterday.isoformat(),
                            'total_requests': yesterday_requests,
                            'approved_requests': yesterday_approved,
                            'rejected_requests': yesterday_rejected
                        }
                    )
                    digests_sent += 1
        
        logger.info(f"Sent {digests_sent} daily leave digests")
        return digests_sent
        
    except Exception as e:
        logger.error(f"Error sending daily leave digest: {e}")
        return 0
