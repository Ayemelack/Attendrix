"""
Surveys signals for Attendrix
"""
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.utils import timezone
from apps.surveys.models import (
    Survey, SurveyQuestion, SurveyResponse, SurveyAnswer,
    SurveyTemplate, SurveyAnalytics, SurveyInvitation, SurveyNotification
)
from apps.alerts.models import Notification
from apps.core.models import ActivityLog
from apps.surveys.tasks import (
    generate_survey_analytics, send_survey_invitations,
    process_survey_notifications
)
import logging

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Survey)
def survey_post_save(sender, instance, created, **kwargs):
    """
    Handle survey post-save operations
    """
    if created:
        # Log creation
        ActivityLog.objects.create(
            user=instance.created_by,
            institution=instance.institution,
            action_type='create',
            action_description=f'Survey created: {instance.title}',
            severity='medium'
        )
        
        # Generate analytics if survey is active
        if instance.status == 'active':
            generate_survey_analytics.delay(
                instance.id,
                ['response_rate', 'completion_rate'],
                instance.start_date.date() if instance.start_date else None,
                instance.end_date.date() if instance.end_date else None
            )
        
        # Send invitations if targeting is configured
        if instance.target_users.exists() and instance.status == 'active':
            user_ids = list(instance.target_users.values_list('id', flat=True))
            send_survey_invitations.delay(
                survey_id=instance.id,
                user_ids=user_ids
            )
        
    else:
        # Log update
        ActivityLog.objects.create(
            user=instance.updated_by,
            institution=instance.institution,
            action_type='update',
            action_description=f'Survey updated: {instance.title}',
            severity='low',
            metadata={
                'survey_id': instance.id,
                'status': instance.status
            }
        )
        
        # Handle status changes
        if hasattr(instance, '_old_status') and instance._old_status != instance.status:
            old_status = instance._old_status
            new_status = instance.status
            
            if old_status != 'active' and new_status == 'active':
                # Survey activated
                ActivityLog.objects.create(
                    user=instance.updated_by,
                    institution=instance.institution,
                    action_type='update',
                    action_description=f'Survey activated: {instance.title}',
                    severity='medium'
                )
                
                # Generate analytics
                generate_survey_analytics.delay(
                    instance.id,
                    ['response_rate', 'completion_rate'],
                    instance.start_date.date() if instance.start_date else None,
                    instance.end_date.date() if instance.end_date else None
                )
                
                # Send invitations
                if instance.target_users.exists():
                    user_ids = list(instance.target_users.values_list('id', flat=True))
                    send_survey_invitations.delay(
                        survey_id=instance.id,
                        user_ids=user_ids
                    )
            
            elif old_status == 'active' and new_status == 'paused':
                # Survey paused
                ActivityLog.objects.create(
                    user=instance.updated_by,
                    institution=instance.institution,
                    action_type='update',
                    action_description=f'Survey paused: {instance.title}',
                    severity='medium'
                )
            
            elif old_status != 'completed' and new_status == 'completed':
                # Survey completed
                ActivityLog.objects.create(
                    user=instance.updated_by,
                    institution=instance.institution,
                    action_type='update',
                    action_description=f'Survey completed: {instance.title}',
                    severity='medium'
                )
                
                # Generate final analytics
                generate_survey_analytics.delay(
                    instance.id,
                    ['response_rate', 'completion_rate', 'question_analytics', 'demographic_analytics'],
                    instance.start_date.date() if instance.start_date else None,
                    instance.end_date.date() if instance.end_date else None
                )
                
                # Send completion notifications
                if instance.show_results_to_respondents:
                    completed_responses = SurveyResponse.objects.filter(
                        survey=instance,
                        status='completed',
                        is_deleted=False
                    )
                    
                    for response in completed_responses:
                        Notification.objects.create(
                            institution=instance.institution,
                            recipient=response.user,
                            title=f'Survey Results Available: {instance.title}',
                            message=f'The results for "{instance.title}" are now available for viewing.',
                            notification_type='completion',
                            priority='medium',
                            metadata={
                                'survey_id': instance.id,
                                'response_id': response.id
                            }
                        )
            
            elif old_status == 'completed' and new_status == 'archived':
                # Survey archived
                ActivityLog.objects.create(
                    user=instance.updated_by,
                    institution=instance.institution,
                    action_type='update',
                    action_description=f'Survey archived: {instance.title}',
                    severity='low'
                )


