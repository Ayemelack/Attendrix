"""
Leave management signals for Attendrix
"""
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.utils import timezone
from apps.leave.models import (
    LeaveRequest, LeaveBalance, LeaveApproval, LeaveAnalytics,
    LeaveHoliday, LeavePolicy
)
from apps.alerts.models import Notification
from apps.core.models import ActivityLog
from apps.leave.tasks import (
    send_leave_notifications, process_leave_balance_accruals
)
import logging

logger = logging.getLogger(__name__)


@receiver(post_save, sender=LeaveRequest)
def leave_request_post_save(sender, instance, created, **kwargs):
    """
    Handle leave request post-save operations
    """
    if created:
        # Log creation
        ActivityLog.objects.create(
            user=instance.user,
            institution=instance.institution,
            action_type='create',
            action_description=f'Leave request created: {instance.leave_type.name}',
            severity='medium',
            metadata={
                'leave_request_id': instance.id,
                'total_days': instance.total_days
            }
        )
        
        # Check for immediate approval (auto-approve)
        if instance.leave_type.auto_approve_days and instance.total_days <= instance.leave_type.auto_approve_days:
            instance.approve(
                instance.created_by if hasattr(instance, 'created_by') else None,
                notes='Auto-approved due to short duration'
            )
        
        # Send notification to user
        send_leave_notifications.delay(
            instance.id,
            'created',
            instance.created_by.id if hasattr(instance, 'created_by') else None
        )
        
    else:
        # Log update
        ActivityLog.objects.create(
            user=instance.updated_by if hasattr(instance, 'updated_by') else instance.user,
            institution=instance.institution,
            action_type='update',
            action_description=f'Leave request updated: {instance.leave_type.name}',
            severity='low',
            metadata={
                'leave_request_id': instance.id,
                'status': instance.status
            }
        )
        
        # Handle status changes
        old_status = instance.status
        new_status = instance.status
        
        if old_status != new_status:
            if new_status == 'approved':
                # Log approval
                ActivityLog.objects.create(
                    user=instance.approver if instance.approver else instance.updated_by,
                    institution=instance.institution,
                    action_type='update',
                    action_description=f'Leave request approved: {instance.leave_type.name}',
                    severity='medium',
                    metadata={
                        'leave_request_id': instance.id,
                        'approver': instance.approver.get_full_name() if instance.approver else None
                    }
                )
                
                # Send approval notifications
                send_leave_notifications.delay(
                    instance.id,
                    'approved',
                    instance.approver.id if instance.approver else instance.user.id
                )
                
            elif new_status == 'rejected':
                # Log rejection
                ActivityLog.objects.create(
                    user=instance.approver if instance.approver else instance.updated_by,
                    institution=instance.institution,
                    action_type='update',
                    action_description=f'Leave request rejected: {instance.leave_type.name}',
                    severity='medium',
                    metadata={
                        'leave_request_id': instance.id,
                        'approver': instance.approver.get_full_name() if instance.approver else None
                    }
                )
                
                # Send rejection notifications
                send_leave_notifications.delay(
                    instance.id,
                    'rejected',
                    instance.approver.id if instance.approver else instance.user.id
                )
            
            elif new_status == 'cancelled':
                # Log cancellation
                ActivityLog.objects.create(
                    user=instance.user,
                    institution=instance.institution,
                    action_type='update',
                    action_description=f'Leave request cancelled: {instance.leave_type.name}',
                    severity='low',
                    metadata={
                        'leave_request_id': instance.id
                    }
                )
                
                # Send cancellation notifications
                send_leave_notifications.delay(
                    instance.id,
                    'cancelled',
                    instance.user.id
                )
            
            elif old_status == 'pending' and new_status == 'draft':
                # Draft to pending submission
                ActivityLog.objects.create(
                    user=instance.user,
                    institution=instance.institution,
                    action_type='update',
                    action_description=f'Leave request submitted: {instance.leave_type.name}',
                    severity='medium',
                    metadata={
                        'leave_request_id': instance.id
                    }
                )
                
                # Send notification for submission
                send_leave_notifications.delay(
                    instance.id,
                    'created',
                    instance.user.id
                )


