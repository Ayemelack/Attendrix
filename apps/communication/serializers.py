from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import CommunicationGroup, Message, Announcement, AnnouncementAcknowledgment, MessageThread

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    """Simple user serializer for communication"""
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name']


class CommunicationGroupSerializer(serializers.ModelSerializer):
    """Serializer for CommunicationGroup model"""
    members = UserSerializer(many=True, read_only=True)
    member_ids = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True,
        required=False
    )
    member_count = serializers.SerializerMethodField()
    
    class Meta:
        model = CommunicationGroup
        fields = [
            'id', 'institution', 'name', 'description', 'members', 'member_ids',
            'member_count', 'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_member_count(self, obj):
        return obj.members.count()
    
    def create(self, validated_data):
        member_ids = validated_data.pop('member_ids', [])
        group = CommunicationGroup.objects.create(**validated_data)
        
        if member_ids:
            users = User.objects.filter(id__in=member_ids)
            group.members.set(users)
        
        return group
    
    def update(self, instance, validated_data):
        member_ids = validated_data.pop('member_ids', None)
        
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        
        if member_ids is not None:
            users = User.objects.filter(id__in=member_ids)
            instance.members.set(users)
        
        return instance


class MessageSerializer(serializers.ModelSerializer):
    """Serializer for Message model"""
    sender = UserSerializer(read_only=True)
    recipient = UserSerializer(read_only=True)
    group_name = serializers.CharField(source='group.name', read_only=True)
    recipient_name = serializers.SerializerMethodField()
    sender_name = serializers.SerializerMethodField()
    
    class Meta:
        model = Message
        fields = [
            'id', 'sender', 'recipient', 'group', 'group_name', 'subject',
            'content', 'attachment', 'is_read', 'read_at', 'recipient_name',
            'sender_name', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'sender', 'is_read', 'read_at', 'created_at', 'updated_at']
    
    def get_recipient_name(self, obj):
        if obj.recipient:
            return f"{obj.recipient.first_name} {obj.recipient.last_name}".strip() or obj.recipient.username
        return None
    
    def get_sender_name(self, obj):
        return f"{obj.sender.first_name} {obj.sender.last_name}".strip() or obj.sender.username
    
    def validate(self, data):
        # Ensure either recipient or group is specified
        recipient = data.get('recipient')
        group = data.get('group')
        
        if not recipient and not group:
            raise serializers.ValidationError("Either recipient or group must be specified.")
        
        if recipient and group:
            raise serializers.ValidationError("Cannot specify both recipient and group.")
        
        return data


class AnnouncementSerializer(serializers.ModelSerializer):
    """Serializer for Announcement model"""
    created_by = UserSerializer(read_only=True)
    institution_name = serializers.CharField(source='institution.name', read_only=True)
    target_groups_data = CommunicationGroupSerializer(
        source='target_groups', many=True, read_only=True
    )
    target_group_ids = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True,
        required=False
    )
    acknowledgment_count = serializers.SerializerMethodField()
    is_acknowledged = serializers.SerializerMethodField()
    
    class Meta:
        model = Announcement
        fields = [
            'id', 'institution', 'institution_name', 'title', 'content', 'priority',
            'target_groups', 'target_groups_data', 'target_group_ids', 'target_roles',
            'expires_at', 'is_active', 'requires_acknowledgment', 'created_by',
            'acknowledgment_count', 'is_acknowledged', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_by', 'acknowledgment_count', 'is_acknowledged', 'created_at', 'updated_at']
    
    def get_acknowledgment_count(self, obj):
        return obj.acknowledgments.count()
    
    def get_is_acknowledged(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.acknowledgments.filter(user=request.user).exists()
        return False
    
    def create(self, validated_data):
        target_group_ids = validated_data.pop('target_group_ids', [])
        announcement = Announcement.objects.create(**validated_data)
        
        if target_group_ids:
            groups = CommunicationGroup.objects.filter(id__in=target_group_ids)
            announcement.target_groups.set(groups)
        
        return announcement
    
    def update(self, instance, validated_data):
        target_group_ids = validated_data.pop('target_group_ids', None)
        
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        
        if target_group_ids is not None:
            groups = CommunicationGroup.objects.filter(id__in=target_group_ids)
            instance.target_groups.set(groups)
        
        return instance


class AnnouncementAcknowledgmentSerializer(serializers.ModelSerializer):
    """Serializer for AnnouncementAcknowledgment model"""
    user = UserSerializer(read_only=True)
    announcement_title = serializers.CharField(source='announcement.title', read_only=True)
    
    class Meta:
        model = AnnouncementAcknowledgment
        fields = [
            'id', 'announcement', 'announcement_title', 'user', 'acknowledged_at',
            'ip_address'
        ]
        read_only_fields = ['id', 'acknowledged_at']


class MessageThreadSerializer(serializers.ModelSerializer):
    """Serializer for MessageThread model"""
    participants = UserSerializer(many=True, read_only=True)
    participant_ids = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True,
        required=False
    )
    participant_count = serializers.SerializerMethodField()
    last_message_preview = serializers.SerializerMethodField()
    
    class Meta:
        model = MessageThread
        fields = [
            'id', 'participants', 'participant_ids', 'subject', 'participant_count',
            'last_message_at', 'last_message_preview', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'last_message_at', 'created_at', 'updated_at']
    
    def get_participant_count(self, obj):
        return obj.participants.count()
    
    def get_last_message_preview(self, obj):
        # Get the most recent message in this thread
        from .models import Message
        last_message = Message.objects.filter(
            models.Q(sender__in=obj.participants.all()) |
            models.Q(recipient__in=obj.participants.all())
        ).order_by('-created_at').first()
        
        if last_message:
            return last_message.content[:100] + ('...' if len(last_message.content) > 100 else '')
        return None
    
    def create(self, validated_data):
        participant_ids = validated_data.pop('participant_ids', [])
        thread = MessageThread.objects.create(**validated_data)
        
        if participant_ids:
            users = User.objects.filter(id__in=participant_ids)
            thread.participants.set(users)
        
        return thread
    
    def update(self, instance, validated_data):
        participant_ids = validated_data.pop('participant_ids', None)
        
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        
        if participant_ids is not None:
            users = User.objects.filter(id__in=participant_ids)
            instance.participants.set(users)
        
        return instance
