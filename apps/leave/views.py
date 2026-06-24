"""
Leave management views for Attendrix - Complete leave workflow system
"""
from rest_framework import status, generics, viewsets
from rest_framework.decorators import api_view, permission_classes, action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from django.utils import timezone
from django.db.models import Q, Count, Avg, Sum
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from datetime import datetime, timedelta
from apps.core.models import ActivityLog
from apps.core.permissions import IsInstitutionAdmin, IsLecturer
from apps.leave.models import (
    LeaveType, LeaveBalance, LeaveRequest, LeaveApproval,
    LeaveCalendar, LeaveHoliday, LeaveAnalytics, LeavePolicy
)
from apps.leave.serializers import (
    LeaveTypeSerializer, LeaveBalanceSerializer, LeaveRequestSerializer,
    LeaveApprovalSerializer, LeaveCalendarSerializer, LeaveHolidaySerializer,
    LeaveAnalyticsSerializer, LeavePolicySerializer, BulkLeaveRequestSerializer,
    LeaveRequestActionSerializer, LeaveBalanceUpdateSerializer, LeaveReportSerializer,
    LeaveCalendarEventSerializer
)
from apps.leave.tasks import (
    process_leave_balance_accruals, generate_leave_analytics,
    send_leave_notifications, cleanup_old_leave_data,
    check_leave_conflicts
)
import json


