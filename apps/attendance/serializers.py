"""
Attendance serializers for Attendrix API
"""
from rest_framework import serializers
from django.utils import timezone
from apps.core.models import ActivityLog
from apps.attendance.models import (
    AttendanceSession, AttendanceRecord, AttendanceStatistics,
    AttendancePattern, AttendanceAlert, AttendanceSettings
)
from apps.users.serializers import UserSerializer
from apps.courses.serializers import CourseSerializer
from apps.scheduling.serializers import ScheduleOccurrenceSerializer


class AttendanceSessionSerializer(serializers.ModelSerializer):
    """
    Attendance session serializer
    """
    course_info = CourseSerializer(source='course', read_only=True)
    lecturer_info = UserSerializer(source='lecturer', read_only=True)
    schedule_occurrence_info = ScheduleOccurrenceSerializer(source='schedule_occurrence', read_only=True)
    
    # Computed fields
    is_expired = serializers.ReadOnlyField()
    attendance_rate = serializers.ReadOnlyField()
    current_time = serializers.SerializerMethodField()
    time_remaining = serializers.SerializerMethodField()
    
    class Meta:
        model = AttendanceSession
        fields = [
            'id', 'title', 'description', 'session_type',
            'course', 'course_info', 'schedule_occurrence', 'schedule_occurrence_info',
            'start_time', 'end_time', 'duration_minutes', 'grace_period_minutes',
            'session_code', 'is_active', 'auto_close', 'actual_end_time',
            'verification_methods', 'require_geolocation', 'geolocation_radius',
            'allowed_ip_ranges', 'require_device_fingerprint',
            'location_name', 'latitude', 'longitude',
            'max_attempts', 'attempt_timeout_minutes', 'duplicate_check_window_minutes',
            'lecturer', 'lecturer_info',
            'total_enrolled', 'total_present', 'total_absent', 'total_late', 'total_excused',
            'is_expired', 'attendance_rate', 'current_time', 'time_remaining',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'session_code', 'total_enrolled', 'total_present', 'total_absent', 
            'total_late', 'total_excused', 'is_expired', 'attendance_rate',
            'created_at', 'updated_at'
        ]

    def get_current_time(self, obj):
        """Get current server time"""
        return timezone.now().isoformat()

    def get_time_remaining(self, obj):
        """Get time remaining until session ends"""
        if obj.is_expired:
            return 0
        
        remaining = obj.end_time - timezone.now()
        return max(0, int(remaining.total_seconds()))

    def validate(self, attrs):
        """Validate session data"""
        start_time = attrs.get('start_time')
        end_time = attrs.get('end_time')
        
        if start_time and end_time:
            if start_time >= end_time:
                raise serializers.ValidationError("Start time must be before end time")
            
            # Check duration
            duration = (end_time - start_time).total_seconds() / 60
            if duration < 15:
                raise serializers.ValidationError("Session duration must be at least 15 minutes")
            if duration > 480:  # 8 hours max
                raise serializers.ValidationError("Session duration cannot exceed 8 hours")
        
        # Validate geolocation settings
        if attrs.get('require_geolocation') and not attrs.get('latitude'):
            raise serializers.ValidationError("Latitude is required when geolocation verification is enabled")
        
        return attrs

    def create(self, validated_data):
        """Create attendance session"""
        session = super().create(validated_data)
        
        # Log activity
        ActivityLog.objects.create(
            user=self.context['request'].user,
            institution=session.institution,
            action_type='create',
            action_description=f'Attendance session created: {session.title}',
            severity='low'
        )
        
        return session

    def update(self, instance, validated_data):
        """Update attendance session"""
        old_active = instance.is_active
        session = super().update(instance, validated_data)
        
        # Log activation/deactivation
        if old_active != session.is_active:
            action = 'activated' if session.is_active else 'deactivated'
            ActivityLog.objects.create(
                user=self.context['request'].user,
                institution=session.institution,
                action_type='update',
                action_description=f'Attendance session {action}: {session.title}',
                severity='medium'
            )
        
        return session


