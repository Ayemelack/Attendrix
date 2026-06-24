"""
Scheduling views for Attendrix - Advanced scheduling engine
"""
from rest_framework import status, generics, viewsets
from rest_framework.decorators import api_view, permission_classes, action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from django.utils import timezone
from django.db.models import Q, Count, Avg
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from apps.core.models import ActivityLog
from apps.core.permissions import IsInstitutionAdmin, IsLecturer
from apps.scheduling.models import (
    Schedule, ScheduleOccurrence, ScheduleTemplate, ScheduleConflict,
    ScheduleAdjustment, SchedulePreference, ScheduleAnalytics
)
from apps.scheduling.serializers import (
    ScheduleSerializer, ScheduleOccurrenceSerializer, ScheduleTemplateSerializer,
    ScheduleConflictSerializer, ScheduleAdjustmentSerializer, SchedulePreferenceSerializer,
    ScheduleAnalyticsSerializer, BulkScheduleSerializer, ScheduleConflictResolutionSerializer
)
from apps.scheduling.tasks import generate_schedule_occurrences, detect_schedule_conflicts
import datetime


class ScheduleViewSet(viewsets.ModelViewSet):
    """
    Schedule viewset with full CRUD operations
    """
    serializer_class = ScheduleSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['schedule_type', 'course', 'lecturer', 'room', 'is_active', 'is_published']
    search_fields = ['title', 'description', 'location']
    ordering_fields = ['start_date', 'start_time', 'created_at']
    ordering = ['start_date', 'start_time']

    def get_queryset(self):
        """Filter schedules by institution and user role"""
        user = self.request.user
        queryset = Schedule.objects.filter(
            institution=user.institution,
            is_deleted=False
        )
        
        # Filter based on user role
        if user.is_student():
            # Students can only see schedules for their enrolled courses
            queryset = queryset.filter(
                course__enrollments__student=user,
                course__enrollments__status='enrolled'
            )
        elif user.is_lecturer():
            # Lecturers can see their own schedules and department schedules
            queryset = queryset.filter(
                Q(lecturer=user) | Q(course__department=user.department)
            )
        elif user.is_institution_admin():
            # Institution admins can see all schedules
            pass
        elif user.is_super_admin():
            # Super admins can see all schedules
            pass
        else:
            # Employees and others have limited access
            queryset = queryset.filter(is_published=True)
        
        return queryset.distinct()

    @action(detail=True, methods=['post'])
    def detect_conflicts(self, request, pk=None):
        """Detect conflicts for this schedule"""
        schedule = self.get_object()
        conflicts = schedule.detect_conflicts()
        
        return Response({
            'message': 'Conflict detection completed',
            'has_conflicts': schedule.has_conflicts,
            'conflicts': schedule.conflict_details
        })

    @action(detail=True, methods=['post'])
    def generate_occurrences(self, request, pk=None):
        """Generate occurrences for recurring schedule"""
        schedule = self.get_object()
        
        if schedule.recurrence_type == 'none':
            return Response({
                'error': 'Cannot generate occurrences for non-recurring schedule'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Trigger async task
        generate_schedule_occurrences.delay(schedule.id)
        
        return Response({
            'message': 'Schedule occurrence generation started'
        })

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """Cancel schedule"""
        schedule = self.get_object()
        reason = request.data.get('reason', '')
        
        schedule.is_cancelled = True
        schedule.save()
        
        # Cancel all future occurrences
        schedule.occurrences.filter(
            occurrence_date__gte=timezone.now().date(),
            status='scheduled'
        ).update(status='cancelled')
        
        # Log activity
        ActivityLog.objects.create(
            user=request.user,
            institution=schedule.institution,
            action_type='update',
            action_description=f'Schedule cancelled: {schedule.title}',
            severity='medium'
        )
        
        return Response({'message': 'Schedule cancelled successfully'})

    @action(detail=True, methods=['post'])
    def duplicate(self, request, pk=None):
        """Duplicate schedule"""
        schedule = self.get_object()
        
        # Create copy
        new_schedule = Schedule.objects.create(
            institution=schedule.institution,
            title=f"{schedule.title} (Copy)",
            description=schedule.description,
            schedule_type=schedule.schedule_type,
            course=schedule.course,
            start_date=timezone.now().date(),
            end_date=timezone.now().date(),
            start_time=schedule.start_time,
            end_time=schedule.end_time,
            location=schedule.location,
            room=schedule.room,
            lecturer=schedule.lecturer,
            assistant_lecturer=schedule.assistant_lecturer,
            max_participants=schedule.max_participants,
            is_mandatory=schedule.is_mandatory,
            created_by=request.user
        )
        
        # Detect conflicts for new schedule
        new_schedule.detect_conflicts()
        
        return Response({
            'message': 'Schedule duplicated successfully',
            'schedule_id': new_schedule.id
        }, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['get'])
    def my_schedules(self, request):
        """Get current user's schedules"""
        user = request.user
        queryset = self.get_queryset()
        
        if user.is_lecturer():
            queryset = queryset.filter(lecturer=user)
        elif user.is_student():
            queryset = queryset.filter(
                course__enrollments__student=user,
                course__enrollments__status='enrolled'
            )
        
        page = self.paginate_queryset(queryset)
        serializer = self.get_serializer(page, many=True)
        return self.get_paginated_response(serializer.data)

    @action(detail=False, methods=['get'])
    def calendar_view(self, request):
        """Get schedules in calendar format"""
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        
        queryset = self.get_queryset()
        
        if start_date:
            queryset = queryset.filter(start_date__gte=start_date)
        if end_date:
            queryset = queryset.filter(end_date__lte=end_date)
        
        schedules = []
        for schedule in queryset:
            occurrences = schedule.occurrences.filter(
                occurrence_date__gte=start_date or timezone.now().date(),
                occurrence_date__lte=end_date or timezone.now().date() + datetime.timedelta(days=30),
                is_deleted=False
            )
            
            for occurrence in occurrences:
                schedules.append({
                    'id': occurrence.id,
                    'title': schedule.title,
                    'start': f"{occurrence.occurrence_date}T{occurrence.start_time}",
                    'end': f"{occurrence.occurrence_date}T{occurrence.end_time}",
                    'type': schedule.schedule_type,
                    'location': occurrence.override_location or schedule.location,
                    'lecturer': schedule.lecturer.get_full_name() if schedule.lecturer else None,
                    'course': schedule.course.title if schedule.course else None,
                    'status': occurrence.status
                })
        
        return Response(schedules)


class ScheduleOccurrenceViewSet(viewsets.ModelViewSet):
    """
    Schedule occurrence viewset
    """
    serializer_class = ScheduleOccurrenceSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['status', 'parent_schedule']
    search_fields = ['notes']
    ordering_fields = ['occurrence_date', 'start_time']
    ordering = ['occurrence_date', 'start_time']

    def get_queryset(self):
        """Filter occurrences by institution and user role"""
        user = self.request.user
        queryset = ScheduleOccurrence.objects.filter(
            institution=user.institution,
            is_deleted=False
        )
        
        # Filter based on user role
        if user.is_student():
            queryset = queryset.filter(
                parent_schedule__course__enrollments__student=user,
                parent_schedule__course__enrollments__status='enrolled'
            )
        elif user.is_lecturer():
            queryset = queryset.filter(
                Q(parent_schedule__lecturer=user) | 
                Q(parent_schedule__course__department=user.department)
            )
        
        return queryset.distinct()

    @action(detail=True, methods=['post'])
    def mark_attendance_ready(self, request, pk=None):
        """Mark occurrence as ready for attendance"""
        occurrence = self.get_object()
        
        if occurrence.status != 'scheduled':
            return Response({
                'error': 'Can only mark scheduled occurrences for attendance'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Create attendance session
        from apps.attendance.models import AttendanceSession
        session, created = AttendanceSession.objects.get_or_create(
            schedule_occurrence=occurrence,
            defaults={
                'institution': occurrence.institution,
                'course': occurrence.parent_schedule.course,
                'lecturer': occurrence.parent_schedule.lecturer,
                'session_code': self._generate_session_code(),
                'start_time': timezone.datetime.combine(
                    occurrence.occurrence_date, 
                    occurrence.start_time
                ),
                'end_time': timezone.datetime.combine(
                    occurrence.occurrence_date, 
                    occurrence.end_time
                ),
                'is_active': False,
                'created_by': request.user
            }
        )
        
        occurrence.attendance_session = session
        occurrence.save()
        
        return Response({
            'message': 'Attendance session created',
            'session_code': session.session_code
        })

    def _generate_session_code(self):
        """Generate unique session code"""
        import random
        import string
        return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))


class ScheduleTemplateViewSet(viewsets.ModelViewSet):
    """
    Schedule template viewset
    """
    serializer_class = ScheduleTemplateSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['template_type', 'is_public']
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'usage_count', 'created_at']
    ordering = ['name']

    def get_queryset(self):
        """Filter templates by institution and access"""
        user = self.request.user
        queryset = ScheduleTemplate.objects.filter(
            institution=user.institution,
            is_deleted=False
        )
        
        # Show public templates and user's department templates
        queryset = queryset.filter(
            Q(is_public=True) | 
            Q(departments=user.department) |
            Q(created_by=user)
        )
        
        return queryset.distinct()

    @action(detail=True, methods=['post'])
    def apply_template(self, request, pk=None):
        """Apply template to create new schedule"""
        template = self.get_object()
        
        # Get template data
        template_data = template.template_data
        start_date = request.data.get('start_date')
        end_date = request.data.get('end_date')
        
        if not start_date or not end_date:
            return Response({
                'error': 'Start date and end date are required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Create schedule from template
        schedule = Schedule.objects.create(
            institution=template.institution,
            title=template_data.get('title', 'Untitled Schedule'),
            description=template_data.get('description', ''),
            schedule_type=template_data.get('schedule_type', 'class'),
            course_id=template_data.get('course_id'),
            start_date=start_date,
            end_date=end_date,
            start_time=template_data.get('start_time', '09:00'),
            end_time=template_data.get('end_time', '10:00'),
            location=template_data.get('location', ''),
            room_id=template_data.get('room_id'),
            lecturer_id=template_data.get('lecturer_id'),
            created_by=request.user
        )
        
        # Update template usage
        template.usage_count += 1
        template.last_used = timezone.now()
        template.save()
        
        return Response({
            'message': 'Template applied successfully',
            'schedule_id': schedule.id
        }, status=status.HTTP_201_CREATED)


class ScheduleConflictViewSet(viewsets.ModelViewSet):
    """
    Schedule conflict viewset
    """
    serializer_class = ScheduleConflictSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['conflict_type', 'severity', 'status']
    search_fields = ['description']
    ordering_fields = ['conflict_date', 'created_at']
    ordering = ['-conflict_date', '-created_at']

    def get_queryset(self):
        """Filter conflicts by institution"""
        user = self.request.user
        return ScheduleConflict.objects.filter(
            institution=user.institution
        )

    @action(detail=True, methods=['post'])
    def resolve(self, request, pk=None):
        """Resolve schedule conflict"""
        conflict = self.get_object()
        serializer = ScheduleConflictResolutionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        resolution_type = serializer.validated_data['resolution_type']
        resolution_notes = serializer.validated_data.get('resolution_notes', '')
        
        # Apply resolution based on type
        if resolution_type == 'keep_first':
            conflict.schedule_2.is_cancelled = True
            conflict.schedule_2.save()
        elif resolution_type == 'keep_second':
            conflict.schedule_1.is_cancelled = True
            conflict.schedule_1.save()
        elif resolution_type == 'cancel_both':
            conflict.schedule_1.is_cancelled = True
            conflict.schedule_2.is_cancelled = True
            conflict.schedule_1.save()
            conflict.schedule_2.save()
        elif resolution_type in ['reschedule_first', 'reschedule_second']:
            # Reschedule logic would go here
            schedule = conflict.schedule_1 if resolution_type == 'reschedule_first' else conflict.schedule_2
            new_date = serializer.validated_data.get('new_date')
            new_start_time = serializer.validated_data.get('new_start_time')
            new_end_time = serializer.validated_data.get('new_end_time')
            
            if new_date:
                schedule.start_date = new_date
                schedule.end_date = new_date
            if new_start_time:
                schedule.start_time = new_start_time
            if new_end_time:
                schedule.end_time = new_end_time
            
            schedule.save()
        
        # Update conflict status
        conflict.status = 'resolved'
        conflict.resolution_notes = resolution_notes
        conflict.resolved_by = request.user
        conflict.resolved_at = timezone.now()
        conflict.save()
        
        return Response({'message': 'Conflict resolved successfully'})

    @action(detail=False, methods=['get'])
    def unresolved(self, request):
        """Get unresolved conflicts"""
        queryset = self.get_queryset().filter(status='open')
        page = self.paginate_queryset(queryset)
        serializer = self.get_serializer(page, many=True)
        return self.get_paginated_response(serializer.data)


class SchedulePreferenceViewSet(viewsets.ModelViewSet):
    """
    Schedule preference viewset
    """
    serializer_class = SchedulePreferenceSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Get user's schedule preferences"""
        user = self.request.user
        return SchedulePreference.objects.filter(
            user=user,
            institution=user.institution
        )

    @action(detail=False, methods=['get', 'post', 'put'])
    def my_preferences(self, request):
        """Get or update user's preferences"""
        user = request.user
        
        if request.method == 'GET':
            preference, created = SchedulePreference.objects.get_or_create(
                user=user,
                institution=user.institution
            )
            serializer = self.get_serializer(preference)
            return Response(serializer.data)
        
        elif request.method in ['POST', 'PUT']:
            preference, created = SchedulePreference.objects.get_or_create(
                user=user,
                institution=user.institution
            )
            serializer = self.get_serializer(preference, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response(serializer.data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def bulk_create_schedules(request):
    """
    Bulk create schedules
    """
    serializer = BulkScheduleSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    
    result = serializer.save()
    
    return Response({
        'message': f'Created {len(result["created_schedules"])} schedules',
        'schedules': [s.id for s in result["created_schedules"]]
    }, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def schedule_analytics(request):
    """
    Get schedule analytics
    """
    user = request.user
    institution = user.institution
    
    # Get date range
    start_date = request.GET.get('start_date', timezone.now().date() - datetime.timedelta(days=30))
    end_date = request.GET.get('end_date', timezone.now().date())
    
    # Schedule statistics
    total_schedules = Schedule.objects.filter(
        institution=institution,
        start_date__gte=start_date,
        end_date__lte=end_date,
        is_deleted=False
    ).count()
    
    active_schedules = Schedule.objects.filter(
        institution=institution,
        start_date__gte=start_date,
        end_date__lte=end_date,
        is_active=True,
        is_cancelled=False,
        is_deleted=False
    ).count()
    
    # Conflict statistics
    total_conflicts = ScheduleConflict.objects.filter(
        institution=institution,
        conflict_date__gte=start_date,
        conflict_date__lte=end_date
    ).count()
    
    resolved_conflicts = ScheduleConflict.objects.filter(
        institution=institution,
        conflict_date__gte=start_date,
        conflict_date__lte=end_date,
        status='resolved'
    ).count()
    
    # Room utilization
    occupied_rooms = Schedule.objects.filter(
        institution=institution,
        start_date__gte=start_date,
        end_date__lte=end_date,
        room__isnull=False,
        is_active=True,
        is_cancelled=False,
        is_deleted=False
    ).values('room').distinct().count()
    
    total_rooms = DepartmentResource.objects.filter(
        institution=institution,
        resource_type='classroom',
        is_active=True,
        is_deleted=False
    ).count()
    
    room_utilization = (occupied_rooms / total_rooms * 100) if total_rooms > 0 else 0
    
    return Response({
        'period': {
            'start_date': start_date,
            'end_date': end_date
        },
        'schedules': {
            'total': total_schedules,
            'active': active_schedules,
            'cancelled': total_schedules - active_schedules
        },
        'conflicts': {
            'total': total_conflicts,
            'resolved': resolved_conflicts,
            'unresolved': total_conflicts - resolved_conflicts,
            'resolution_rate': (resolved_conflicts / total_conflicts * 100) if total_conflicts > 0 else 0
        },
        'utilization': {
            'rooms': {
                'total': total_rooms,
                'occupied': occupied_rooms,
                'utilization_percentage': room_utilization
            }
        }
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def available_slots(request):
    """
    Get available time slots for scheduling
    """
    user = request.user
    date = request.GET.get('date', timezone.now().date())
    
    # Get existing schedules for the date
    existing_schedules = Schedule.objects.filter(
        institution=user.institution,
        start_date__lte=date,
        end_date__gte=date,
        is_active=True,
        is_cancelled=False,
        is_deleted=False
    )
    
    # Generate available slots (simplified logic)
    all_slots = []
    for hour in range(8, 20):  # 8 AM to 8 PM
        for minute in [0, 30]:  # Every 30 minutes
            slot_time = f"{hour:02d}:{minute:02d}"
            all_slots.append(slot_time)
    
    # Remove occupied slots
    occupied_slots = set()
    for schedule in existing_schedules:
        start_hour = schedule.start_time.hour
        start_minute = schedule.start_time.minute
        end_hour = schedule.end_time.hour
        end_minute = schedule.end_time.minute
        
        # Mark all 30-minute slots in this range as occupied
        current_hour = start_hour
        current_minute = start_minute
        
        while (current_hour < end_hour or 
               (current_hour == end_hour and current_minute < end_minute)):
            slot = f"{current_hour:02d}:{current_minute:02d}"
            occupied_slots.add(slot)
            
            current_minute += 30
            if current_minute >= 60:
                current_minute = 0
                current_hour += 1
    
    available_slots = [slot for slot in all_slots if slot not in occupied_slots]
    
    return Response({
        'date': date,
        'available_slots': available_slots,
        'total_slots': len(all_slots),
        'occupied_slots': len(occupied_slots)
    })
