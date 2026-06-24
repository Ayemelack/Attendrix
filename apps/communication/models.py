from django.db import models
from django.contrib.auth import get_user_model
from apps.institutions.models import Institution

User = get_user_model()


class CommunicationGroup(models.Model):
    """Communication groups for targeted messaging"""
    institution = models.ForeignKey(Institution, on_delete=models.CASCADE, related_name='communication_groups')
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    members = models.ManyToManyField(User, related_name='communication_groups')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Communication Group'
        verbose_name_plural = 'Communication Groups'
        unique_together = ['institution', 'name']
    
    def __str__(self):
        return f"{self.name} - {self.institution.name}"


class Message(models.Model):
    """Messages between users"""
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_messages')
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_messages', null=True, blank=True)
    group = models.ForeignKey(CommunicationGroup, on_delete=models.CASCADE, related_name='messages', null=True, blank=True)
    subject = models.CharField(max_length=200, blank=True)
    content = models.TextField()
    attachment = models.FileField(upload_to='message_attachments/', blank=True, null=True)
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    is_deleted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Message'
        verbose_name_plural = 'Messages'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Message from {self.sender.username}"


class Announcement(models.Model):
    """System announcements"""
    institution = models.ForeignKey(Institution, on_delete=models.CASCADE, related_name='announcements')
    title = models.CharField(max_length=200)
    content = models.TextField()
    priority = models.CharField(max_length=20, choices=[
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ], default='medium')
    target_groups = models.ManyToManyField(CommunicationGroup, related_name='announcements', blank=True)
    target_roles = models.JSONField(default=list, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    requires_acknowledgment = models.BooleanField(default=False)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_announcements')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Announcement'
        verbose_name_plural = 'Announcements'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.title} - {self.institution.name}"


class AnnouncementAcknowledgment(models.Model):
    """Track announcement acknowledgments"""
    announcement = models.ForeignKey(Announcement, on_delete=models.CASCADE, related_name='acknowledgments')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='announcement_acknowledgments')
    acknowledged_at = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    
    class Meta:
        verbose_name = 'Announcement Acknowledgment'
        verbose_name_plural = 'Announcement Acknowledgments'
        unique_together = ['announcement', 'user']
    
    def __str__(self):
        return f"{self.user.username} - {self.announcement.title}"


class MessageThread(models.Model):
    """Message threads for conversations"""
    participants = models.ManyToManyField(User, related_name='message_threads')
    subject = models.CharField(max_length=200, blank=True)
    last_message_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Message Thread'
        verbose_name_plural = 'Message Threads'
        ordering = ['-last_message_at']
    
    def __str__(self):
        return f"Thread with {self.participants.count()} participants"