@receiver(post_save, sender=LeaveBalance)
def leave_balance_post_save(sender, instance, created, **kwargs):
    """
    Handle leave balance post-save operations
    """
    if created:
        # Log balance creation
        ActivityLog.objects.create(
            user=instance.user,
            institution=instance.institution,
            action_type='create',
            action_description=f'Leave balance created: {instance.leave_type.name} for {instance.user.get_full_name()}',
            severity='low'
        )
    else:
        # Log balance update
        ActivityLog.objects.create(
            user=instance.user,
            institution=instance.institution,
            action_type='update',
            action_description=f'Leave balance updated: {instance.leave_type.name} for {instance.user.get_full_name()}',
            severity='low'
        )


@receiver(post_save, sender=LeaveApproval)
def leave_approval_post_save(sender, instance, created, **kwargs):
    """
    Handle leave approval post-save operations
    """
    if created:
        # Log approval creation
        ActivityLog.objects.create(
            user=instance.approver,
            institution=instance.institution,
            action_type='create',
            action_description=f'Leave approval created: {instance.leave_request.title}',
            severity='medium',
            metadata={
                'leave_approval_id': instance.id,
                'leave_request_id': instance.leave_request.id
            }
        )
        
        # Update leave request status if decision made
        if instance.decision in ['approved', 'rejected']:
            # Update leave request status
            leave_request = instance.leave_request
            leave_request.status = instance.decision
            leave_request.approval_date = instance.decision_date
            leave_request.approver = instance.approver
            leave_request.save()
            
            # Send notifications
            send_leave_notifications.delay(
                instance.leave_request.id,
                instance.decision,
                instance.approver.id
            )


@receiver(post_save, sender=LeaveAnalytics)
def leave_analytics_post_save(sender, instance, created, **kwargs):
    """
    Handle leave analytics post-save operations
    """
    if created:
        # Log analytics creation
        ActivityLog.objects.create(
            user=None,  # Analytics are system-generated
            institution=instance.institution,
            action_type='create',
            action_description=f'Leave analytics created: {instance.analytics_type}',
            severity='low',
            metadata={
                'analytics_id': instance.id
            }
        )
    else:
        # Log analytics update
        ActivityLog.objects.create(
            user=None,  # Analytics are system-generated
            institution=instance.institution,
            action_type='update',
            action_description=f'Leave analytics updated: {instance.analytics_type}',
            severity='low',
            metadata={
                'analytics_id': instance.id
            }
        )


@receiver(post_save, sender=LeaveHoliday)
def leave_holiday_post_save(sender, instance, created, **kwargs):
    """
    Handle holiday post-save operations
    """
    if created:
        # Log holiday creation
        ActivityLog.objects.create(
            user=instance.created_by,
            institution=instance.institution,
            action_type='create',
            action_description=f'Holiday created: {instance.name}',
            severity='low',
            metadata={
                'holiday_id': instance.id
            }
        )
        
        # Check for conflicts with approved leave requests
        conflicting_requests = LeaveRequest.objects.filter(
            institution=instance.institution,
            status='approved',
            start_date__lte=instance.date,
            end_date__gte=instance.date,
            is_deleted=False
        )
        
        if conflicting_requests.exists():
            # Create alerts for conflicts
            from apps.alerts.models import Alert
            for request in conflicting_requests:
                Alert.objects.get_or_create(
                    institution=instance.institution,
                    title='Holiday Conflict Detected',
                    description=f'Approved leave request conflicts with holiday: {instance.name}',
                    student=request.user,
                    alert_type='schedule_conflict',
                    severity='warning',
                    metadata={
                        'holiday_id': instance.id,
                        'leave_request_id': request.id
                    }
                )
        
        logger.info(f"Created holiday: {instance.name} - {conflicts: {conflicting_requests.count()}")

    else:
        # Log holiday update
        ActivityLog.objects.create(
            user=instance.updated_by,
            institution=instance.institution,
            action_type='update',
            action_description=f'Holiday updated: {instance.name}',
            severity='low',
            metadata={
                'holiday_id': instance.id
            }
        )


