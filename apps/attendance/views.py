"""
Attendance views for Attendrix - Advanced attendance engine
"""
from rest_framework import status, generics, viewsets
from rest_framework.decorators import api_view, permission_classes, action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from django.utils import timezone
from django.db.models import Q, Count, Avg, Sum, F
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from django.core.paginator import Paginator
from apps.core.models import ActivityLog, SecurityLog
from apps.core.permissions import IsInstitutionAdmin, IsLecturer
from apps.attendance.models import (
    AttendanceSession, AttendanceRecord, AttendanceStatistics,
    AttendancePattern, AttendanceAlert, AttendanceSettings
)
from apps.attendance.serializers import (
    AttendanceSessionSerializer, AttendanceRecordSerializer, AttendanceStatisticsSerializer,
    AttendancePatternSerializer, AttendanceAlertSerializer, AttendanceSettingsSerializer,
    AttendanceMarkingSerializer, BulkAttendanceSerializer, AttendanceReportSerializer
)
from apps.attendance.tasks import (
    generate_attendance_analytics, detect_attendance_anomalies,
    send_attendance_reminders, cleanup_old_attendance_records
)
import datetime
import json


class AttendanceSessionViewSet(viewsets.ModelViewSet):
    """
    Attendance session viewset with full CRUD operations
    """
    serializer_class = AttendanceSessionSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['session_type', 'course', 'lecturer', 'is_active']
    search_fields = ['title', 'description', 'session_code']
    ordering_fields = ['start_time', 'created_at']
    ordering = ['-start_time']

    def get_queryset(self):
        """Filter sessions by institution and user role"""
        user = self.request.user
        queryset = AttendanceSession.objects.filter(
            institution=user.institution,
            is_deleted=False
        )
        
        # Filter based on user role
        if user.is_student():
            # Students can only see sessions for their enrolled courses
            queryset = queryset.filter(
                course__enrollments__student=user,
                course__enrollments__status='enrolled'
            )
        elif user.is_lecturer():
            # Lecturers can see their own sessions
            queryset = queryset.filter(lecturer=user)
        elif user.is_institution_admin():
            # Institution admins can see all sessions
            pass
        elif user.is_super_admin():
            # Super admins can see all sessions
            pass
        
        return queryset.distinct()

    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        """Activate attendance session"""
        session = self.get_object()
        
        if session.is_active:
            return Response({
                'error': 'Session is already active'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if session.is_expired:
            return Response({
                'error': 'Cannot activate expired session'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        session.is_active = True
        session.save()
        
        # Log activity
        ActivityLog.objects.create(
            user=request.user,
            institution=session.institution,
            action_type='update',
            action_description=f'Attendance session activated: {session.title}',
            severity='medium'
        )
        
        return Response({'message': 'Session activated successfully'})

    @action(detail=True, methods=['post'])
    def deactivate(self, request, pk=None):
        """Deactivate attendance session"""
        session = self.get_object()
        
        if not session.is_active:
            return Response({
                'error': 'Session is not active'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        session.is_active = False
        session.actual_end_time = timezone.now()
        session.save()
        
        # Generate analytics for the session
        generate_attendance_analytics.delay(session.id)
        
        # Log activity
        ActivityLog.objects.create(
            user=request.user,
            institution=session.institution,
            action_type='update',
            action_description=f'Attendance session deactivated: {session.title}',
            severity='medium'
        )
        
        return Response({'message': 'Session deactivated successfully'})

    @action(detail=True, methods=['get'])
    def attendance_records(self, request, pk=None):
        """Get attendance records for this session"""
        session = self.get_object()
        records = session.attendance_records.filter(is_deleted=False)
        
        # Filter by status if specified
        status_filter = request.query_params.get('status')
        if status_filter:
            records = records.filter(status=status_filter)
        
        # Filter by suspicious records
        suspicious_only = request.query_params.get('suspicious_only', 'false').lower() == 'true'
        if suspicious_only:
            records = records.filter(is_suspicious=True)
        
        page = self.paginate_queryset(records)
        serializer = AttendanceRecordSerializer(page, many=True, context={'request': request})
        return self.get_paginated_response(serializer.data)

    @action(detail=True, methods=['post'])
    def bulk_mark_attendance(self, request, pk=None):
        """Bulk mark attendance for multiple students"""
        session = self.get_object()
        serializer = BulkAttendanceSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        
        validated_data = serializer.validated_data
        student_ids = validated_data['student_ids']
        status = validated_data['status']
        marking_method = validated_data['marking_method']
        notes = validated_data.get('notes', '')
        
        created_records = []
        errors = []
        
        for student_id in student_ids:
            try:
                # Check if record already exists
                if AttendanceRecord.objects.filter(
                    session=session,
                    student_id=student_id,
                    is_deleted=False
                ).exists():
                    errors.append(f'Student {student_id} already has attendance record')
                    continue
                
                # Create attendance record
                record = AttendanceRecord.objects.create(
                    institution=session.institution,
                    session=session,
                    student_id=student_id,
                    status=status,
                    marking_method=marking_method,
                    check_in_time=timezone.now(),
                    notes=notes,
                    ip_address=request.META.get('REMOTE_ADDR'),
                    user_agent=request.META.get('HTTP_USER_AGENT', ''),
                    created_by=request.user
                )
                
                created_records.append(record.id)
                
            except Exception as e:
                errors.append(f'Error for student {student_id}: {str(e)}')
        
        # Update session statistics
        self._update_session_statistics(session)
        
        return Response({
            'message': f'Created {len(created_records)} attendance records',
            'created_records': created_records,
            'errors': errors
        })

    @action(detail=True, methods=['get'])
    def analytics(self, request, pk=None):
        """Get session analytics"""
        session = self.get_object()
        
        records = session.attendance_records.filter(is_deleted=False)
        
        stats = records.aggregate(
            total=Count('id'),
            present=Count('id', filter=Q(status='present')),
            absent=Count('id', filter=Q(status='absent')),
            late=Count('id', filter=Q(status='late')),
            excused=Count('id', filter=Q(status='excused')),
            suspicious=Count('id', filter=Q(is_suspicious=True)),
            avg_verification_score=Avg('verification_score')
        )
        
        # Calculate rates
        total_records = stats['total'] or 0
        attendance_rate = ((stats['present'] or 0) / total_records * 100) if total_records > 0 else 0
        punctuality_rate = (((stats['present'] or 0) - (stats['late'] or 0)) / total_records * 100) if total_records > 0 else 0
        
        # Method breakdown
        method_stats = records.values('marking_method').annotate(
            count=Count('id')
        ).order_by('-count')
        
        return Response({
            'session_info': {
                'title': session.title,
                'session_code': session.session_code,
                'start_time': session.start_time,
                'end_time': session.end_time,
                'total_enrolled': session.total_enrolled
            },
            'attendance_stats': {
                'total_records': total_records,
                'present': stats['present'] or 0,
                'absent': stats['absent'] or 0,
                'late': stats['late'] or 0,
                'excused': stats['excused'] or 0,
                'suspicious': stats['suspicious'] or 0,
                'attendance_rate': round(attendance_rate, 2),
                'punctuality_rate': round(punctuality_rate, 2),
                'avg_verification_score': round(stats['avg_verification_score'] or 0, 2)
            },
            'method_breakdown': list(method_stats)
        })

    def _update_session_statistics(self, session):
        """Update session statistics"""
        stats = session.attendance_records.filter(is_deleted=False).aggregate(
            present=Count('id', filter=Q(status='present')),
            absent=Count('id', filter=Q(status='absent')),
            late=Count('id', filter=Q(status='late')),
            excused=Count('id', filter=Q(status='excused'))
        )
        
        session.total_present = stats['present'] or 0
        session.total_absent = stats['absent'] or 0
        session.total_late = stats['late'] or 0
        session.total_excused = stats['excused'] or 0
        session.save()


class AttendanceRecordViewSet(viewsets.ModelViewSet):
    """
    Attendance record viewset
    """
    serializer_class = AttendanceRecordSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['status', 'marking_method', 'session']
    search_fields = ['notes', 'excuse_reason']
    ordering_fields = ['marked_at', 'check_in_time']
    ordering = ['-marked_at']

    def get_queryset(self):
        """Filter records by institution and user role"""
        user = self.request.user
        queryset = AttendanceRecord.objects.filter(
            institution=user.institution,
            is_deleted=False
        )
        
        # Filter based on user role
        if user.is_student():
            # Students can only see their own records
            queryset = queryset.filter(student=user)
        elif user.is_lecturer():
            # Lecturers can see records for their courses
            queryset = queryset.filter(session__course__lecturer=user)
        elif user.is_institution_admin():
            # Institution admins can see all records
            pass
        
        return queryset.distinct()

    @action(detail=True, methods=['post'])
    def approve_excuse(self, request, pk=None):
        """Approve attendance excuse"""
        record = self.get_object()
        
        if record.status not in ['absent', 'late']:
            return Response({
                'error': 'Can only approve excuses for absent or late records'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        record.status = 'excused'
        record.approved_by = request.user
        record.save()
        
        # Update session statistics
        self._update_session_statistics(record.session)
        
        # Log activity
        ActivityLog.objects.create(
            user=request.user,
            institution=record.institution,
            action_type='update',
            action_description=f'Attendance excuse approved for {record.student.get_full_name()}',
            severity='low'
        )
        
        return Response({'message': 'Excuse approved successfully'})

    @action(detail=True, methods=['post'])
    def mark_suspicious(self, request, pk=None):
        """Mark attendance record as suspicious"""
        record = self.get_object()
        reason = request.data.get('reason', '')
        
        record.is_suspicious = True
        if reason:
            record.security_flags = record.security_flags + ['manual_flag']
            record.notes = f"{record.notes}\n[SUSPICIOUS]: {reason}".strip()
        
        record.save()
        
        # Create alert
        AttendanceAlert.objects.create(
            institution=record.institution,
            alert_type='suspicious_activity',
            severity='warning',
            title='Manually Flagged Suspicious Attendance',
            description=f'Attendance manually flagged as suspicious: {reason}',
            student=record.student,
            course=record.session.course,
            alert_data={
                'record_id': record.id,
                'flagged_by': request.user.get_full_name(),
                'reason': reason
            }
        )
        
        return Response({'message': 'Record marked as suspicious'})

    def _update_session_statistics(self, session):
        """Update session statistics"""
        stats = session.attendance_records.filter(is_deleted=False).aggregate(
            present=Count('id', filter=Q(status='present')),
            absent=Count('id', filter=Q(status='absent')),
            late=Count('id', filter=Q(status='late')),
            excused=Count('id', filter=Q(status='excused'))
        )
        
        session.total_present = stats['present'] or 0
        session.total_absent = stats['absent'] or 0
        session.total_late = stats['late'] or 0
        session.total_excused = stats['excused'] or 0
        session.save()


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mark_attendance(request):
    """
    Mark attendance for a session
    """
    serializer = AttendanceMarkingSerializer(data=request.data, context={'request': request})
    serializer.is_valid(raise_exception=True)
    
    session = serializer.validated_session
    student = request.user
    
    # Check if already marked
    if AttendanceRecord.objects.filter(
        session=session,
        student=student,
        is_deleted=False
    ).exists():
        return Response({
            'error': 'Attendance already marked for this session'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Create attendance record
    record = AttendanceRecord.objects.create(
        institution=session.institution,
        session=session,
        student=student,
        status='present',
        marking_method=serializer.validated_data['marking_method'],
        check_in_time=timezone.now(),
        latitude=serializer.validated_data.get('latitude'),
        longitude=serializer.validated_data.get('longitude'),
        location_accuracy=serializer.validated_data.get('location_accuracy'),
        notes=serializer.validated_data.get('notes', ''),
        ip_address=request.META.get('REMOTE_ADDR'),
        user_agent=request.META.get('HTTP_USER_AGENT', ''),
        device_fingerprint=serializer._generate_device_fingerprint(request),
        created_by=student
    )
    
    # Update session statistics
    session.total_present += 1
    session.save()
    
    # Log activity
    ActivityLog.objects.create(
        user=student,
        institution=record.institution,
        action_type='attendance_mark',
        action_description=f'Attendance marked for {session.title}',
        ip_address=record.ip_address,
        user_agent=record.user_agent,
        device_fingerprint=record.device_fingerprint,
        severity='low'
    )
    
    # Check for suspicious activity
    if record.is_suspicious:
        # Create alert
        AttendanceAlert.objects.create(
            institution=record.institution,
            alert_type='suspicious_activity',
            severity='warning',
            title='Suspicious Attendance Detected',
            description=f'Suspicious attendance pattern detected for {student.get_full_name()}',
            student=student,
            course=session.course,
            alert_data={
                'record_id': record.id,
                'verification_score': record.verification_score,
                'security_flags': record.security_flags
            }
        )
    
    return Response({
        'message': 'Attendance marked successfully',
        'record_id': record.id,
        'verification_score': record.verification_score,
        'is_suspicious': record.is_suspicious
    })


class AttendanceStatisticsViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Attendance statistics viewset
    """
    serializer_class = AttendanceStatisticsSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['statistics_type']
    ordering_fields = ['reference_date', 'attendance_rate']
    ordering = ['-reference_date']

    def get_queryset(self):
        """Filter statistics by institution"""
        user = self.request.user
        return AttendanceStatistics.objects.filter(institution=user.institution)

    @action(detail=False, methods=['get'])
    def dashboard(self, request):
        """Get dashboard statistics"""
        user = request.user
        institution = user.institution
        
        # Get date range
        end_date = timezone.now().date()
        start_date = end_date - datetime.timedelta(days=30)
        
        # Overall statistics
        overall_stats = AttendanceStatistics.objects.filter(
            institution=institution,
            reference_date__gte=start_date,
            reference_date__lte=end_date
        ).aggregate(
            avg_attendance_rate=Avg('attendance_rate'),
            total_sessions=Sum('total_sessions'),
            total_records=Sum('total_attendance_records')
        )
        
        # Recent alerts
        recent_alerts = AttendanceAlert.objects.filter(
            institution=institution,
            is_active=True,
            created_at__gte=timezone.now() - datetime.timedelta(days=7)
        ).count()
        
        # My statistics (if student)
        my_stats = {}
        if user.is_student():
            my_records = AttendanceRecord.objects.filter(
                student=user,
                is_deleted=False,
                marked_at__gte=start_date
            ).aggregate(
                total=Count('id'),
                present=Count('id', filter=Q(status='present')),
                late=Count('id', filter=Q(status='late')),
                absent=Count('id', filter=Q(status='absent'))
            )
            
            total = my_records['total'] or 0
            my_stats = {
                'total_sessions': total,
                'present': my_records['present'] or 0,
                'late': my_records['late'] or 0,
                'absent': my_records['absent'] or 0,
                'attendance_rate': ((my_records['present'] or 0) / total * 100) if total > 0 else 0
            }
        
        # Active sessions
        active_sessions = AttendanceSession.objects.filter(
            institution=institution,
            is_active=True
        ).count()
        
        return Response({
            'period': {
                'start_date': start_date,
                'end_date': end_date
            },
            'overall_statistics': {
                'average_attendance_rate': round(overall_stats['avg_attendance_rate'] or 0, 2),
                'total_sessions': overall_stats['total_sessions'] or 0,
                'total_records': overall_stats['total_records'] or 0
            },
            'active_alerts': recent_alerts,
            'active_sessions': active_sessions,
            'my_statistics': my_stats
        })


class AttendanceAlertViewSet(viewsets.ModelViewSet):
    """
    Attendance alert viewset
    """
    serializer_class = AttendanceAlertSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['alert_type', 'severity', 'student', 'acknowledged', 'resolved']
    search_fields = ['title', 'description']
    ordering_fields = ['created_at', 'severity']
    ordering = ['-created_at']

    def get_queryset(self):
        """Filter alerts by institution and user role"""
        user = self.request.user
        queryset = AttendanceAlert.objects.filter(
            institution=user.institution,
            is_active=True
        )
        
        # Filter based on user role
        if user.is_student():
            # Students can only see alerts about themselves
            queryset = queryset.filter(student=user)
        elif user.is_lecturer():
            # Lecturers can see alerts for their courses
            queryset = queryset.filter(course__lecturer=user)
        
        return queryset.distinct()

    @action(detail=True, methods=['post'])
    def acknowledge(self, request, pk=None):
        """Acknowledge alert"""
        alert = self.get_object()
        
        if alert.acknowledged:
            return Response({
                'error': 'Alert already acknowledged'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        alert.acknowledged = True
        alert.acknowledged_by = request.user
        alert.acknowledged_at = timezone.now()
        alert.save()
        
        return Response({'message': 'Alert acknowledged successfully'})

    @action(detail=True, methods=['post'])
    def resolve(self, request, pk=None):
        """Resolve alert"""
        alert = self.get_object()
        resolution_notes = request.data.get('resolution_notes', '')
        
        alert.resolved = True
        alert.resolved_by = request.user
        alert.resolved_at = timezone.now()
        alert.resolution_notes = resolution_notes
        alert.save()
        
        return Response({'message': 'Alert resolved successfully'})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def my_attendance(request):
    """
    Get current user's attendance records
    """
    user = request.user
    
    # Get date range
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    
    if not start_date:
        start_date = timezone.now().date() - datetime.timedelta(days=30)
    else:
        start_date = datetime.datetime.strptime(start_date, '%Y-%m-%d').date()
    
    if not end_date:
        end_date = timezone.now().date()
    else:
        end_date = datetime.datetime.strptime(end_date, '%Y-%m-%d').date()
    
    records = AttendanceRecord.objects.filter(
        student=user,
        marked_at__date__gte=start_date,
        marked_at__date__lte=end_date,
        is_deleted=False
    ).select_related('session', 'session__course').order_by('-marked_at')
    
    # Serialize records
    serializer = AttendanceRecordSerializer(records, many=True, context={'request': request})
    
    # Calculate statistics
    stats = records.aggregate(
        total=Count('id'),
        present=Count('id', filter=Q(status='present')),
        late=Count('id', filter=Q(status='late')),
        absent=Count('id', filter=Q(status='absent')),
        excused=Count('id', filter=Q(status='excused'))
    )
    
    total = stats['total'] or 0
    attendance_rate = ((stats['present'] or 0) / total * 100) if total > 0 else 0
    
    return Response({
        'period': {
            'start_date': start_date,
            'end_date': end_date
        },
        'statistics': {
            'total_sessions': total,
            'present': stats['present'] or 0,
            'late': stats['late'] or 0,
            'absent': stats['absent'] or 0,
            'excused': stats['excused'] or 0,
            'attendance_rate': round(attendance_rate, 2)
        },
        'records': serializer.data
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def generate_attendance_report(request):
    """
    Generate attendance report
    """
    serializer = AttendanceReportSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    
    report_type = serializer.validated_data['report_type']
    start_date = serializer.validated_data['start_date']
    end_date = serializer.validated_data['end_date']
    course_id = serializer.validated_data.get('course_id')
    student_id = serializer.validated_data.get('student_id')
    
    user = request.user
    institution = user.institution
    
    # Generate report based on type
    if report_type == 'student_summary':
        if not student_id:
            return Response({
                'error': 'Student ID is required for student summary'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Generate student summary report
        records = AttendanceRecord.objects.filter(
            student_id=student_id,
            marked_at__date__gte=start_date,
            marked_at__date__lte=end_date,
            is_deleted=False
        ).select_related('session', 'session__course')
        
        # Calculate statistics
        stats = records.aggregate(
            total=Count('id'),
            present=Count('id', filter=Q(status='present')),
            late=Count('id', filter=Q(status='late')),
            absent=Count('id', filter=Q(status='absent')),
            excused=Count('id', filter=Q(status='excused'))
        )
        
        total = stats['total'] or 0
        attendance_rate = ((stats['present'] or 0) / total * 100) if total > 0 else 0
        
        report_data = {
            'report_type': report_type,
            'period': {'start_date': start_date, 'end_date': end_date},
            'student_id': student_id,
            'statistics': {
                'total_sessions': total,
                'present': stats['present'] or 0,
                'late': stats['late'] or 0,
                'absent': stats['absent'] or 0,
                'excused': stats['excused'] or 0,
                'attendance_rate': round(attendance_rate, 2)
            },
            'records': AttendanceRecordSerializer(records, many=True, context={'request': request}).data
        }
    
    elif report_type == 'course_summary':
        if not course_id:
            return Response({
                'error': 'Course ID is required for course summary'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Generate course summary report
        records = AttendanceRecord.objects.filter(
            session__course_id=course_id,
            marked_at__date__gte=start_date,
            marked_at__date__lte=end_date,
            is_deleted=False
        ).select_related('student', 'session')
        
        # Calculate statistics
        stats = records.aggregate(
            total=Count('id'),
            present=Count('id', filter=Q(status='present')),
            late=Count('id', filter=Q(status='late')),
            absent=Count('id', filter=Q(status='absent')),
            excused=Count('id', filter=Q(status='excused'))
        )
        
        total = stats['total'] or 0
        attendance_rate = ((stats['present'] or 0) / total * 100) if total > 0 else 0
        
        # Student breakdown
        student_stats = records.values('student__id', 'student__first_name', 'student__last_name').annotate(
            total=Count('id'),
            present=Count('id', filter=Q(status='present')),
            late=Count('id', filter=Q(status='late')),
            absent=Count('id', filter=Q(status='absent')),
            excused=Count('id', filter=Q(status='excused'))
        ).order_by('-present')
        
        report_data = {
            'report_type': report_type,
            'period': {'start_date': start_date, 'end_date': end_date},
            'course_id': course_id,
            'statistics': {
                'total_sessions': total,
                'present': stats['present'] or 0,
                'late': stats['late'] or 0,
                'absent': stats['absent'] or 0,
                'excused': stats['excused'] or 0,
                'attendance_rate': round(attendance_rate, 2)
            },
            'student_breakdown': list(student_stats)
        }
    
    else:
        # Generate general report
        records = AttendanceRecord.objects.filter(
            institution=institution,
            marked_at__date__gte=start_date,
            marked_at__date__lte=end_date,
            is_deleted=False
        )
        
        if course_id:
            records = records.filter(session__course_id=course_id)
        
        if student_id:
            records = records.filter(student_id=student_id)
        
        stats = records.aggregate(
            total=Count('id'),
            present=Count('id', filter=Q(status='present')),
            late=Count('id', filter=Q(status='late')),
            absent=Count('id', filter=Q(status='absent')),
            excused=Count('id', filter=Q(status='excused'))
        )
        
        total = stats['total'] or 0
        attendance_rate = ((stats['present'] or 0) / total * 100) if total > 0 else 0
        
        report_data = {
            'report_type': report_type,
            'period': {'start_date': start_date, 'end_date': end_date},
            'statistics': {
                'total_sessions': total,
                'present': stats['present'] or 0,
                'late': stats['late'] or 0,
                'absent': stats['absent'] or 0,
                'excused': stats['excused'] or 0,
                'attendance_rate': round(attendance_rate, 2)
            }
        }
    
    return Response(report_data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def attendance_analytics(request):
    """
    Get comprehensive attendance analytics
    """
    user = request.user
    institution = user.institution
    
    # Get date range
    end_date = timezone.now().date()
    start_date = end_date - datetime.timedelta(days=90)  # Last 3 months
    
    # Overall statistics
    overall_stats = AttendanceRecord.objects.filter(
        institution=institution,
        marked_at__date__gte=start_date,
        marked_at__date__lte=end_date,
        is_deleted=False
    ).aggregate(
        total_records=Count('id'),
        present=Count('id', filter=Q(status='present')),
        late=Count('id', filter=Q(status='late')),
        absent=Count('id', filter=Q(status='absent')),
        excused=Count('id', filter=Q(status='excused')),
        suspicious=Count('id', filter=Q(is_suspicious=True))
    )
    
    total_records = overall_stats['total_records'] or 0
    attendance_rate = ((overall_stats['present'] or 0) / total_records * 100) if total_records > 0 else 0
    
    # Daily trends
    daily_stats = AttendanceRecord.objects.filter(
        institution=institution,
        marked_at__date__gte=start_date,
        marked_at__date__lte=end_date,
        is_deleted=False
    ).extra({
        'date': 'date(marked_at)'
    }).values('date').annotate(
        total=Count('id'),
        present=Count('id', filter=Q(status='present')),
        absent=Count('id', filter=Q(status='absent'))
    ).order_by('date')
    
    # Course performance
    course_stats = AttendanceRecord.objects.filter(
        institution=institution,
        marked_at__date__gte=start_date,
        marked_at__date__lte=end_date,
        is_deleted=False
    ).values('session__course__id', 'session__course__title').annotate(
        total=Count('id'),
        present=Count('id', filter=Q(status='present')),
        attendance_rate=(Count('id', filter=Q(status='present')) * 100.0 / Count('id'))
    ).order_by('-attendance_rate')
    
    # Risk analysis
    high_risk_students = AttendanceRecord.objects.filter(
        institution=institution,
        marked_at__date__gte=start_date,
        marked_at__date__lte=end_date,
        is_deleted=False
    ).values('student__id', 'student__first_name', 'student__last_name').annotate(
        total=Count('id'),
        present=Count('id', filter=Q(status='present')),
        attendance_rate=(Count('id', filter=Q(status='present')) * 100.0 / Count('id'))
    ).filter(
        attendance_rate__lt=70
    ).order_by('attendance_rate')
    
    return Response({
        'period': {
            'start_date': start_date,
            'end_date': end_date
        },
        'overall_statistics': {
            'total_records': total_records,
            'present': overall_stats['present'] or 0,
            'late': overall_stats['late'] or 0,
            'absent': overall_stats['absent'] or 0,
            'excused': overall_stats['excused'] or 0,
            'suspicious': overall_stats['suspicious'] or 0,
            'attendance_rate': round(attendance_rate, 2)
        },
        'daily_trends': list(daily_stats),
        'course_performance': list(course_stats),
        'risk_analysis': {
            'high_risk_students': list(high_risk_students),
            'high_risk_count': len(high_risk_students)
        }
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def detect_anomalies(request):
    """
    Trigger attendance anomaly detection
    """
    user = request.user
    institution = user.institution
    
    # Trigger async task
    detect_attendance_anomalies.delay(institution.id)
    
    return Response({
        'message': 'Anomaly detection started'
    })