@receiver(pre_save, sender=Survey)
def survey_pre_save(sender, instance, **kwargs):
    """
    Handle survey pre-save operations
    """
    if instance.pk:
        # Store old value for comparison
        try:
            old_instance = Survey.objects.get(pk=instance.pk)
            instance._old_status = old_instance.status
        except Survey.DoesNotExist:
            pass


@receiver(post_save, sender=SurveyQuestion)
def survey_question_post_save(sender, instance, created, **kwargs):
    """
    Handle survey question post-save operations
    """
    if created:
        # Log creation
        ActivityLog.objects.create(
            user=instance.created_by,
            institution=instance.institution,
            action_type='create',
            action_description=f'Survey question created: {instance.question_text[:50]}',
            severity='low'
        )
        
        # Trigger analytics regeneration if survey is active
        if instance.survey.status == 'active':
            generate_survey_analytics.delay(
                instance.survey.id,
                ['question_analytics'],
                instance.survey.start_date.date() if instance.survey.start_date else None,
                instance.survey.end_date.date() if instance.survey.end_date else None
            )
    
    else:
        # Log update
        ActivityLog.objects.create(
            user=instance.updated_by,
            institution=instance.institution,
            action_type='update',
            action_description=f'Survey question updated: {instance.question_text[:50]}',
            severity='low'
        )


@receiver(post_save, sender=SurveyResponse)
def survey_response_post_save(sender, instance, created, **kwargs):
    """
    Handle survey response post-save operations
    """
    if created:
        # Log creation
        ActivityLog.objects.create(
            user=instance.user,
            institution=instance.institution,
            action_type='create',
            action_description=f'Survey response created: {instance.survey.title}',
            severity='low',
            metadata={
                'response_id': instance.id,
                'survey_id': instance.survey.id
            }
        )
        
        # Update survey statistics
        instance.survey.total_responses += 1
        instance.survey.save()
        
        # Generate analytics
        if instance.survey.status == 'active':
            generate_survey_analytics.delay(
                instance.survey.id,
                ['response_rate', 'completion_rate'],
                instance.survey.start_date.date() if instance.survey.start_date else None,
                instance.survey.end_date.date() if instance.survey.end_date else None
            )
        
        # Send notification to user if completed
        if instance.status == 'completed':
            Notification.objects.create(
                institution=instance.institution,
                recipient=instance.user,
                title=f'Thank You: {instance.survey.title}',
                message=f'Thank you for completing the survey "{instance.survey.title}". Your feedback is valuable to us.',
                notification_type='completion',
                priority='medium',
                metadata={
                    'survey_id': instance.survey.id,
                    'response_id': instance.id
                }
            )
            
            # Update invitation status if applicable
            try:
                invitation = SurveyInvitation.objects.get(
                    survey=instance.survey,
                    user=instance.user
                )
                invitation.status = 'completed'
                invitation.completed_at = timezone.now()
                invitation.save()
            except SurveyInvitation.DoesNotExist:
                pass
    
    else:
        # Log update
        ActivityLog.objects.create(
            user=instance.user,
            institution=instance.institution,
            action_type='update',
            action_description=f'Survey response updated: {instance.survey.title}',
            severity='low',
            metadata={
                'response_id': instance.id,
                'survey_id': instance.survey.id,
                'status': instance.status
            }
        )
        
        # Handle completion
        if hasattr(instance, '_old_status') and instance._old_status != 'completed' and instance.status == 'completed':
            # Response completed
            ActivityLog.objects.create(
                user=instance.user,
                institution=instance.institution,
                action_type='update',
                action_description=f'Survey response completed: {instance.survey.title}',
                severity='medium',
                metadata={
                    'response_id': instance.id,
                    'survey_id': instance.survey.id
                }
            )
            
            # Update survey statistics
            instance.survey.completed_responses += 1
            instance.survey.save()
            
            # Generate analytics
            generate_survey_analytics.delay(
                instance.survey.id,
                ['response_rate', 'completion_rate', 'question_analytics'],
                instance.survey.start_date.date() if instance.survey.start_date else None,
                instance.survey.end_date.date() if instance.survey.end_date else None
            )
            
            # Send completion notifications
            if instance.survey.show_results_to_respondents:
                Notification.objects.create(
                    institution=instance.institution,
                    recipient=instance.user,
                    title=f'Survey Results Available: {instance.survey.title}',
                    message=f'The results for "{instance.survey.title}" are now available for viewing.',
                    notification_type='completion',
                    priority='medium',
                    metadata={
                        'survey_id': instance.survey.id,
                        'response_id': instance.id
                    }
                )
            
            # Update invitation status
            try:
                invitation = SurveyInvitation.objects.get(
                    survey=instance.survey,
                    user=instance.user
                )
                invitation.status = 'completed'
                invitation.completed_at = timezone.now()
                invitation.save()
            except SurveyInvitation.DoesNotExist:
                pass