@receiver(post_save, sender=LeavePolicy)
def leave_policy_post_save(sender, instance, created, **kwargs):
    """
    Handle leave policy post-save operations
    """
    if created:
        # Log policy creation
        ActivityLog.objects.create(
            user=instance.created_by,
            institution=instance.institution,
            action_type='create',
            action_description=f'Leave policy created for {instance.institution.name}',
            severity='high'
        )
    else:
        # Log policy update
        ActivityLog.objects.create(
            user=instance.updated_by,
            institution=instance.institution,
            action_type='update',
            action_description=f'Leave policy updated for {instance.institution.name}',
            severity='high'
        )


@receiver(post_delete, sender=LeaveRequest)
def leave_request_post_delete(sender, instance, **kwargs):
    """
    Handle leave request post-delete operations
    """
    # Log deletion
    ActivityLog.objects.create(
        user=getattr(instance, 'deleted_by', None),
        institution=instance.institution,
        action_type='delete',
        action_description=f'Leave request deleted: {instance.leave_type.name}',
        severity='medium',
        metadata={
            'leave_request_id': instance.id,
            'user_id': instance.user.id
        }
    )


@receiver(post_delete, sender=LeaveBalance)
def leave_balance_post_delete(sender, instance, **kwargs):
    """
    Handle leave balance post-delete operations
    """
    # Log deletion
    ActivityLog.objects.create(
        user=getattr(instance, 'deleted_by', None),
        institution=instance.institution,
        action_type='delete',
        action_description=f'Leave balance deleted for {instance.leave_type.name}',
        severity='low',
        metadata={
            'balance_id': instance.id,
            'user_id': instance.user.id
        }
    )


@receiver(post_save, sender=LeaveApproval)
def leave_approval_post_delete(sender, instance, **kwargs):
    """
    Handle leave approval post-delete operations
    """
    # Log deletion
    ActivityLog.objects.create(
        user=getattr(instance, 'deleted_by', None),
        institution=instance.institution,
        action_type='delete',
        action_description=f'Leave approval deleted: {instance.leave_request.title}',
        severity='medium',
        metadata={
            'leave_approval_id': instance.id,
            'leave_request_id': instance.leave_request.id,
            'approver_id': instance.approver.id
        }
    )


@receiver(post_save, sender=LeaveAnalytics)
def leave_analytics_post_delete(sender, instance, **kwargs):
    """
    Handle leave analytics post-delete operations
    """
    # Log deletion
    ActivityLog.objects.create(
        user=None,  # Analytics are system-generated
        institution=instance.institution,
        action_type='delete',
        action_description=f'Leave analytics deleted: {instance.analytics_type}',
        severity='low',
        metadata={
            'analytics_id': instance.id
        }
    )


@receiver(post_save, sender=LeaveHoliday)
def leave_holiday_post_delete(sender, instance, **kwargs):
    """
    Handle holiday post-delete operations
    """
    # Log deletion
    ActivityLog.objects.create(
        user=getattr(instance, 'deleted_by', None),
        institution=instance.institution,
        action_type='delete',
        action_description=f'Holiday deleted: {instance.name}',
        severity='low',
        metadata={
            'holiday_id': instance.id
        }
    )


@receiver(post_save, sender=LeavePolicy)
def leave_policy_post_delete(sender, instance, **kwargs):
    """
    Handle leave policy post-delete operations
    """
    # Log deletion
    ActivityLog.objects.create(
        user=getattr(instance, 'deleted_by', None),
        institution=instance.institution,
        action_type='delete',
        action_description=f'Leave policy deleted for {instance.institution.name}',
        severity='high'
    )


# Import Q for database queries
from django.db.models import Q
