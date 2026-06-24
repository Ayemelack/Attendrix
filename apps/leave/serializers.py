"""
Leave management serializers for Attendrix API
"""
from rest_framework import serializers
from django.utils import timezone
from apps.leave.models import (
    LeaveType, LeaveBalance, LeaveRequest, LeaveApproval,
    LeaveCalendar, LeaveHoliday, LeaveAnalytics, LeavePolicy
)
from apps.users.serializers import UserSerializer
from apps.departments.serializers import DepartmentSerializer
from apps.courses.serializers import CourseSerializer


class LeaveTypeSerializer(serializers.ModelSerializer):
    """
    Leave type serializer
    """
    class Meta:
        model = LeaveType
        fields = [
            'id', 'name', 'description', 'category',
            'max_days_per_year', 'max_consecutive_days', 'requires_approval',
            'requires_documentation', 'eligible_roles', 'min_employment_months',
            'accrual_frequency', 'accrual_rate', 'carry_forward_allowed',
            'max_carry_forward_days', 'blackout_periods', 'advance_notice_days',
            'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']

    def create(self, validated_data):
        """Create leave type with validation"""
        leave_type = super().create(validated_data)
        
        # Log creation
        from apps.core.models import ActivityLog
        ActivityLog.objects.create(
            user=self.context['request'].user,
            institution=leave_type.institution,
            action_type='create',
            action_description=f'Leave type created: {leave_type.name}',
            severity='low'
        )
        
        return leave_type


class LeaveBalanceSerializer(serializers.ModelSerializer):
    """
    Leave balance serializer
    """
    user_info = UserSerializer(source='user', read_only=True)
    leave_type_info = LeaveTypeSerializer(source='leave_type', read_only=True)
    
    class Meta:
        model = LeaveBalance
        fields = [
            'id', 'user', 'user_info', 'leave_type', 'leave_type_info',
            'accrued_days', 'used_days', 'pending_days', 'available_days',
            'carried_forward_days', 'carry_forward_expiry',
            'period_start', 'period_end', 'last_updated',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'accrued_days', 'used_days', 'pending_days', 'available_days',
            'carried_forward_days', 'last_updated', 'created_at', 'updated_at'
        ]


class LeaveRequestSerializer(serializers.ModelSerializer):
    """
    Leave request serializer
    """
    user_info = UserSerializer(source='user', read_only=True)
    leave_type_info = LeaveTypeSerializer(source='leave_type', read_only=True)
    approver_info = UserSerializer(source='approver', read_only=True)
    delegated_approver_info = UserSerializer(source='delegated_approver', read_only=True)
    
    class Meta:
        model = LeaveRequest
        fields = [
            'id', 'user', 'user_info', 'leave_type', 'leave_type_info',
            'start_date', 'end_date', 'total_days', 'half_day', 'half_day_part',
            'reason', 'priority', 'contact_phone', 'contact_email', 'emergency_contact',
            'supporting_documents', 'medical_certificate',
            'status', 'approver', 'approver_info', 'approval_date', 'approval_notes',
            'delegated_approver', 'delegated_approver_info',
            'requester_comments', 'approver_comments',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'total_days', 'status', 'approver', 'approval_date',
            'created_at', 'updated_at'
        ]

    def validate(self, attrs):
        """Validate leave request"""
        start_date = attrs.get('start_date')
        end_date = attrs.get('end_date')
        
        if start_date and end_date:
            if start_date > end_date:
                raise serializers.ValidationError("Start date cannot be after end date")
            
            # Check if dates are in the past
            if start_date < timezone.now().date():
                raise serializers.ValidationError("Start date cannot be in the past")
        
        # Validate half_day settings
        half_day = attrs.get('half_day', False)
        half_day_part = attrs.get('half_day_part')
        
        if half_day and not half_day_part:
            raise serializers.ValidationError("Half day part is required when half_day is True")
        
        if not half_day and half_day_part:
            raise serializers.ValidationError("Half day part cannot be set when half_day is False")
        
        return attrs

    def create(self, validated_data):
        """Create leave request with balance check"""
        user = self.context['request'].user
        leave_type = validated_data['leave_type']
        start_date = validated_data['start_date']
        end_date = validated_data['end_date']
        
        # Calculate total days
        total_days = self._calculate_total_days(start_date, end_date, validated_data.get('half_day', False))
        
        # Check leave balance
        try:
            balance = LeaveBalance.objects.get(
                user=user,
                leave_type=leave_type,
                period_start__lte=start_date,
                period_end__gte=end_date
            )
            
            if not balance.can_request_leave(total_days):
                raise serializers.ValidationError(
                    f"Insufficient leave balance. Available: {balance.available_days} days, Requested: {total_days} days"
                )
            
            # Add to pending balance
            balance.add_pending_leave(total_days)
            
        except LeaveBalance.DoesNotExist:
            # Create balance if it doesn't exist
            pass
        
        # Create leave request
        leave_request = super().create(validated_data)
        
        # Log creation
        from apps.core.models import ActivityLog
        ActivityLog.objects.create(
            user=user,
            institution=leave_request.institution,
            action_type='create',
            action_description=f'Leave request created: {leave_request.leave_type.name}',
            severity='medium',
            metadata={
                'leave_request_id': leave_request.id,
                'total_days': total_days
            }
        )
        
        return leave_request

    def _calculate_total_days(self, start_date, end_date, half_day):
        """Calculate total days for leave request"""
        if start_date == end_date and half_day:
            return 0.5
        
        # Calculate business days (excluding weekends)
        from datetime import timedelta
        current_date = start_date
        days_count = 0
        
        while current_date <= end_date:
            if current_date.weekday() < 5:  # Monday to Friday
                days_count += 1
            current_date += timedelta(days=1)
        
        return days_count

    def update(self, instance, validated_data):
        """Update leave request"""
        old_status = instance.status
        old_total_days = instance.total_days
        
        leave_request = super().update(instance, validated_data)
        
        # Handle status changes
        if 'status' in validated_data and old_status != validated_data['status']:
            new_status = validated_data['status']
            
            if new_status == 'approved':
                from apps.core.models import ActivityLog
                ActivityLog.objects.create(
                    user=self.context['request'].user,
                    institution=instance.institution,
                    action_type='update',
                    action_description=f'Leave request approved: {instance.leave_type.name}',
                    severity='medium',
                    metadata={
                        'leave_request_id': instance.id,
                        'approver': instance.approver.get_full_name() if instance.approver else None
                    }
                )
            elif new_status == 'rejected':
                from apps.core.models import ActivityLog
                ActivityLog.objects.create(
                    user=self.context['request'].user,
                    institution=instance.institution,
                    action_type='update',
                    action_description=f'Leave request rejected: {instance.leave_type.name}',
                    severity='medium',
                    metadata={
                        'leave_request_id': instance.id,
                        'approver': instance.approver.get_full_name() if instance.approver else None
                    }
                )
            elif new_status == 'cancelled':
                from apps.core.models import ActivityLog
                ActivityLog.objects.create(
                    user=self.context['request'].user,
                    institution=instance.institution,
                    action_type='update',
                    action_description=f'Leave request cancelled: {instance.leave_type.name}',
                    severity='low',
                    metadata={
                        'leave_request_id': instance.id
                    }
                )
        
        return leave_request


