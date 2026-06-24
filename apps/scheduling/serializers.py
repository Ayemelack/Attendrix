"""
Scheduling serializers for Attendrix API
"""
from rest_framework import serializers
from django.utils import timezone
from apps.core.models import ActivityLog
from apps.scheduling.models import (
    Schedule, ScheduleOccurrence, ScheduleTemplate, ScheduleConflict,
    ScheduleAdjustment, SchedulePreference, ScheduleAnalytics
)
from apps.users.serializers import UserSerializer
from apps.courses.serializers import CourseSerializer
from apps.departments.serializers import DepartmentResourceSerializer


class ScheduleSerializer(serializers.ModelSerializer):
    """
    Schedule serializer
    """
    course_info = CourseSerializer(source='course', read_only=True)
    lecturer_info = UserSerializer(source='lecturer', read_only=True)
    assistant_lecturer_info = UserSerializer(source='assistant_lecturer', read_only=True)
    room_info = DepartmentResourceSerializer(source='room', read_only=True)
    
    # Computed fields
    duration_minutes = serializers.SerializerMethodField()
    occurrence_count = serializers.SerializerMethodField()
    next_occurrence = serializers.SerializerMethodField()
    
    class Meta:
        model = Schedule
        fields = [
            'id', 'title', 'description', 'schedule_type', 'course', 'course_info',
            'start_date', 'end_date', 'start_time', 'end_time', 'timezone',
            'recurrence_type', 'recurrence_pattern', 'max_occurrences',
            'location', 'room', 'room_info', 'virtual_meeting_url',
            'lecturer', 'lecturer_info', 'assistant_lecturer', 'assistant_lecturer_info',
            'max_participants', 'is_mandatory', 'requires_registration',
            'is_active', 'is_published', 'is_cancelled',
            'has_conflicts', 'conflict_details',
            'duration_minutes', 'occurrence_count', 'next_occurrence',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['has_conflicts', 'conflict_details', 'created_at', 'updated_at']

    def get_duration_minutes(self, obj):
        """Calculate duration in minutes"""
        start = timezone.datetime.strptime(str(obj.start_time), '%H:%M:%S')
        end = timezone.datetime.strptime(str(obj.end_time), '%H:%M:%S')
        return (end - start).total_seconds() / 60

    def get_occurrence_count(self, obj):
        """Get number of occurrences"""
        return obj.occurrences.filter(is_deleted=False).count()

    def get_next_occurrence(self, obj):
        """Get next occurrence date"""
        next_occ = obj.occurrences.filter(
            occurrence_date__gte=timezone.now().date(),
            status='scheduled',
            is_deleted=False
        ).order_by('occurrence_date').first()
        
        if next_occ:
            return {
                'date': next_occ.occurrence_date,
                'start_time': next_occ.start_time,
                'end_time': next_occ.end_time
            }
        return None

    def validate(self, attrs):
        """Validate schedule data"""
        if attrs.get('start_date') and attrs.get('end_date'):
            if attrs['start_date'] > attrs['end_date']:
                raise serializers.ValidationError("Start date cannot be after end date")
        
        if attrs.get('start_time') and attrs.get('end_time'):
            if attrs['start_time'] >= attrs['end_time']:
                raise serializers.ValidationError("Start time must be before end time")
        
        return attrs

    def create(self, validated_data):
        """Create schedule with conflict detection"""
        schedule = super().create(validated_data)
        
        # Detect conflicts
        schedule.detect_conflicts()
        
        # Log activity
        ActivityLog.objects.create(
            user=self.context['request'].user,
            institution=schedule.institution,
            action_type='schedule_create',
            action_description=f'Schedule created: {schedule.title}',
            severity='low'
        )
        
        return schedule

    def update(self, instance, validated_data):
        """Update schedule with conflict detection"""
        old_values = {
            'title': instance.title,
            'start_date': instance.start_date,
            'end_date': instance.end_date,
            'start_time': instance.start_time,
            'end_time': instance.end_time,
            'lecturer': instance.lecturer,
            'room': instance.room
        }
        
        schedule = super().update(instance, validated_data)
        
        # Detect conflicts if critical fields changed
        critical_fields = ['start_date', 'end_date', 'start_time', 'end_time', 'lecturer', 'room']
        if any(field in validated_data for field in critical_fields):
            schedule.detect_conflicts()
        
        # Log activity
        ActivityLog.objects.create(
            user=self.context['request'].user,
            institution=schedule.institution,
            action_type='schedule_update',
            action_description=f'Schedule updated: {schedule.title}',
            severity='low'
        )
        
        return schedule


class ScheduleOccurrenceSerializer(serializers.ModelSerializer):
    """
    Schedule occurrence serializer
    """
    schedule_info = ScheduleSerializer(source='parent_schedule', read_only=True)
    override_room_info = DepartmentResourceSerializer(source='override_room', read_only=True)
    override_lecturer_info = UserSerializer(source='override_lecturer', read_only=True)
    
    class Meta:
        model = ScheduleOccurrence
        fields = [
            'id', 'parent_schedule', 'schedule_info',
            'occurrence_date', 'start_time', 'end_time', 'status',
            'attendance_session', 'notes', 'cancellation_reason',
            'override_location', 'override_room', 'override_room_info',
            'override_lecturer', 'override_lecturer_info',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']

    def validate(self, attrs):
        """Validate occurrence data"""
        if attrs.get('start_time') and attrs.get('end_time'):
            if attrs['start_time'] >= attrs['end_time']:
                raise serializers.ValidationError("Start time must be before end time")
        
        return attrs


class ScheduleTemplateSerializer(serializers.ModelSerializer):
    """
    Schedule template serializer
    """
    departments_info = serializers.SerializerMethodField()
    
    class Meta:
        model = ScheduleTemplate
        fields = [
            'id', 'name', 'description', 'template_type',
            'template_data', 'default_settings',
            'usage_count', 'last_used',
            'is_public', 'departments', 'departments_info',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['usage_count', 'last_used', 'created_at', 'updated_at']

    def get_departments_info(self, obj):
        """Get department information"""
        return [{'id': dept.id, 'name': dept.name} for dept in obj.departments.all()]

    def create(self, validated_data):
        """Create schedule template"""
        template = super().create(validated_data)
        
        # Log activity
        ActivityLog.objects.create(
            user=self.context['request'].user,
            institution=template.institution,
            action_type='create',
            action_description=f'Schedule template created: {template.name}',
            severity='low'
        )
        
        return template


class ScheduleConflictSerializer(serializers.ModelSerializer):
    """
    Schedule conflict serializer
    """
    schedule_1_info = ScheduleSerializer(source='schedule_1', read_only=True)
    schedule_2_info = ScheduleSerializer(source='schedule_2', read_only=True)
    resolved_by_info = UserSerializer(source='resolved_by', read_only=True)
    
    class Meta:
        model = ScheduleConflict
        fields = [
            'id', 'conflict_type', 'severity', 'status',
            'schedule_1', 'schedule_1_info', 'schedule_2', 'schedule_2_info',
            'description', 'conflict_date', 'conflict_time_start', 'conflict_time_end',
            'resolution_notes', 'resolved_by', 'resolved_by_info', 'resolved_at',
            'suggested_solutions', 'auto_resolvable',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']

    def update(self, instance, validated_data):
        """Update conflict resolution"""
        conflict = super().update(instance, validated_data)
        
        if 'status' in validated_data and validated_data['status'] == 'resolved':
            # Log resolution
            ActivityLog.objects.create(
                user=self.context['request'].user,
                institution=conflict.institution,
                action_type='update',
                action_description=f'Schedule conflict resolved: {conflict.conflict_type}',
                severity='medium'
            )
        
        return conflict


class ScheduleAdjustmentSerializer(serializers.ModelSerializer):
    """
    Schedule adjustment serializer
    """
    schedule_info = ScheduleSerializer(source='schedule', read_only=True)
    approved_by_info = UserSerializer(source='approved_by', read_only=True)
    
    class Meta:
        model = ScheduleAdjustment
        fields = [
            'id', 'schedule', 'schedule_info', 'adjustment_type',
            'original_data', 'new_data', 'reason',
            'approved_by', 'approved_by_info', 'approval_notes',
            'affected_students', 'affected_lecturers', 'notification_sent',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['affected_students', 'affected_lecturers', 'notification_sent', 'created_at', 'updated_at']

    def create(self, validated_data):
        """Create schedule adjustment"""
        adjustment = super().create(validated_data)
        
        # Calculate affected users
        schedule = adjustment.schedule
        if schedule.course:
            adjustment.affected_students = schedule.course.enrollments.filter(status='enrolled').count()
        
        adjustment.affected_lecturers = 1 if schedule.lecturer else 0
        if schedule.assistant_lecturer:
            adjustment.affected_lecturers += 1
        
        adjustment.save()
        
        # Log activity
        ActivityLog.objects.create(
            user=self.context['request'].user,
            institution=adjustment.institution,
            action_type='update',
            action_description=f'Schedule adjustment created: {adjustment.adjustment_type}',
            severity='medium'
        )
        
        return adjustment


class SchedulePreferenceSerializer(serializers.ModelSerializer):
    """
    Schedule preference serializer
    """
    user_info = UserSerializer(source='user', read_only=True)
    preferred_rooms_info = DepartmentResourceSerializer(source='preferred_rooms', many=True, read_only=True)
    
    class Meta:
        model = SchedulePreference
        fields = [
            'id', 'user', 'user_info',
            'preferred_start_time', 'preferred_end_time', 'preferred_days',
            'preferred_rooms', 'preferred_rooms_info', 'preferred_locations',
            'max_consecutive_classes', 'min_break_between_classes', 'preferred_class_duration',
            'unavailable_times', 'preferred_workload',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']

    def validate(self, attrs):
        """Validate preference data"""
        if attrs.get('preferred_start_time') and attrs.get('preferred_end_time'):
            if attrs['preferred_start_time'] >= attrs['preferred_end_time']:
                raise serializers.ValidationError("Preferred start time must be before end time")
        
        if attrs.get('max_consecutive_classes', 0) < 1:
            raise serializers.ValidationError("Max consecutive classes must be at least 1")
        
        if attrs.get('min_break_between_classes', 0) < 0:
            raise serializers.ValidationError("Min break between classes cannot be negative")
        
        return attrs


class ScheduleAnalyticsSerializer(serializers.ModelSerializer):
    """
    Schedule analytics serializer
    """
    class Meta:
        model = ScheduleAnalytics
        fields = [
            'id', 'date',
            'total_schedules', 'active_schedules', 'cancelled_schedules',
            'total_rooms', 'occupied_rooms', 'room_utilization_percentage',
            'total_lecturer_hours', 'average_lecturer_workload', 'overloaded_lecturers',
            'total_conflicts', 'resolved_conflicts', 'conflict_resolution_rate',
            'total_student_hours', 'average_student_schedule_density',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']


class BulkScheduleSerializer(serializers.Serializer):
    """
    Bulk schedule operations serializer
    """
    schedules = ScheduleSerializer(many=True)
    template_id = serializers.UUIDField(required=False)
    start_date = serializers.DateField(required=False)
    end_date = serializers.DateField(required=False)
    
    def validate_schedules(self, value):
        """Validate bulk schedules"""
        if len(value) > 100:
            raise serializers.ValidationError("Cannot create more than 100 schedules at once")
        return value

    def create(self, validated_data):
        """Create bulk schedules"""
        schedules_data = validated_data.pop('schedules', [])
        template_id = validated_data.pop('template_id', None)
        
        created_schedules = []
        
        # Create from template if provided
        if template_id:
            try:
                template = ScheduleTemplate.objects.get(id=template_id)
                # Apply template to create schedules
                # Implementation depends on template structure
            except ScheduleTemplate.DoesNotExist:
                raise serializers.ValidationError("Invalid template ID")
        
        # Create individual schedules
        for schedule_data in schedules_data:
            serializer = ScheduleSerializer(data=schedule_data, context=self.context)
            serializer.is_valid(raise_exception=True)
            schedule = serializer.save()
            created_schedules.append(schedule)
        
        return {'created_schedules': created_schedules}


class ScheduleConflictResolutionSerializer(serializers.Serializer):
    """
    Schedule conflict resolution serializer
    """
    resolution_type = serializers.ChoiceField(choices=[
        ('keep_first', 'Keep First Schedule'),
        ('keep_second', 'Keep Second Schedule'),
        ('reschedule_first', 'Reschedule First Schedule'),
        ('reschedule_second', 'Reschedule Second Schedule'),
        ('split_time', 'Split Time Between Both'),
        ('cancel_both', 'Cancel Both Schedules'),
    ])
    new_start_time = serializers.TimeField(required=False)
    new_end_time = serializers.TimeField(required=False)
    new_date = serializers.DateField(required=False)
    new_room = serializers.UUIDField(required=False)
    resolution_notes = serializers.CharField(required=False, allow_blank=True)
    
    def validate(self, attrs):
        """Validate resolution data"""
        resolution_type = attrs.get('resolution_type')
        
        if resolution_type in ['reschedule_first', 'reschedule_second']:
            if not any([attrs.get('new_start_time'), attrs.get('new_date'), attrs.get('new_room')]):
                raise serializers.ValidationError("At least one new parameter is required for rescheduling")
        
        return attrs