@receiver(pre_save, sender=SurveyResponse)
def survey_response_pre_save(sender, instance, **kwargs):
    """
    Handle survey response pre-save operations
    """
    if instance.pk:
        # Store old value for comparison
        try:
            old_instance = SurveyResponse.objects.get(pk=instance.pk)
            instance._old_status = old_instance.status
        except SurveyResponse.DoesNotExist:
            pass


@receiver(post_save, sender=SurveyAnswer)
def survey_answer_post_save(sender, instance, created, **kwargs):
    """
    Handle survey answer post-save operations
    """
    if created:
        # Log creation
        ActivityLog.objects.create(
            user=instance.response.user if instance.response else None,
            institution=instance.institution,
            action_type='create',
            action_description=f'Survey answer created: {instance.question.question_text[:50]}',
            severity='low',
            metadata={
                'answer_id': instance.id,
                'question_id': instance.question.id,
                'response_id': instance.response.id if instance.response else None
            }
        )
        
        # Trigger analytics regeneration if survey is active
        if instance.response and instance.response.survey.status == 'active':
            generate_survey_analytics.delay(
                instance.response.survey.id,
                ['question_analytics'],
                instance.response.survey.start_date.date() if instance.response.survey.start_date else None,
                instance.response.survey.end_date.date() if instance.response.survey.end_date else None
            )
    
    else:
        # Log update
        ActivityLog.objects.create(
            user=instance.response.user if instance.response else None,
            institution=instance.institution,
            action_type='update',
            action_description=f'Survey answer updated: {instance.question.question_text[:50]}',
            severity='low',
            metadata={
                'answer_id': instance.id,
                'question_id': instance.question.id,
                'response_id': instance.response.id if instance.response else None
            }
        )


@receiver(post_save, sender=SurveyTemplate)
def survey_template_post_save(sender, instance, created, **kwargs):
    """
    Handle survey template post-save operations
    """
    if created:
        # Log creation
        ActivityLog.objects.create(
            user=instance.created_by,
            institution=instance.institution,
            action_type='create',
            action_description=f'Survey template created: {instance.name}',
            severity='low'
        )
    else:
        # Log update
        ActivityLog.objects.create(
            user=instance.updated_by,
            institution=instance.institution,
            action_type='update',
            action_description=f'Survey template updated: {instance.name}',
            severity='low'
        )


@receiver(post_save, sender=SurveyAnalytics)
def survey_analytics_post_save(sender, instance, created, **kwargs):
    """
    Handle survey analytics post-save operations
    """
    if created:
        # Log creation
        ActivityLog.objects.create(
            user=None,  # Analytics are system-generated
            institution=instance.institution,
            action_type='create',
            action_description=f'Survey analytics created: {instance.analytics_type}',
            severity='low',
            metadata={
                'analytics_id': instance.id
            }
        )
    else:
        # Log update
        ActivityLog.objects.create(
            user=None,  # Analytics are system-generated
            institution=instance.institution,
            action_type='update',
            action_description=f'Survey analytics updated: {instance.analytics_type}',
            severity='low',
            metadata={
                'analytics_id': instance.id
            }
        )


