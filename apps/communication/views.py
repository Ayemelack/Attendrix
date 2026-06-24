from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.contrib.auth import get_user_model
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter

from .models import CommunicationGroup, Message, Announcement, AnnouncementAcknowledgment, MessageThread
from .serializers import (
    CommunicationGroupSerializer, MessageSerializer, AnnouncementSerializer,
    AnnouncementAcknowledgmentSerializer, MessageThreadSerializer
)

User = get_user_model()


class CommunicationGroupViewSet(viewsets.ModelViewSet):
    """ViewSet for CommunicationGroup model"""
    serializer_class = CommunicationGroupSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['institution', 'is_active']
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'created_at']
    ordering = ['name']
    
    def get_queryset(self):
        queryset = CommunicationGroup.objects.filter(is_active=True)
        user = self.request.user
        
        # Filter by user's institution
        if hasattr(user, 'institution'):
            queryset = queryset.filter(institution=user.institution)
        
        return queryset
    
    @action(detail=True, methods=['post'])
    def add_members(self, request, pk=None):
        """Add members to communication group"""
        group = self.get_object()
        user_ids = request.data.get('user_ids', [])
        
        users = User.objects.filter(id__in=user_ids)
        group.members.add(*users)
        
        return Response({'message': f'Added {len(users)} members to {group.name}'})
    
    @action(detail=True, methods=['post'])
    def remove_members(self, request, pk=None):
        """Remove members from communication group"""
        group = self.get_object()
        user_ids = request.data.get('user_ids', [])
        
        users = User.objects.filter(id__in=user_ids)
        group.members.remove(*users)
        
        return Response({'message': f'Removed {len(users)} members from {group.name}'})


class MessageViewSet(viewsets.ModelViewSet):
    """ViewSet for Message model"""
    serializer_class = MessageSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['sender', 'recipient', 'group', 'is_read']
    search_fields = ['subject', 'content']
    ordering_fields = ['created_at', 'read_at']
    ordering = ['-created_at']
    
    def get_queryset(self):
        queryset = Message.objects.filter(is_deleted=False)
        user = self.request.user
        
        # Filter messages for current user
        queryset = queryset.filter(
            models.Q(sender=user) | 
            models.Q(recipient=user) | 
            models.Q(group__members=user)
        ).distinct()
        
        return queryset
    
    def perform_create(self, serializer):
        serializer.save(sender=self.request.user)
    
    @action(detail=True, methods=['post'])
    def mark_read(self, request, pk=None):
        """Mark message as read"""
        message = self.get_object()
        
        # Only recipient can mark as read
        if message.recipient != request.user and not message.group:
            return Response(
                {'error': 'Only message recipient can mark as read'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        message.is_read = True
        message.read_at = timezone.now()
        message.save()
        
        return Response({'message': 'Message marked as read'})
    
    @action(detail=False, methods=['get'])
    def unread_count(self, request):
        """Get unread message count for current user"""
        count = Message.objects.filter(
            recipient=request.user,
            is_read=False,
            is_deleted=False
        ).count()
        
        return Response({'unread_count': count})


class AnnouncementViewSet(viewsets.ModelViewSet):
    """ViewSet for Announcement model"""
    serializer_class = AnnouncementSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['institution', 'priority', 'is_active']
    search_fields = ['title', 'content']
    ordering_fields = ['created_at', 'priority']
    ordering = ['-created_at']
    
    def get_queryset(self):
        queryset = Announcement.objects.filter(is_active=True)
        user = self.request.user
        
        # Filter by user's institution
        if hasattr(user, 'institution'):
            queryset = queryset.filter(institution=user.institution)
        
        # Filter expired announcements
        queryset = queryset.filter(
            models.Q(expires_at__isnull=True) | 
            models.Q(expires_at__gt=timezone.now())
        )
        
        return queryset
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
    
    @action(detail=True, methods=['post'])
    def acknowledge(self, request, pk=None):
        """Acknowledge announcement"""
        announcement = self.get_object()
        
        if not announcement.requires_acknowledgment:
            return Response(
                {'error': 'This announcement does not require acknowledgment'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        acknowledgment, created = AnnouncementAcknowledgment.objects.get_or_create(
            announcement=announcement,
            user=request.user,
            defaults={'ip_address': request.META.get('REMOTE_ADDR')}
        )
        
        if created:
            return Response({'message': 'Announcement acknowledged'})
        else:
            return Response({'message': 'Already acknowledged'})


class AnnouncementAcknowledgmentViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for AnnouncementAcknowledgment model"""
    serializer_class = AnnouncementAcknowledgmentSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['announcement', 'user']
    ordering_fields = ['acknowledged_at']
    ordering = ['-acknowledged_at']
    
    def get_queryset(self):
        queryset = AnnouncementAcknowledgment.objects.all()
        user = self.request.user
        
        # Users can only see their own acknowledgments
        if not user.is_staff:
            queryset = queryset.filter(user=user)
        
        return queryset


class MessageThreadViewSet(viewsets.ModelViewSet):
    """ViewSet for MessageThread model"""
    serializer_class = MessageThreadSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['participants']
    search_fields = ['subject']
    ordering_fields = ['last_message_at', 'created_at']
    ordering = ['-last_message_at']
    
    def get_queryset(self):
        queryset = MessageThread.objects.all()
        user = self.request.user
        
        # Filter threads where user is a participant
        queryset = queryset.filter(participants=user)
        
        return queryset
    
    @action(detail=True, methods=['post'])
    def add_participant(self, request, pk=None):
        """Add participant to message thread"""
        thread = self.get_object()
        user_id = request.data.get('user_id')
        
        try:
            user = User.objects.get(id=user_id)
            thread.participants.add(user)
            return Response({'message': f'Added {user.username} to thread'})
        except User.DoesNotExist:
            return Response(
                {'error': 'User not found'},
                status=status.HTTP_404_NOT_FOUND
            )
    
    @action(detail=True, methods=['post'])
    def remove_participant(self, request, pk=None):
        """Remove participant from message thread"""
        thread = self.get_object()
        user_id = request.data.get('user_id')
        
        try:
            user = User.objects.get(id=user_id)
            thread.participants.remove(user)
            return Response({'message': f'Removed {user.username} from thread'})
        except User.DoesNotExist:
            return Response(
                {'error': 'User not found'},
                status=status.HTTP_404_NOT_FOUND
            )