class LeaveTypeViewSet(viewsets.ModelViewSet):
    """
    Leave type viewset
    """
    serializer_class = LeaveTypeSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['category', 'requires_approval', 'is_active']
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'category', 'created_at']
    ordering = ['name']

    def get_queryset(self):
        """Filter leave types by institution"""
        user = self.request.user
        return LeaveType.objects.filter(
            institution=user.institution,
            is_deleted=False
        )

    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        """Activate leave type"""
        leave_type = self.get_object()
        
        if leave_type.is_active:
            return Response({
                'error': 'Leave type is already active'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        leave_type.is_active = True
        leave_type.save()
        
        return Response({
            'message': 'Leave type activated successfully'
        })

    @action(detail=True, methods=['post'])
    def deactivate(self, request, pk=None):
        """Deactivate leave type"""
        leave_type = self.get_object()
        
        if not leave_type.is_active:
            return Response({
                'error': 'Leave type is already inactive'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        leave_type.is_active = False
        leave_type.save()
        
        return Response({
            'message': 'Leave type deactivated successfully'
        })

    @action(detail=False, methods=['get'])
    def active_types(self, request):
        """Get active leave types"""
        user = request.user
        active_types = LeaveType.objects.filter(
            institution=user.institution,
            is_active=True,
            is_deleted=False
        )
        
        # Filter by user role if specified
        if not user.is_admin():
            active_types = active_types.filter(
                eligible_roles__contains=[user.role]
            )
        
        serializer = self.get_serializer(active_types, many=True)
        return Response(serializer.data)


class LeaveBalanceViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Leave balance viewset
    """
    serializer_class = LeaveBalanceSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['leave_type']
    search_fields = ['user__first_name', 'user__last_name']
    ordering_fields = ['period_start', 'available_days']
    ordering = ['-period_start']

    def get_queryset(self):
        """Filter leave balances by user and institution"""
        user = self.request.user
        return LeaveBalance.objects.filter(
            user=user,
            institution=user.institution
        )

    @action(detail=False, methods=['get'])
    def my_balances(self, request):
        """Get current user's leave balances"""
        user = request.user
        
        # Get current period (current year)
        current_date = timezone.now().date()
        period_start = current_date.replace(month=1, day=1)
        period_end = current_date.replace(month=12, day=31)
        
        balances = LeaveBalance.objects.filter(
            user=user,
            institution=user.institution,
            period_start=period_start,
            period_end=period_end
        ).select_related('leave_type')
        
        serializer = self.get_serializer(balances, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['post'])
    def update_balance(self, request):
        """Update leave balance"""
        serializer = LeaveBalanceUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        user = request.user
        
        if not user.is_admin():
            return Response({
                'error': 'Admin access required'
            }, status=status.HTTP_403_FORBIDDEN)
        
        validated_data = serializer.validated_data
        user_id = validated_data['user_id']
        leave_type_id = validated_data['leave_type_id']
        adjustment_type = validated_data['adjustment_type']
        days = validated_data['days']
        reason = validated_data['reason']
        effective_date = validated_data.get('effective_date')
        
        try:
            # Get user and leave type
            target_user = User.objects.get(id=user_id, institution=user.institution)
            leave_type = LeaveType.objects.get(id=leave_type_id, institution=user.institution)
            
            # Get or create balance for the period
            if effective_date:
                period_start = effective_date.replace(month=1, day=1)
                period_end = effective_date.replace(month=12, day=31)
            else:
                current_date = timezone.now().date()
                period_start = current_date.replace(month=1, day=1)
                period_end = current_date.replace(month=12, day=31)
            
            balance, created = LeaveBalance.objects.get_or_create(
                user=target_user,
                leave_type=leave_type,
                period_start=period_start,
                period_end=period_end
            )
            
            # Apply adjustment
            if adjustment_type == 'accrual':
                balance.accrued_days += days
                balance.available_days += days
            elif adjustment_type == 'manual_adjustment':
                balance.available_days += days
            elif adjustment_type == 'carry_forward':
                balance.carried_forward_days += days
                balance.available_days += days
            
            balance.save()
            
            # Log adjustment
            ActivityLog.objects.create(
                user=request.user,
                institution=user.institution,
                action_type='update',
                action_description=f'Leave balance adjusted: {adjustment_type} {days} days for {target_user.get_full_name()}',
                severity='medium',
                metadata={
                    'adjustment_type': adjustment_type,
                    'days': days,
                    'reason': reason,
                    'leave_type_id': leave_type_id,
                    'user_id': user_id
                }
            )
            
            return Response({
                'message': 'Leave balance updated successfully',
                'new_balance': balance.available_days
            })
            
        except User.DoesNotExist:
            return Response({
                'error': 'User not found'
            }, status=status.HTTP_404_NOT_FOUND)
        except LeaveType.DoesNotExist:
            return Response({
                'error': 'Leave type not found'
            }, status=status.HTTP_404_NOT_FOUND)


class LeaveRequestViewSet(viewsets.ModelViewSet):
    """
    Leave request viewset
    """
    serializer_class = LeaveRequestSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['status', 'priority', 'leave_type', 'user']
    search_fields = ['reason', 'requester_comments']
    ordering_fields = ['created_at', 'start_date', 'priority']
    ordering = ['-created_at']

    def get_queryset(self):
        """Filter leave requests by institution and user role"""
        user = self.request.user
        queryset = LeaveRequest.objects.filter(
            institution=user.institution,
            is_deleted=False
        )
        
        # Filter based on user role
        if user.is_student():
            # Students can only see their own requests
            queryset = queryset.filter(user=user)
        elif user.is_lecturer():
            # Lecturers can see requests for their courses
            queryset = queryset.filter(
                Q(user=user) |
                Q(user__courseenrollments__course__lecturer=user)
            )
        elif user.is_institution_admin():
            # Institution admins can see all requests in their institution
            queryset = queryset.filter(user__institution=user.institution)
        elif user.is_super_admin():
            # Super admins can see all requests
            pass
        
        return queryset.distinct()

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """Approve leave request"""
        leave_request = self.get_object()
        serializer = LeaveRequestActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        comments = serializer.validated_data.get('comments', '')
        
        if leave_request.status != 'pending':
            return Response({
                'error': 'Can only approve pending requests'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        leave_request.approve(request.user, comments)
        
        # Send notifications
        send_leave_notifications.delay(
            leave_request.id,
            'approved',
            request.user.id
        )
        
        return Response({
            'message': 'Leave request approved successfully'
        })

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """Reject leave request"""
        leave_request = self.get_object()
        serializer = LeaveRequestActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        comments = serializer.validated_data.get('comments', '')
        
        if leave_request.status != 'pending':
            return Response({
                'error': 'Can only reject pending requests'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        leave_request.reject(request.user, comments)
        
        # Send notifications
        send_leave_notifications.delay(
            leave_request.id,
            'rejected',
            request.user.id
        )
        
        return Response({
            'message': 'Leave request rejected successfully'
        })

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """Cancel leave request"""
        leave_request = self.get_object()
        
        if leave_request.status in ['approved', 'completed']:
            return Response({
                'error': 'Cannot cancel approved or completed requests'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        leave_request.cancel()
        
        # Send notifications
        send_leave_notifications.delay(
            leave_request.id,
            'cancelled',
            request.user.id
        )
        
        return Response({
            'message': 'Leave request cancelled successfully'
        })

    @action(detail=True, methods=['post'])
    def escalate(self, request, pk=None):
        """Escalate leave request"""
        leave_request = self.get_object()
        serializer = LeaveRequestActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        escalate_to_id = serializer.validated_data.get('escalate_to_id')
        reason = serializer.validated_data.get('comments', '')
        
        try:
            from apps.users.models import User
            escalate_to_user = User.objects.get(id=escalate_to_id)
            
            # Create escalation approval
            LeaveApproval.objects.create(
                institution=leave_request.institution,
                leave_request=leave_request,
                approver=request.user,
                approval_type='escalated',
                decision='pending',
                escalated_to=escalate_to_user,
                escalation_reason=reason
            )
            
            return Response({
                'message': 'Leave request escalated successfully'
            })
            
        except User.DoesNotExist:
            return Response({
                'error': 'Escalation user not found'
            }, status=status.HTTP_404_NOT_FOUND)

    @action(detail=False, methods=['post'])
    def bulk_create(self, request):
        """Create multiple leave requests"""
        serializer = BulkLeaveRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        user = request.user
        leave_requests_data = serializer.validated_data['leave_requests']
        
        created_requests = []
        errors = []
        
        for request_data in leave_requests_data:
            # Add user to request data
            request_data['user'] = user.id
            request_data['institution'] = user.institution.id
            
            # Validate and create request
            request_serializer = LeaveRequestSerializer(data=request_data)
            request_serializer.is_valid(raise_exception=True)
            
            try:
                leave_request = request_serializer.save()
                created_requests.append(leave_request.id)
            except Exception as e:
                errors.append(f"Error creating request: {str(e)}")
        
        return Response({
            'message': f'Created {len(created_requests)} leave requests',
            'created_requests': created_requests,
            'errors': errors
        })

    @action(detail=False, methods=['get'])
    def my_requests(self, request):
        """Get current user's leave requests"""
        user = request.user
        requests = self.get_queryset().filter(user=user)
        
        page = self.paginate_queryset(requests)
        serializer = self.get_serializer(page, many=True)
        return self.get_paginated_response(serializer.data)

    @action(detail=False, methods=['get'])
    def pending_approval(self, request):
        """Get leave requests pending approval for current user"""
        user = request.user
        
        if not user.is_admin():
            return Response({
                'error': 'Admin access required'
            }, status=status.HTTP_403_FORBIDDEN)
        
        pending_requests = LeaveRequest.objects.filter(
            institution=user.institution,
            status='pending',
            is_deleted=False
        ).select_related('user', 'leave_type', 'approver')
        
        page = self.paginate_queryset(pending_requests)
        serializer = self.get_serializer(page, many=True)
        return self.get_paginated_response(serializer.data)


class LeaveApprovalViewSet(viewsets.ModelViewSet):
    """
    Leave approval viewset
    """
    serializer_class = LeaveApprovalSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['approval_type', 'decision', 'approver']
    search_fields = ['comments', 'delegation_reason']
    ordering_fields = ['created_at', 'decision_date']
    ordering = ['-created_at']

    def get_queryset(self):
        """Filter approvals by institution and user role"""
        user = self.request.user
        queryset = LeaveApproval.objects.filter(
            institution=user.institution
        )
        
        # Filter based on user role
        if user.is_student():
            # Students can only see approvals for their requests
            queryset = queryset.filter(leave_request__user=user)
        elif user.is_lecturer():
            # Lecturers can see approvals for their courses
            queryset = queryset.filter(
                Q(leave_request__user=user) |
                Q(leave_request__user__courseenrollments__course__lecturer=user)
            )
        elif user.is_institution_admin():
            # Institution admins can see all approvals in their institution
            pass
        elif user.is_super_admin():
            # Super admins can see all approvals
            pass
        
        return queryset.distinct()

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """Approve leave approval"""
        approval = self.get_object()
        
        if approval.decision != 'pending':
            return Response({
                'error': 'Approval already decided'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        approval.approve()
        
        # Update leave request status
        leave_request = approval.leave_request
        leave_request.status = 'approved'
        leave_request.approver = approval.approver
        leave_request.approval_date = timezone.now()
        leave_request.save()
        
        # Send notifications
        send_leave_notifications.delay(
            leave_request.id,
            'approved',
            approval.approver.id
        )
        
        return Response({
            'message': 'Leave approval approved successfully'
        })

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """Reject leave approval"""
        approval = self.get_object()
        
        if approval.decision != 'pending':
            return Response({
                'error': 'Approval already decided'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        approval.reject()
        
        # Update leave request status
        leave_request = approval.leave_request
        leave_request.status = 'rejected'
        leave_request.approver = approval.approver
        leave_request.approval_date = timezone.now()
        leave_request.save()
        
        # Send notifications
        send_leave_notifications.delay(
            leave_request.id,
            'rejected',
            approval.approver.id
        )
        
        return Response({
            'message': 'Leave approval rejected successfully'
        })


class LeaveCalendarViewSet(viewsets.ModelViewSet):
    """
    Leave calendar viewset
    """
    serializer_class = LeaveCalendarSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['calendar_type', 'is_public']
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'created_at']
    ordering = ['name']

    def get_queryset(self):
        """Filter calendars by institution and user role"""
        user = self.request.user
        queryset = LeaveCalendar.objects.filter(
            institution=user.institution,
            is_deleted=False
        )
        
        # Filter based on user role
        if user.is_student():
            # Students can see their own calendars and public ones
            queryset = queryset.filter(
                Q(user=user) | Q(is_public=True)
            )
        elif user.is_lecturer():
            # Lecturers can see their calendars, department calendars, and public ones
            queryset = queryset.filter(
                Q(user=user) |
                Q(department=user.department) |
                Q(is_public=True)
            )
        elif user.is_institution_admin():
            # Institution admins can see all calendars in their institution
            queryset = queryset.filter(user__institution=user.institution)
        elif user.is_super_admin():
            # Super admins can see all calendars
            pass
        
        return queryset.distinct()

    @action(detail=True, methods=['get'])
    def events(self, request, pk=None):
        """Get calendar events"""
        calendar = self.get_object()
        
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        
        if not start_date:
            start_date = timezone.now().date().replace(day=1)
        else:
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
        
        if not end_date:
            end_date = timezone.now().date().replace(day=31)
        else:
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
        
        events = []
        
        # Add leave requests
        if calendar.calendar_type in ['personal', 'department', 'course']:
            leave_requests = LeaveRequest.objects.filter(
                institution=calendar.institution,
                status='approved',
                start_date__gte=start_date,
                end_date__lte=end_date,
                is_deleted=False
            )
            
            if calendar.calendar_type == 'personal' and calendar.user:
                leave_requests = leave_requests.filter(user=calendar.user)
            elif calendar.calendar_type == 'department' and calendar.department:
                leave_requests = leave_requests.filter(
                    user__department=calendar.department
                )
            elif calendar.calendar_type == 'course' and calendar.course:
                leave_requests = leave_requests.filter(
                    user__courseenrollments__course=calendar.course
                )
            
            for leave_request in leave_requests:
                events.append({
                    'id': f"leave_{leave_request.id}",
                    'title': f"{leave_request.user.get_full_name()} - {leave_request.leave_type.name}",
                    'start': leave_request.start_date.isoformat(),
                    'end': leave_request.end_date.isoformat(),
                    'type': 'leave',
                    'color': '#FF5722',
                    'description': leave_request.reason
                })
        
        # Add holidays if enabled
        if calendar.show_holidays:
            holidays = LeaveHoliday.objects.filter(
                institution=calendar.institution,
                date__gte=start_date,
                date__lte=end_date,
                is_deleted=False
            )
            
            for holiday in holidays:
                events.append({
                    'id': f"holiday_{holiday.id}",
                    'title': holiday.name,
                    'start': holiday.date.isoformat(),
                    'end': holiday.date.isoformat(),
                    'type': 'holiday',
                    'color': holiday.color,
                    'description': holiday.description
                })
        
        return Response(events)


class LeaveHolidayViewSet(viewsets.ModelViewSet):
    """
    Leave holiday viewset
    """
    serializer_class = LeaveHolidaySerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['holiday_type', 'is_recurring']
    search_fields = ['name', 'description']
    ordering_fields = ['date', 'name']
    ordering = ['date']

    def get_queryset(self):
        """Filter holidays by institution"""
        user = self.request.user
        return LeaveHoliday.objects.filter(
            institution=user.institution,
            is_deleted=False
        )

    @action(detail=False, methods=['post'])
    def bulk_create(self, request):
        """Create multiple holidays"""
        holidays_data = request.data.get('holidays', [])
        
        created_holidays = []
        errors = []
        
        for holiday_data in holidays_data:
            try:
                holiday = LeaveHoliday.objects.create(
                    institution=self.request.user.institution,
                    **holiday_data
                )
                created_holidays.append(holiday.id)
            except Exception as e:
                errors.append(f"Error creating holiday: {str(e)}")
        
        return Response({
            'message': f'Created {len(created_holidays)} holidays',
            'created_holidays': created_holidays,
            'errors': errors
        })


class LeaveAnalyticsViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Leave analytics viewset
    """
    serializer_class = LeaveAnalyticsSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['analytics_type', 'trend_direction']
    search_fields = ['metadata']
    ordering_fields = ['reference_date', 'analytics_type']
    ordering = ['-reference_date']

    def get_queryset(self):
        """Filter analytics by institution and user role"""
        user = self.request.user
        queryset = LeaveAnalytics.objects.filter(
            institution=user.institution
        )
        
        # Filter based on user role
        if user.is_student():
            # Students can only see their own analytics
            queryset = queryset.filter(
                analytics_type='user',
                reference_id=user.id
            )
        elif user.is_lecturer():
            # Lecturers can see their course analytics
            queryset = queryset.filter(
                Q(analytics_type='course') |
                Q(analytics_type='user', reference_id=user.id)
            )
        elif user.is_institution_admin():
            # Institution admins can see department and institution analytics
            queryset = queryset.filter(
                analytics_type__in=['department', 'institution']
            )
        elif user.is_super_admin():
            # Super admins can see all analytics
            pass
        
        return queryset.distinct()

    @action(detail=False, methods=['get'])
    def dashboard_summary(self, request):
        """Get dashboard summary analytics"""
        user = request.user
        institution = user.institution
        
        # Get current date range
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=30)
        
        # Get summary analytics
        summary_analytics = LeaveAnalytics.objects.filter(
            institution=institution,
            analytics_type='summary',
            reference_date=end_date
        ).first()
        
        # Get trend analytics
        trend_analytics = LeaveAnalytics.objects.filter(
            institution=institution,
            analytics_type='trend',
            reference_date__gte=start_date,
            reference_date__lte=end_date
        ).order_by('reference_date')
        
        # Get department analytics if applicable
        department_analytics = []
        if user.is_institution_admin() or user.is_super_admin():
            department_analytics = LeaveAnalytics.objects.filter(
                institution=institution,
                analytics_type='department',
                reference_date=end_date
            ).select_related('reference_id')
        
        return Response({
            'period': {
                'start_date': start_date,
                'end_date': end_date
            },
            'summary': LeaveAnalyticsSerializer(summary_analytics).data if summary_analytics else None,
            'trends': LeaveAnalyticsSerializer(trend_analytics, many=True).data,
            'departments': LeaveAnalyticsSerializer(department_analytics, many=True).data
        })


class LeavePolicyViewSet(viewsets.ModelViewSet):
    """
    Leave policy viewset
    """
    serializer_class = LeavePolicySerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        """Get institution's leave policy"""
        user = self.request.user
        policy, created = LeavePolicy.objects.get_or_create(
            institution=user.institution
        )
        return policy

    @action(detail=False, methods=['get', 'post', 'put'])
    def policy(self, request):
        """Get or update institution's leave policy"""
        user = request.user
        
        if not user.is_admin():
            return Response({
                'error': 'Admin access required'
            }, status=status.HTTP_403_FORBIDDEN)
        
        policy = self.get_object()
        
        if request.method == 'GET':
            serializer = self.get_serializer(policy)
            return Response(serializer.data)
        elif request.method in ['POST', 'PUT']:
            serializer = self.get_serializer(policy, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            
            return Response({
                'message': 'Leave policy updated successfully'
            })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def generate_leave_report(request):
    """
    Generate leave report
    """
    serializer = LeaveReportSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    
    user = request.user
    institution = user.institution
    
    # Get report parameters
    report_type = serializer.validated_data['report_type']
    start_date = serializer.validated_data['start_date']
    end_date = serializer.validated_data['end_date']
    
    # Get filters
    user_ids = serializer.validated_data.get('user_ids', [])
    department_ids = serializer.validated_data.get('department_ids', [])
    leave_type_ids = serializer.validated_data.get('leave_type_ids', [])
    status = serializer.validated_data.get('status', 'all')
    format_type = serializer.validated_data['format']
    include_details = serializer.validated_data.get('include_details', True)
    include_analytics = serializer.validated_data.get('include_analytics', True)
    
    # Trigger async report generation
    from apps.leave.tasks import generate_leave_report
    report_data = {
        'institution_id': institution.id,
        'report_type': report_type,
        'start_date': start_date,
        'end_date': end_date,
        'user_ids': user_ids,
        'department_ids': department_ids,
        'leave_type_ids': leave_type_ids,
        'status': status,
        'format': format_type,
        'include_details': include_details,
        'include_analytics': include_analytics,
        'requested_by': user.id
    }
    
    generate_leave_report.delay(report_data)
    
    return Response({
        'message': 'Leave report generation started',
        'report_type': report_type,
        'format': format_type
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def check_leave_conflicts(request):
    """
    Check for leave conflicts
    """
    user = request.user
    institution = user.institution
    
    # Get parameters
    start_date = request.data.get('start_date')
    end_date = request.data.get('end_date')
    user_id = request.data.get('user_id')
    
    # Trigger conflict check
    check_leave_conflicts.delay(
        institution.id,
        start_date,
        end_date,
        user_id
    )
    
    return Response({
        'message': 'Leave conflict check started'
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def add_calendar_event(request):
    """
    Add event to leave calendar
    """
    serializer = LeaveCalendarEventSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    
    user = request.user
    calendar_id = serializer.validated_data['calendar_id']
    
    try:
        calendar = LeaveCalendar.objects.get(
            id=calendar_id,
            institution=user.institution
        )
        
        # Check if user can add events to this calendar
        if not _can_add_to_calendar(user, calendar):
            return Response({
                'error': 'Permission denied'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Create event (this would be stored in a separate Event model)
        event_data = serializer.validated_data
        event_data['calendar_id'] = calendar_id
        event_data['created_by'] = user.id
        
        # For now, just return success
        return Response({
            'message': 'Event added to calendar successfully',
            'event': event_data
        })
        
    except LeaveCalendar.DoesNotExist:
        return Response({
                'error': 'Calendar not found'
            }, status=status.HTTP_404_NOT_FOUND)


def _can_add_to_calendar(user, calendar):
    """Check if user can add events to calendar"""
    if calendar.calendar_type == 'personal':
        return calendar.user == user
    elif calendar.calendar_type == 'department':
        return calendar.department and calendar.department.head == user
    elif calendar.calendar_type == 'course':
        return calendar.course and calendar.course.lecturer == user
    elif calendar.calendar_type == 'institution':
        return user.is_institution_admin() or user.is_super_admin()
    
    return False
