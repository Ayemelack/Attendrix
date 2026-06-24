from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from django.utils import timezone
from .models import Message, Announcement, AnnouncementAcknowledgment

User = get_user_model()


@receiver(post_save, sender=Message)
def message_created(sender, instance, created, **kwargs):
    """Handle message creation"""
    if created:
        from apps.alerts.models import Notification, NotificationTemplate
        
        # Create notification for recipient
        if instance.recipient:
            # Get or create message notification template
            template, _ = NotificationTemplate.objects.get_or_create(
                name='new_message',
                defaults={
                    'title': 'New Message',
                    'message': 'You have received a new message from {sender}',
                    'notification_type': 'message'
                }
            )
            
            # Create notification
            Notification.objects.create(
                user=instance.recipient,
                title='New Message',
                message=f'You have received a new message from {instance.sender.get_full_name() or instance.sender.username}',
                notification_type='message',
                related_object_id=instance.id,
                related_object_type='message',
                institution=instance.recipient.institution if hasattr(instance.recipient, 'institution') else None
            )
        
        # Create notifications for group members
        elif instance.group:
            for member in instance.group.members.all():
                if member != instance.sender:  # Don't notify sender
                    Notification.objects.create(
                        user=member,
                        title='New Group Message',
                        message=f'New message in {instance.group.name} from {instance.sender.get_full_name() or instance.sender.username}',
                        notification_type='message',
                        related_object_id=instance.id,
                        related_object_type='message',
                        institution=member.institution if hasattr(member, 'institution') else None
                    )


@receiver(post_save, sender=Announcement)
def announcement_created(sender, instance, created, **kwargs):
    """Handle announcement creation"""
    if created:
        from apps.alerts.models import Notification
        
        # Determine target users
        target_users = set()
        
        # Add users from target groups
        for group in instance.target_groups.all():
            target_users.update(group.members.all())
        
        # Add users by target roles
        if instance.target_roles:
            from apps.users.models import UserProfile
            target_users.update(
                User.objects.filter(
                    userprofile__role__in=instance.target_roles,
                    userprofile__institution=instance.institution
                )
            )
        
        # Create notifications for all target users
        for user in target_users:
            if user != instance.created_by:  # Don't notify creator
                Notification.objects.create(
                    user=user,
                    title=f'New Announcement: {instance.title}',
                    message=instance.content[:200] + ('...' if len(instance.content) > 200 else ''),
                    notification_type='announcement',
                    related_object_id=instance.id,
                    related_object_type='announcement',
                    institution=instance.institution,
                    priority=instance.priority
                )


@receiver(post_save, sender=AnnouncementAcknowledgment)
def acknowledgment_created(sender, instance, created, **kwargs):
    """Handle announcement acknowledgment"""
    if created:
        from apps.alerts.models import Notification
        
        # Create notification for announcement creator
        Notification.objects.create(
            user=instance.announcement.created_by,
            title='Acknowledgment Received',
            message=f'{instance.user.get_full_name() or instance.user.username} has acknowledged your announcement: {instance.announcement.title}',
            notification_type='acknowledgment',
            related_object_id=instance.id,
            related_object_type='acknowledgment',
            institution=instance.announcement.institution
        )


@receiver(post_delete, sender=Message)
def message_deleted(sender, instance, **kwargs):
    """Handle message deletion"""
    # Log message deletion for audit
    from apps.core.models import AuditLog
    
    AuditLog.objects.create(
        user=instance.sender,
        action='DELETE',
        model='Message',
        object_id=instance.id,
        details={
            'message_subject': instance.subject,
            'recipient': instance.recipient.username if instance.recipient else None,
            'group': instance.group.name if instance.group else None,
            'deleted_at': timezone.now().isoformat()
        }
    )


@receiver(post_delete, sender=Announcement)
def announcement_deleted(sender, instance, **kwargs):
    """Handle announcement deletion"""
    # Log announcement deletion for audit
    from apps.core.models import AuditLog
    
    AuditLog.objects.create(
        user=instance.created_by,
        action='DELETE',
        model='Announcement',
        object_id=instance.id,
        details={
            'announcement_title': instance.title,
            'institution': instance.institution.name,
            'priority': instance.priority,
            'deleted_at': timezone.now().isoformat()
        }
    )
