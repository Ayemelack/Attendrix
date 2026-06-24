"""
Alerts views for Attendrix - Smart notification and alert system
"""
from rest_framework import status, generics, viewsets
from rest_framework.decorators import api_view, permission_classes, action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from django.utils import timezone
from django.db.models import Q, Count, Avg
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from datetime import datetime, timedelta
from apps.core.models import ActivityLog
from apps.core.permissions import IsInstitutionAdmin, IsLecturer
from apps.alerts.models import (
    Alert, Notification, NotificationTemplate, NotificationPreference,
    NotificationQueue, AlertRule
)
from apps.alerts.serializers import (
    AlertSerializer, NotificationSerializer, NotificationTemplateSerializer,
    NotificationPreferenceSerializer, NotificationQueueSerializer, AlertRuleSerializer,
    BulkNotificationSerializer, AlertActionSerializer, NotificationStatsSerializer,
    AlertRuleTestSerializer
)
from apps.alerts.tasks import (
    process_notification_queue, send_bulk_notifications,
    evaluate_alert_rules, cleanup_expired_notifications
)
import json


class AlertViewSet(viewsets.ModelViewSet):
    """
    Alert viewset with full CRUD operations
    """
    serializer_class = AlertSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['alert_type', 'severity', 'status', 'student', 'course']
    search_fields = ['title', 'description']
    ordering_fields = ['created_at', 'severity', 'escalation_level']
    ordering = ['-created_at']

    def get_queryset(self):
        """Filter alerts by institution and user role"""
        user = self.request.user
        queryset = Alert.objects.filter(
            institution=user.institution,
            is_deleted=False
        )
        
        # Filter based on user role
        if user.is_student():
            # Students can only see alerts about themselves
            queryset = queryset.filter(student=user)
        elif user.is_lecturer():
            # Lecturers can see alerts for their courses and students
            queryset = queryset.filter(
                Q(course__lecturer=user) | Q(student__courseenrollments__course__lecturer=user)
            )
        elif user.is_institution_admin():
            # Institution admins can see all alerts
            pass
        elif user.is_super_admin():
            # Super admins can see all alerts
            pass
        
        return queryset.distinct()

    @action(detail=True, methods=['post'])
    def acknowledge(self, request, pk=None):
        """Acknowledge alert"""
        alert = self.get_object()
        
        if alert.acknowledged:
            return Response({
                'error': 'Alert already acknowledged'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        alert.acknowledge(request.user)
        
        return Response({
            'message': 'Alert acknowledged successfully'
        })

    @action(detail=True, methods=['post'])
    def resolve(self, request, pk=None):
        """Resolve alert"""
        alert = self.get_object()
        serializer = AlertActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        notes = serializer.validated_data.get('notes', '')
        
        alert.resolve(request.user, notes)
        
        return Response({
            'message': 'Alert resolved successfully'
        })

    @action(detail=True, methods=['post'])
    def escalate(self, request, pk=None):
        """Escalate alert"""
        alert = self.get_object()
        serializer = AlertActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        escalation_user_id = serializer.validated_data.get('escalation_user_id')
        reason = serializer.validated_data.get('notes', '')
        
        try:
            from apps.users.models import User
            escalation_user = User.objects.get(id=escalation_user_id)
            
            alert.escalate(escalation_user, reason)
            
            return Response({
                'message': 'Alert escalated successfully'
            })
            
        except User.DoesNotExist:
            return Response({
                'error': 'Escalation user not found'
            }, status=status.HTTP_404_NOT_FOUND)

    @action(detail=True, methods=['post'])
    def dismiss(self, request, pk=None):
        """Dismiss alert"""
        alert = self.get_object()
        
        alert.dismiss(request.user)
        
        return Response({
            'message': 'Alert dismissed successfully'
        })

    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Get alert statistics"""
        user = request.user
        institution = user.institution
        
        # Get date range
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        
        if not start_date:
            start_date = timezone.now().date() - timedelta(days=30)
        else:
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
        
        if not end_date:
            end_date = timezone.now().date()
        else:
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
        
        # Calculate statistics
        stats = Alert.objects.filter(
            institution=institution,
            created_at__date__gte=start_date,
            created_at__date__lte=end_date,
            is_deleted=False
        ).aggregate(
            total=Count('id'),
            active=Count('id', filter=Q(status='active')),
            acknowledged=Count('id', filter=Q(status='acknowledged')),
            resolved=Count('id', filter=Q(status='resolved')),
            critical=Count('id', filter=Q(severity='critical')),
            urgent=Count('id', filter=Q(severity='urgent'))
        )
        
        # Type breakdown
        type_breakdown = Alert.objects.filter(
            institution=institution,
            created_at__date__gte=start_date,
            created_at__date__lte=end_date,
            is_deleted=False
        ).values('alert_type').annotate(
            count=Count('id')
        ).order_by('-count')
        
        # Severity breakdown
        severity_breakdown = Alert.objects.filter(
            institution=institution,
            created_at__date__gte=start_date,
            created_at__date__lte=end_date,
            is_deleted=False
        ).values('severity').annotate(
            count=Count('id')
        ).order_by('-count')
        
        return Response({
            'period': {
                'start_date': start_date,
                'end_date': end_date
            },
            'statistics': stats,
            'type_breakdown': list(type_breakdown),
            'severity_breakdown': list(severity_breakdown)
        })


class NotificationViewSet(viewsets.ModelViewSet):
    """
    Notification viewset
    """
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['notification_type', 'priority', 'in_app_read']
    search_fields = ['title', 'message']
    ordering_fields = ['created_at', 'priority', 'read_at']
    ordering = ['-created_at']

    def get_queryset(self):
        """Filter notifications by user and institution"""
        user = self.request.user
        return Notification.objects.filter(
            recipient=user,
            institution=user.institution
        ).exclude(expires_at__lt=timezone.now())

    @action(detail=True, methods=['post'])
    def mark_as_read(self, request, pk=None):
        """Mark notification as read"""
        notification = self.get_object()
        
        if notification.in_app_read:
            return Response({
                'error': 'Notification already read'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        notification.mark_as_read()
        
        return Response({
            'message': 'Notification marked as read'
        })

    @action(detail=True, methods=['post'])
    def send_email(self, request, pk=None):
        """Send email notification"""
        notification = self.get_object()
        
        if notification.email_sent:
            return Response({
                'error': 'Email already sent'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        success = notification.send_email()
        
        if success:
            return Response({
                'message': 'Email sent successfully'
            })
        else:
            return Response({
                'error': 'Failed to send email',
                'details': notification.email_error
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['post'])
    def send_sms(self, request, pk=None):
        """Send SMS notification"""
        notification = self.get_object()
        
        if notification.sms_sent:
            return Response({
                'error': 'SMS already sent'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        success = notification.send_sms()
        
        if success:
            return Response({
                'message': 'SMS sent successfully'
            })
        else:
            return Response({
                'error': 'Failed to send SMS',
                'details': notification.sms_error
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['post'])
    def send_push(self, request, pk=None):
        """Send push notification"""
        notification = self.get_object()
        
        if notification.push_sent:
            return Response({
                'error': 'Push notification already sent'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        success = notification.send_push()
        
        if success:
            return Response({
                'message': 'Push notification sent successfully'
            })
        else:
            return Response({
                'error': 'Failed to send push notification',
                'details': notification.push_error
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def unread_count(self, request):
        """Get unread notifications count"""
        user = request.user
        
        unread_count = Notification.objects.filter(
            recipient=user,
            institution=user.institution,
            in_app_read=False
        ).exclude(expires_at__lt=timezone.now()).count()
        
        return Response({
            'unread_count': unread_count
        })

    @action(detail=False, methods=['post'])
    def mark_all_as_read(self, request):
        """Mark all notifications as read"""
        user = request.user
        
        notifications = Notification.objects.filter(
            recipient=user,
            institution=user.institution,
            in_app_read=False
        ).exclude(expires_at__lt=timezone.now())
        
        count = notifications.count()
        notifications.update(in_app_read=True, read_at=timezone.now())
        
        return Response({
            'message': f'Marked {count} notifications as read'
        })


class NotificationTemplateViewSet(viewsets.ModelViewSet):
    """
    Notification template viewset
    """
    serializer_class = NotificationTemplateSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['template_type', 'is_active', 'is_default']
    search_fields = ['name', 'subject_template', 'message_template']
    ordering_fields = ['name', 'template_type', 'usage_count']
    ordering = ['name']

    def get_queryset(self):
        """Filter templates by institution"""
        user = self.request.user
        return NotificationTemplate.objects.filter(
            institution=user.institution,
            is_deleted=False
        )

    @action(detail=True, methods=['post'])
    def preview(self, request, pk=None):
        """Preview template with sample data"""
        template = self.get_object()
        
        # Sample context for preview
        sample_context = {
            'student_name': 'John Doe',
            'course_title': 'Introduction to Computer Science',
            'attendance_rate': '85%',
            'date': timezone.now().strftime('%Y-%m-%d'),
            'institution_name': template.institution.name
        }
        
        subject, message = template.render(sample_context)
        
        return Response({
            'subject': subject,
            'message': message,
            'sample_context': sample_context
        })

    @action(detail=True, methods=['post'])
    def set_as_default(self, request, pk=None):
        """Set template as default for its type"""
        template = self.get_object()
        
        # Remove default status from other templates of same type
        NotificationTemplate.objects.filter(
            institution=template.institution,
            template_type=template.template_type,
            is_default=True
        ).update(is_default=False)
        
        # Set this template as default
        template.is_default = True
        template.save()
        
        return Response({
            'message': f'Template set as default for {template.template_type}'
        })


class NotificationPreferenceViewSet(viewsets.ModelViewSet):
    """
    Notification preference viewset
    """
    serializer_class = NotificationPreferenceSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Get user's notification preferences"""
        user = self.request.user
        return NotificationPreference.objects.filter(
            user=user,
            institution=user.institution
        )

    @action(detail=False, methods=['get', 'post', 'put'])
    def my_preferences(self, request):
        """Get or update user's notification preferences"""
        user = request.user
        
        if request.method == 'GET':
            preference, created = NotificationPreference.objects.get_or_create(
                user=user,
                institution=user.institution
            )
            serializer = self.get_serializer(preference)
            return Response(serializer.data)
        
        elif request.method in ['POST', 'PUT']:
            preference, created = NotificationPreference.objects.get_or_create(
                user=user,
                institution=user.institution
            )
            serializer = self.get_serializer(preference, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response(serializer.data)


class NotificationQueueViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Notification queue viewset
    """
    serializer_class = NotificationQueueSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['status', 'priority']
    search_fields = ['notification__title']
    ordering_fields = ['created_at', 'priority', 'status']
    ordering = ['-created_at']

    def get_queryset(self):
        """Filter queue by institution and user role"""
        user = self.request.user
        
        if user.is_super_admin():
            # Super admins can see all queue entries
            return NotificationQueue.objects.filter(institution=user.institution)
        else:
            # Others can only see their own notifications
            return NotificationQueue.objects.filter(
                institution=user.institution,
                notification__recipient=user
            )

    @action(detail=False, methods=['post'])
    def process_queue(self, request):
        """Process notification queue"""
        user = request.user
        
        if not user.is_admin():
            return Response({
                'error': 'Admin access required'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Trigger async task
        process_notification_queue.delay(user.institution.id)
        
        return Response({
            'message': 'Notification queue processing started'
        })

    @action(detail=True, methods=['post'])
    def retry(self, request, pk=None):
        """Retry failed notification"""
        queue_entry = self.get_object()
        
        if queue_entry.status != 'failed':
            return Response({
                'error': 'Can only retry failed notifications'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Reset status and attempts
        queue_entry.status = 'pending'
        queue_entry.attempts = 0
        queue_entry.next_attempt_at = timezone.now()
        queue_entry.error_message = ''
        queue_entry.save()
        
        return Response({
            'message': 'Notification retry scheduled'
        })


class AlertRuleViewSet(viewsets.ModelViewSet):
    """
    Alert rule viewset
    """
    serializer_class = AlertRuleSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['rule_type', 'alert_type', 'severity', 'is_active']
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'created_at', 'trigger_count']
    ordering = ['name']

    def get_queryset(self):
        """Filter rules by institution and user role"""
        user = self.request.user
        queryset = AlertRule.objects.filter(
            institution=user.institution,
            is_deleted=False
        )
        
        # Filter based on user role
        if not user.is_admin():
            # Non-admins can only see active rules
            queryset = queryset.filter(is_active=True)
        
        return queryset

    @action(detail=True, methods=['post'])
    def test(self, request, pk=None):
        """Test alert rule"""
        rule = self.get_object()
        serializer = AlertRuleTestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        test_context = serializer.validated_data['test_context']
        dry_run = serializer.validated_data['dry_run']
        
        # Test the rule
        result = rule.evaluate_condition(test_context)
        
        response_data = {
            'rule_name': rule.name,
            'test_context': test_context,
            'condition_met': result,
            'dry_run': dry_run
        }
        
        if result and not dry_run:
            # Actually trigger the alert
            alert_created = rule.trigger_alert(test_context)
            response_data['alert_created'] = alert_created
        
        return Response(response_data)

    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        """Activate alert rule"""
        rule = self.get_object()
        
        if rule.is_active:
            return Response({
                'error': 'Rule is already active'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        rule.is_active = True
        rule.save()
        
        return Response({
            'message': 'Alert rule activated successfully'
        })

    @action(detail=True, methods=['post'])
    def deactivate(self, request, pk=None):
        """Deactivate alert rule"""
        rule = self.get_object()
        
        if not rule.is_active:
            return Response({
                'error': 'Rule is already inactive'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        rule.is_active = False
        rule.save()
        
        return Response({
            'message': 'Alert rule deactivated successfully'
        })

    @action(detail=False, methods=['post'])
    def evaluate_all(self, request):
        """Evaluate all active alert rules"""
        user = request.user
        
        if not user.is_admin():
            return Response({
                'error': 'Admin access required'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Trigger async task
        evaluate_alert_rules.delay(user.institution.id)
        
        return Response({
            'message': 'Alert rule evaluation started'
        })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def send_bulk_notification(request):
    """
    Send bulk notifications
    """
    serializer = BulkNotificationSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    
    user = request.user
    institution = user.institution
    
    # Prepare notification data
    notification_data = serializer.validated_data
    notification_data['institution_id'] = institution.id
    notification_data['created_by_id'] = user.id
    
    # Trigger async task
    send_bulk_notifications.delay(notification_data)
    
    return Response({
        'message': 'Bulk notification sending started'
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def notification_statistics(request):
    """
    Get notification statistics
    """
    serializer = NotificationStatsSerializer(data=request.query_params)
    serializer.is_valid(raise_exception=True)
    
    user = request.user
    institution = user.institution
    
    start_date = serializer.validated_data['start_date']
    end_date = serializer.validated_data['end_date']
    notification_type = serializer.validated_data.get('notification_type')
    recipient_id = serializer.validated_data.get('recipient_id')
    
    # Build query
    notifications = Notification.objects.filter(
        institution=institution,
        created_at__date__gte=start_date,
        created_at__date__lte=end_date
    )
    
    if notification_type:
        notifications = notifications.filter(notification_type=notification_type)
    
    if recipient_id:
        notifications = notifications.filter(recipient_id=recipient_id)
    
    # Calculate statistics
    stats = notifications.aggregate(
        total=Count('id'),
        email_sent=Count('id', filter=Q(email_sent=True)),
        sms_sent=Count('id', filter=Q(sms_sent=True)),
        push_sent=Count('id', filter=Q(push_sent=True)),
        in_app_read=Count('id', filter=Q(in_app_read=True))
    )
    
    # Type breakdown
    type_breakdown = notifications.values('notification_type').annotate(
        count=Count('id')
    ).order_by('-count')
    
    # Priority breakdown
    priority_breakdown = notifications.values('priority').annotate(
        count=Count('id')
    ).order_by('-count')
    
    return Response({
        'period': {
            'start_date': start_date,
            'end_date': end_date
        },
        'statistics': stats,
        'type_breakdown': list(type_breakdown),
        'priority_breakdown': list(priority_breakdown)
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def cleanup_notifications(request):
    """
    Clean up expired notifications
    """
    user = request.user
    
    if not user.is_admin():
        return Response({
            'error': 'Admin access required'
        }, status=status.HTTP_403_FORBIDDEN)
    
    # Trigger async task
    cleanup_expired_notifications.delay(user.institution.id)
    
    return Response({
        'message': 'Notification cleanup started'
    })