class LeaveApprovalSerializer(serializers.ModelSerializer):
    """
    Leave approval serializer
    """
    approver_info = UserSerializer(source='approver', read_only=True)
    delegated_by_info = UserSerializer(source='delegated_by', read_only=True)
    escalated_to_info = UserSerializer(source='escalated_to', read_only=True)
    leave_request_info = LeaveRequestSerializer(source='leave_request', read_only=True)
    
    class Meta:
        model = LeaveApproval
        fields = [
            'id', 'leave_request', 'leave_request_info', 'approver', 'approver_info',
            'approval_type', 'decision', 'comments', 'decision_date',
            'delegated_by', 'delegated_by_info', 'delegation_reason',
            'escalated_to', 'escalated_to_info', 'escalation_reason',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['decision_date', 'created_at', 'updated_at']

    def create(self, validated_data):
        """Create leave approval"""
        approval = super().create(validated_data)
        
        # Log creation
        from apps.core.models import ActivityLog
        ActivityLog.objects.create(
            user=approval.approver,
            institution=approval.institution,
            action_type='create',
            action_description=f'Leave approval created: {approval.approval_type}',
            severity='medium',
            metadata={
                'leave_request_id': approval.leave_request.id,
                'approver': approval.approver.get_full_name()
            }
        )
        
        return approval


class LeaveCalendarSerializer(serializers.ModelSerializer):
    """
    Leave calendar serializer
    """
    user_info = UserSerializer(source='user', read_only=True)
    department_info = DepartmentSerializer(source='department', read_only=True)
    course_info = CourseSerializer(source='course', read_only=True)
    
    class Meta:
        model = LeaveCalendar
        fields = [
            'id', 'calendar_type', 'name', 'description',
            'user', 'user_info', 'department', 'department_info',
            'course', 'course_info', 'is_public', 'show_weekends',
            'show_holidays', 'default_view',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']


class LeaveHolidaySerializer(serializers.ModelSerializer):
    """
    Leave holiday serializer
    """
    class Meta:
        model = LeaveHoliday
        fields = [
            'id', 'name', 'description', 'holiday_type', 'date',
            'is_recurring', 'recurrence_pattern',
            'affects_leave', 'affects_attendance',
            'color', 'icon', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']


class LeaveAnalyticsSerializer(serializers.ModelSerializer):
    """
    Leave analytics serializer
    """
    class Meta:
        model = LeaveAnalytics
        fields = [
            'id', 'analytics_type', 'reference_id', 'reference_date',
            'total_requests', 'approved_requests', 'rejected_requests',
            'pending_requests', 'cancelled_requests',
            'total_leave_days', 'approved_leave_days',
            'approval_rate', 'rejection_rate', 'average_days_per_request',
            'trend_percentage', 'trend_direction',
            'metadata', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'total_requests', 'approved_requests', 'rejected_requests',
            'pending_requests', 'cancelled_requests',
            'total_leave_days', 'approved_leave_days',
            'approval_rate', 'rejection_rate', 'average_days_per_request',
            'trend_percentage', 'trend_direction', 'created_at', 'updated_at'
        ]


class LeavePolicySerializer(serializers.ModelSerializer):
    """
    Leave policy serializer
    """
    class Meta:
        model = LeavePolicy
        fields = [
            'id', 'institution',
            'max_concurrent_leaves', 'advance_notice_days',
            'approval_workflow', 'auto_approve_days',
            'working_days_only', 'include_weekends', 'exclude_holidays',
            'notify_requester', 'notify_approver', 'notify_department_head',
            'require_documents_for_days', 'allowed_document_types',
            'carry_forward_enabled', 'max_carry_forward_days',
            'carry_forward_expiry_months',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']


class BulkLeaveRequestSerializer(serializers.Serializer):
    """
    Bulk leave request serializer
    """
    leave_requests = LeaveRequestSerializer(many=True)
    
    class Meta:
        fields = ['leave_requests']


class LeaveRequestActionSerializer(serializers.Serializer):
    """
    Leave request action serializer
    """
    action = serializers.ChoiceField(choices=[
        ('approve', 'Approve'),
        ('reject', 'Reject'),
        ('cancel', 'Cancel'),
        ('escalate', 'Escalate'),
    ])
    comments = serializers.CharField(required=False, allow_blank=True, max_length=500)
    escalate_to_id = serializers.UUIDField(required=False)
    
    def validate(self, attrs):
        """Validate action parameters"""
        action = attrs.get('action')
        
        if action == 'escalate' and not attrs.get('escalate_to_id'):
            raise serializers.ValidationError("Escalation user ID is required for escalate action")
        
        if action in ['approve', 'reject'] and not attrs.get('comments'):
            raise serializers.ValidationError("Comments are required for approve and reject actions")
        
        return attrs


class LeaveBalanceUpdateSerializer(serializers.Serializer):
    """
    Leave balance update serializer
    """
    user_id = serializers.UUIDField()
    leave_type_id = serializers.UUIDField()
    adjustment_type = serializers.ChoiceField(choices=[
        ('accrual', 'Accrual'),
        ('manual_adjustment', 'Manual Adjustment'),
        ('carry_forward', 'Carry Forward'),
    ])
    days = serializers.FloatField(min_value=0)
    reason = serializers.CharField(max_length=500)
    effective_date = serializers.DateField(required=False)
    
    def validate(self, attrs):
        """Validate balance update parameters"""
        adjustment_type = attrs.get('adjustment_type')
        
        if adjustment_type == 'accrual' and not attrs.get('effective_date'):
            raise serializers.ValidationError("Effective date is required for accrual adjustments")
        
        return attrs


class LeaveReportSerializer(serializers.Serializer):
    """
    Leave report serializer
    """
    report_type = serializers.ChoiceField(choices=[
        ('summary', 'Summary Report'),
        ('balance', 'Balance Report'),
        ('trend', 'Trend Report'),
        ('department', 'Department Report'),
        ('leave_type', 'Leave Type Report'),
        ('user', 'User Report'),
    ])
    
    # Date range
    start_date = serializers.DateField()
    end_date = serializers.DateField()
    
    # Filters
    user_ids = serializers.ListField(child=serializers.UUIDField(), required=False)
    department_ids = serializers.ListField(child=serializers.UUIDField(), required=False)
    leave_type_ids = serializers.ListField(child=serializers.UUIDField(), required=False)
    status = serializers.ChoiceField(
        choices=['all', 'approved', 'rejected', 'pending', 'cancelled'],
        default='all',
        required=False
    )
    
    # Output format
    format = serializers.ChoiceField(choices=['json', 'csv', 'pdf'], default='json')
    
    # Additional options
    include_details = serializers.BooleanField(default=True)
    include_analytics = serializers.BooleanField(default=True)
    
    def validate(self, attrs):
        """Validate report parameters"""
        start_date = attrs.get('start_date')
        end_date = attrs.get('end_date')
        
        if start_date and end_date:
            if start_date > end_date:
                raise serializers.ValidationError("Start date cannot be after end date")
            
            # Check date range is not too large
            if (end_date - start_date).days > 365:
                raise serializers.ValidationError("Report date range cannot exceed 1 year")
        
        return attrs


class LeaveCalendarEventSerializer(serializers.Serializer):
    """
    Leave calendar event serializer
    """
    calendar_id = serializers.UUIDField()
    start_date = serializers.DateField()
    end_date = serializers.DateField()
    event_type = serializers.ChoiceField(choices=[
        ('leave', 'Leave'),
        ('holiday', 'Holiday'),
        ('event', 'Event'),
    ])
    title = serializers.CharField(max_length=200)
    description = serializers.CharField(max_length=500, required=False)
    color = serializers.CharField(max_length=7, required=False)
    
    def validate(self, attrs):
        """Validate calendar event"""
        start_date = attrs.get('start_date')
        end_date = attrs.get('end_date')
        
        if start_date and end_date:
            if start_date > end_date:
                raise serializers.ValidationError("Start date cannot be after end date")
        
        return attrs
