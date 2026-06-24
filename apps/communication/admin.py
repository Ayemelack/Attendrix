from django.contrib import admin
from .models import CommunicationGroup, Message, Announcement, AnnouncementAcknowledgment, MessageThread


@admin.register(CommunicationGroup)
class CommunicationGroupAdmin(admin.ModelAdmin):
    list_display = ['name', 'institution', 'member_count', 'is_active', 'created_at']
    list_filter = ['institution', 'is_active', 'created_at']
    search_fields = ['name', 'description']
    filter_horizontal = ['members']
    readonly_fields = ['created_at', 'updated_at']
    
    def member_count(self, obj):
        return obj.members.count()
    member_count.short_description = 'Members'


class MessageInline(admin.TabularInline):
    model = Message
    extra = 0
    readonly_fields = ['created_at']
    fields = ['sender', 'recipient', 'subject', 'is_read', 'created_at']


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ['sender', 'recipient', 'group', 'subject', 'is_read', 'created_at']
    list_filter = ['is_read', 'is_deleted', 'created_at']
    search_fields = ['subject', 'content', 'sender__username', 'recipient__username']
    readonly_fields = ['created_at', 'updated_at']
    date_hierarchy = 'created_at'
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if not request.user.is_superuser:
            # Filter to show only messages involving current user
            qs = qs.filter(
                models.Q(sender=request.user) | 
                models.Q(recipient=request.user)
            )
        return qs


@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = ['title', 'institution', 'priority', 'requires_acknowledgment', 'is_active', 'created_at']
    list_filter = ['institution', 'priority', 'requires_acknowledgment', 'is_active', 'created_at']
    search_fields = ['title', 'content']
    filter_horizontal = ['target_groups']
    readonly_fields = ['created_at', 'updated_at']
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('institution', 'title', 'content', 'priority')
        }),
        ('Targeting', {
            'fields': ('target_groups', 'target_roles')
        }),
        ('Settings', {
            'fields': ('expires_at', 'is_active', 'requires_acknowledgment')
        }),
        ('Metadata', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )


class AnnouncementAcknowledgmentInline(admin.TabularInline):
    model = AnnouncementAcknowledgment
    extra = 0
    readonly_fields = ['acknowledged_at', 'ip_address']
    fields = ['user', 'acknowledged_at', 'ip_address']


@admin.register(AnnouncementAcknowledgment)
class AnnouncementAcknowledgmentAdmin(admin.ModelAdmin):
    list_display = ['announcement', 'user', 'acknowledged_at', 'ip_address']
    list_filter = ['acknowledged_at', 'announcement__institution']
    search_fields = ['announcement__title', 'user__username']
    readonly_fields = ['acknowledged_at']
    date_hierarchy = 'acknowledged_at'


@admin.register(MessageThread)
class MessageThreadAdmin(admin.ModelAdmin):
    list_display = ['subject', 'participant_count', 'last_message_at', 'created_at']
    list_filter = ['created_at', 'last_message_at']
    search_fields = ['subject']
    filter_horizontal = ['participants']
    readonly_fields = ['created_at', 'updated_at']
    date_hierarchy = 'created_at'
    
    def participant_count(self, obj):
        return obj.participants.count()
    participant_count.short_description = 'Participants'