@receiver(post_save, sender=SurveyInvitation)
def survey_invitation_post_save(sender, instance, created, **kwargs):
    """
    Handle survey invitation post-save operations
    """
    if created:
        # Log creation
        ActivityLog.objects.create(
            user=instance.created_by,
            institution=instance.institution,
            action_type='create',
            action_description=f'Survey invitation created: {instance.user.get_full_name()} - {instance.survey.title}',
            severity='medium'
        )
        
        # Send notification
        _send_invitation_notification(instance)
    
    else:
        # Log update
        ActivityLog.objects.create(
            user=instance.updated_by,
            institution=instance.institution,
            action_type='update',
            action_description=f'Survey invitation updated: {instance.user.get_full_name()} - {instance.survey.title}',
            severity='low'
        )
        
        # Handle status changes
        if hasattr(instance, '_old_status') and instance._old_status != instance.status:
            old_status = instance._old_status
            new_status = instance.status
            
            if old_status != 'completed' and new_status == 'completed':
                # Invitation completed
                ActivityLog.objects.create(
                    user=instance.user,
                    institution=instance.institution,
                    action_type='update',
                    action_description=f'Survey invitation completed: {instance.user.get_full_name()} - {instance.survey.title}',
                    severity='medium'
                )
                
                # Send completion notification
                Notification.objects.create(
                    institution=instance.institution,
                    recipient=instance.user,
                    title='Survey Completed',
                    message=f'Thank you for completing the survey "{instance.survey.title}".',
                    notification_type='completion',
                    priority='medium',
                    metadata={
                        'survey_id': instance.survey.id,
                        'invitation_id': instance.id
                    }
                )
            
            elif old_status != 'opened' and new_status == 'opened':
                # Invitation opened
                instance.mark_opened()
                
                # Send opened notification
                Notification.objects.create(
                    institution=instance.institution,
                    recipient=instance.user,
                    title='Survey Invitation Opened',
                    message=f'You opened the invitation for "{instance.survey.title}".',
                    notification_type='reminder',
                    priority='low',
                    metadata={
                        'survey_id': instance.survey.id,
                        'invitation_id': instance.id
                    }
                )
            
            elif old_status != 'started' and new_status == 'started':
                # Invitation started
                instance.mark_started()
                
                # Send started notification
                Notification.objects.create(
                    institution=instance.institution,
                    recipient=instance.user,
                    title='Survey Started',
                    message=f'You started responding to "{instance.survey.title}".',
                    notification_type='reminder',
                    priority='medium',
                    metadata={
                        'survey_id': instance.survey.id,
                        'invitation_id': instance.id
                    }
                )


@receiver(post_save, sender=SurveyNotification)
def survey_notification_post_save(sender, instance, created, **kwargs):
    """
    Handle survey notification post-save operations
    """
    if created:
        # Log creation
        ActivityLog.objects.create(
            user=None,  # Notifications are system-generated
            institution=instance.institution,
            action_type='create',
            action_description=f'Survey notification created: {instance.title}',
            severity='low',
            metadata={
                'notification_id': instance.id,
                'notification_type': instance.notification_type
            }
        )
    else:
        # Log update
        ActivityLog.objects.create(
            user=None,  # Notifications are system-generated
            institution=instance.institution,
            action_type='update',
            action_description=f'Survey notification updated: {instance.title}',
            severity='low',
            metadata={
                'notification_id': instance.id,
                'notification_type': instance.notification_type
            }
        )


@receiver(post_delete, sender=Survey)
def survey_post_delete(sender, instance, **kwargs):
    """
    Handle survey post-delete operations
    """
    # Log deletion
    ActivityLog.objects.create(
        user=getattr(instance, 'deleted_by', None),
        institution=instance.institution,
        action_type='delete',
        action_description=f'Survey deleted: {instance.title}',
        severity='medium',
        metadata={
            'survey_id': instance.id
        }
    )


@receiver(post_delete, sender=SurveyQuestion)
def survey_question_post_delete(sender, instance, **kwargs):
    """
    Handle survey question post-delete operations
    """
    # Log deletion
    ActivityLog.objects.create(
        user=getattr(instance, 'deleted_by', None),
        institution=instance.institution,
        action_type='delete',
        action_description=f'Survey question deleted: {instance.question_text[:50]}',
        severity='low',
        metadata={
            'question_id': instance.id,
            'survey_id': instance.survey.id
        }
    )