class AttendanceRecordSerializer(serializers.ModelSerializer):
    """
    Attendance record serializer
    """
    session_info = AttendanceSessionSerializer(source='session', read_only=True)
    student_info = UserSerializer(source='student', read_only=True)
    approved_by_info = UserSerializer(source='approved_by', read_only=True)
    
    class Meta:
        model = AttendanceRecord
        fields = [
            'id', 'session', 'session_info', 'student', 'student_info',
            'status', 'marking_method', 'marked_at',
            'check_in_time', 'check_out_time', 'minutes_late',
            'latitude', 'longitude', 'location_accuracy', 'location_verified',
            'ip_address', 'user_agent', 'device_fingerprint', 'device_trusted',
            'verification_score', 'is_suspicious', 'security_flags',
            'notes', 'excuse_reason', 'excuse_document', 'approved_by', 'approved_by_info',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'verification_score', 'is_suspicious', 'security_flags',
            'created_at', 'updated_at'
        ]

    def validate(self, attrs):
        """Validate attendance record"""
        session = self.instance.session if self.instance else attrs.get('session')
        student = attrs.get('student')
        
        # Check if session is active
        if session and not session.is_active:
            raise serializers.ValidationError("Session is not active")
        
        # Check if session has expired
        if session and session.is_expired:
            raise serializers.ValidationError("Session has expired")
        
        # Check for duplicate attendance
        if AttendanceRecord.objects.filter(
            session=session,
            student=student,
            is_deleted=False
        ).exists():
            raise serializers.ValidationError("Attendance already marked for this session")
        
        # Validate geolocation if required
        if session and session.require_geolocation:
            latitude = attrs.get('latitude')
            longitude = attrs.get('longitude')
            
            if not latitude or not longitude:
                raise serializers.ValidationError("Location coordinates are required")
            
            # Verify location
            if not session.verify_location(latitude, longitude):
                raise serializers.ValidationError("Location is outside allowed radius")
        
        return attrs

    def create(self, validated_data):
        """Create attendance record with security checks"""
        request = self.context['request']
        session = validated_data['session']
        student = validated_data['student']
        
        # Add request metadata
        validated_data['ip_address'] = self._get_client_ip(request)
        validated_data['user_agent'] = request.META.get('HTTP_USER_AGENT', '')
        validated_data['device_fingerprint'] = self._generate_device_fingerprint(request)
        
        # Check device trust
        validated_data['device_trusted'] = self._is_device_trusted(student, validated_data['device_fingerprint'])
        
        # Create record
        record = super().create(validated_data)
        
        # Update session statistics
        self._update_session_statistics(session)
        
        # Log activity
        ActivityLog.objects.create(
            user=student,
            institution=record.institution,
            action_type='attendance_mark',
            action_description=f'Attendance marked for {session.title}',
            ip_address=validated_data['ip_address'],
            user_agent=validated_data['user_agent'],
            device_fingerprint=validated_data['device_fingerprint'],
            severity='low'
        )
        
        # Check for suspicious activity
        if record.is_suspicious:
            self._handle_suspicious_attendance(record)
        
        return record

    def _get_client_ip(self, request):
        """Get client IP address"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0]
        return request.META.get('REMOTE_ADDR')

    def _generate_device_fingerprint(self, request):
        """Generate device fingerprint"""
        import hashlib
        import json
        
        fingerprint_data = {
            'user_agent': request.META.get('HTTP_USER_AGENT', ''),
            'accept_language': request.META.get('HTTP_ACCEPT_LANGUAGE', ''),
            'accept_encoding': request.META.get('HTTP_ACCEPT_ENCODING', ''),
        }
        
        fingerprint_string = json.dumps(fingerprint_data, sort_keys=True)
        return hashlib.sha256(fingerprint_string.encode()).hexdigest()[:32]

    def _is_device_trusted(self, student, fingerprint):
        """Check if device is trusted"""
        if not fingerprint:
            return False
        
        trusted_records = AttendanceRecord.objects.filter(
            student=student,
            device_fingerprint=fingerprint,
            device_trusted=True,
            verification_score__gte=80
        ).count()
        
        return trusted_records > 0

    def _update_session_statistics(self, session):
        """Update session statistics"""
        stats = session.attendance_records.filter(is_deleted=False).aggregate(
            total=models.Count('id'),
            present=models.Count('id', filter=models.Q(status='present')),
            absent=models.Count('id', filter=models.Q(status='absent')),
            late=models.Count('id', filter=models.Q(status='late')),
            excused=models.Count('id', filter=models.Q(status='excused'))
        )
        
        session.total_present = stats['present'] or 0
        session.total_absent = stats['absent'] or 0
        session.total_late = stats['late'] or 0
        session.total_excused = stats['excused'] or 0
        session.save()

    def _handle_suspicious_attendance(self, record):
        """Handle suspicious attendance"""
        # Create alert
        AttendanceAlert.objects.create(
            institution=record.institution,
            alert_type='suspicious_activity',
            severity='warning',
            title=f'Suspicious Attendance Detected',
            description=f'Suspicious attendance pattern detected for {record.student.get_full_name()} in {record.session.title}',
            student=record.student,
            course=record.session.course,
            alert_data={
                'record_id': record.id,
                'verification_score': record.verification_score,
                'security_flags': record.security_flags
            }
        )


class AttendanceMarkingSerializer(serializers.Serializer):
    """
    Attendance marking serializer for API endpoints
    """
    session_code = serializers.CharField(max_length=10)
    marking_method = serializers.ChoiceField(choices=AttendanceRecord.MARKING_METHODS)
    
    # Optional location data
    latitude = serializers.FloatField(required=False)
    longitude = serializers.FloatField(required=False)
    location_accuracy = serializers.FloatField(required=False)
    
    # Optional notes
    notes = serializers.CharField(required=False, allow_blank=True, max_length=500)
    
    def validate_session_code(self, value):
        """Validate session code"""
        try:
            session = AttendanceSession.objects.get(
                session_code=value.upper(),
                is_active=True
            )
            
            if session.is_expired:
                raise serializers.ValidationError("Session has expired")
            
            self.validated_session = session
            return value
            
        except AttendanceSession.DoesNotExist:
            raise serializers.ValidationError("Invalid session code")

    def validate(self, attrs):
        """Validate attendance marking data"""
        session = self.validated_session
        
        # Check if user can mark attendance
        user = self.context['request'].user
        can_mark, message = session.can_mark_attendance(user)
        
        if not can_mark:
            raise serializers.ValidationError(message)
        
        # Validate location if required
        if session.require_geolocation:
            if not attrs.get('latitude') or not attrs.get('longitude'):
                raise serializers.ValidationError("Location coordinates are required")
        
        return attrs


class AttendanceStatisticsSerializer(serializers.ModelSerializer):
    """
    Attendance statistics serializer
    """
    class Meta:
        model = AttendanceStatistics
        fields = [
            'id', 'statistics_type', 'reference_id', 'reference_date',
            'total_sessions', 'total_attendance_records',
            'present_count', 'absent_count', 'late_count', 'excused_count',
            'attendance_rate', 'punctuality_rate', 'engagement_score',
            'dropout_risk_score', 'performance_risk_score',
            'attendance_trend', 'trend_direction',
            'metadata', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']


class AttendancePatternSerializer(serializers.ModelSerializer):
    """
    Attendance pattern serializer
    """
    student_info = UserSerializer(source='student', read_only=True)
    course_info = CourseSerializer(source='course', read_only=True)
    
    class Meta:
        model = AttendancePattern
        fields = [
            'id', 'student', 'student_info', 'course', 'course_info',
            'pattern_type', 'confidence_score', 'risk_level',
            'average_attendance_rate', 'attendance_variance', 'consistency_score',
            'anomaly_count', 'last_anomaly_date',
            'preferred_seating_position', 'typical_arrival_time', 'device_consistency',
            'analysis_start_date', 'analysis_end_date', 'total_sessions_analyzed',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']


class AttendanceAlertSerializer(serializers.ModelSerializer):
    """
    Attendance alert serializer
    """
    student_info = UserSerializer(source='student', read_only=True)
    course_info = CourseSerializer(source='course', read_only=True)
    acknowledged_by_info = UserSerializer(source='acknowledged_by', read_only=True)
    resolved_by_info = UserSerializer(source='resolved_by', read_only=True)
    
    class Meta:
        model = AttendanceAlert
        fields = [
            'id', 'alert_type', 'severity', 'title', 'description',
            'student', 'student_info', 'course', 'course_info',
            'alert_data', 'threshold_value', 'actual_value',
            'is_active', 'acknowledged', 'acknowledged_by', 'acknowledged_by_info', 'acknowledged_at',
            'resolved', 'resolved_by', 'resolved_by_info', 'resolved_at', 'resolution_notes',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']


class AttendanceSettingsSerializer(serializers.ModelSerializer):
    """
    Attendance settings serializer
    """
    class Meta:
        model = AttendanceSettings
        fields = [
            'id', 'institution',
            'default_session_duration', 'default_grace_period', 'default_geolocation_radius',
            'enable_geolocation_verification', 'enable_device_fingerprinting',
            'enable_ip_verification', 'enable_biometric_verification',
            'low_attendance_threshold', 'chronic_absenteeism_threshold',
            'suspicious_activity_threshold',
            'auto_close_sessions', 'auto_generate_reports', 'auto_send_alerts',
            'notify_lecturers_absenteeism', 'notify_students_low_attendance',
            'notify_admins_suspicious_activity',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']


class BulkAttendanceSerializer(serializers.Serializer):
    """
    Bulk attendance operations serializer
    """
    session_code = serializers.CharField(max_length=10)
    student_ids = serializers.ListField(child=serializers.UUIDField())
    status = serializers.ChoiceField(choices=AttendanceRecord.ATTENDANCE_STATUSES)
    marking_method = serializers.ChoiceField(choices=AttendanceRecord.MARKING_METHODS)
    notes = serializers.CharField(required=False, allow_blank=True, max_length=500)
    
    def validate_session_code(self, value):
        """Validate session code"""
        try:
            session = AttendanceSession.objects.get(
                session_code=value.upper(),
                is_active=True
            )
            
            if session.is_expired:
                raise serializers.ValidationError("Session has expired")
            
            self.validated_session = session
            return value
            
        except AttendanceSession.DoesNotExist:
            raise serializers.ValidationError("Invalid session code")

    def validate(self, attrs):
        """Validate bulk attendance data"""
        if len(attrs['student_ids']) > 100:
            raise serializers.ValidationError("Cannot process more than 100 students at once")
        
        # Validate students are enrolled in course
        session = self.validated_session
        from apps.courses.models import CourseEnrollment
        
        invalid_students = []
        for student_id in attrs['student_ids']:
            if not CourseEnrollment.objects.filter(
                student_id=student_id,
                course=session.course,
                status='enrolled'
            ).exists():
                invalid_students.append(str(student_id))
        
        if invalid_students:
            raise serializers.ValidationError(f"Students not enrolled: {', '.join(invalid_students)}")
        
        return attrs


class AttendanceReportSerializer(serializers.Serializer):
    """
    Attendance report serializer
    """
    report_type = serializers.ChoiceField(choices=[
        ('student_summary', 'Student Summary'),
        ('course_summary', 'Course Summary'),
        ('session_details', 'Session Details'),
        ('attendance_trends', 'Attendance Trends'),
        ('suspicious_activity', 'Suspicious Activity'),
    ])
    start_date = serializers.DateField()
    end_date = serializers.DateField()
    course_id = serializers.UUIDField(required=False)
    student_id = serializers.UUIDField(required=False)
    
    def validate(self, attrs):
        """Validate report parameters"""
        start_date = attrs['start_date']
        end_date = attrs['end_date']
        
        if start_date > end_date:
            raise serializers.ValidationError("Start date cannot be after end date")
        
        # Check date range is not too large
        if (end_date - start_date).days > 365:
            raise serializers.ValidationError("Report date range cannot exceed 1 year")
        
        return attrs