@receiver(post_delete, sender=SurveyResponse)
def survey_response_post_delete(sender, instance, **kwargs):
    """
    Handle survey response post-delete operations
    """
    # Log deletion
    ActivityLog.objects.create(
        user=getattr(instance, 'deleted_by', None),
        institution=instance.institution,
        action_type='delete',
        action_description=f'Survey response deleted: {instance.survey.title}',
        severity='medium',
        metadata={
            'response_id': instance.id,
            'survey_id': instance.survey.id,
            'user_id': instance.user.id if instance.user else None
        }
    )
    
    # Update survey statistics
    if instance.survey.total_responses > 0:
        instance.survey.total_responses -= 1
        instance.survey.save()


@receiver(post_delete, sender=SurveyAnswer)
def survey_answer_post_delete(sender, instance, **kwargs):
    """
    Handle survey answer post-delete operations
    """
    # Log deletion
    ActivityLog.objects.create(
        user=getattr(instance, 'deleted_by', None),
        institution=instance.institution,
        action_type='delete',
        action_description=f'Survey answer deleted: {instance.question.question_text[:50]}',
        severity='low',
        metadata={
            'answer_id': instance.id,
            'question_id': instance.question.id,
            'response_id': instance.response.id if instance.response else None
        }
    )


@receiver(post_delete, sender=SurveyTemplate)
def survey_template_post_delete(sender, instance, **kwargs):
    """
    Handle survey template post-delete operations
    """
    # Log deletion
    ActivityLog.objects.create(
        user=getattr(instance, 'deleted_by', None),
        institution=instance.institution,
        action_type='delete',
        action_description=f'Survey template deleted: {instance.name}',
        severity='low',
        metadata={
            'template_id': instance.id
        }
    )


@receiver(post_delete, sender=SurveyAnalytics)
def survey_analytics_post_delete(sender, instance, **kwargs):
    """
    Handle survey analytics post-delete operations
    """
    # Log deletion
    ActivityLog.objects.create(
        user=None,  # Analytics are system-generated
        institution=instance.institution,
        action_type='delete',
        action_description=f'Survey analytics deleted: {instance.analytics_type}',
        severity='low',
        metadata={
            'analytics_id': instance.id
        }
    )


@receiver(post_delete, sender=SurveyInvitation)
def survey_invitation_post_delete(sender, instance, **kwargs):
    """
    Handle survey invitation post-delete operations
    """
    # Log deletion
    ActivityLog.objects.create(
        user=getattr(instance, 'deleted_by', None),
        institution=instance.institution,
        action_type='delete',
        action_description=f'Survey invitation deleted: {instance.user.get_full_name()} - {instance.survey.title}',
        severity='medium',
        metadata={
            'invitation_id': instance.id,
            'survey_id': instance.survey.id,
            'user_id': instance.user.id
        }
    )


@receiver(post_delete, sender=SurveyNotification)
def survey_notification_post_delete(sender, instance, **kwargs):
    """
    Handle survey notification post-delete operations
    """
    # Log deletion
    ActivityLog.objects.create(
        user=None,  # Notifications are system-generated
        institution=instance.institution,
        action_type='delete',
        action_description=f'Survey notification deleted: {instance.title}',
        severity='low',
        metadata={
            'notification_id': instance.id,
            'notification_type': instance.notification_type
        }
    )


def _send_invitation_notification(invitation):
    """Send invitation notification"""
    # Create notification for invitation
    notification = Notification.objects.create(
        institution=invitation.survey.institution,
        recipient=invitation.user,
        title=f"Survey Invitation: {invitation.survey.title}",
        message=invitation.personal_message or f"You have been invited to participate in a survey.",
        notification_type='invitation',
        priority='medium',
        metadata={
            'survey_id': invitation.survey.id,
            'invitation_id': invitation.id,
            'invitation_token': invitation.invitation_token
        }
    )
    
    # Queue for delivery
    from apps.alerts.models import NotificationQueue
    NotificationQueue.objects.create(
        institution=invitation.survey.institution,
        notification=notification,
        priority='medium',
        channel_priority=['in_app', 'email']
    )


# Import Q for database queries
from django.db.models import Q
