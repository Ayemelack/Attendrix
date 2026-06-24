"""
Scheduling models for Attendrix - Advanced scheduling engine with conflict detection
"""
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from django.core.exceptions import ValidationError
from apps.core.models import TimeStampedModel, SoftDeleteModel, AuditModel, TenantModel
from apps.institutions.models import Institution, AcademicSession, HolidayCalendar
from apps.users.models import User
from apps.departments.models import Department
from apps.courses.models import Course
import uuid


class Schedule(TimeStampedModel, SoftDeleteModel, AuditModel, TenantModel):
    """
    Master schedule for class sessions and events
    """
    SCHEDULE_TYPES = [
        ('class', 'Class Session'),
        ('exam', 'Exam'),
        ('meeting', 'Meeting'),
        ('event', 'Event'),
        ('office_hours', 'Office Hours'),
        ('lab', 'Laboratory Session'),
        ('tutorial', 'Tutorial'),
        ('seminar', 'Seminar'),
        ('workshop', 'Workshop'),
        ('other', 'Other'),
    ]

    RECURRENCE_TYPES = [
        ('none', 'No Recurrence'),
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('biweekly', 'Bi-weekly'),
        ('monthly', 'Monthly'),
        ('custom', 'Custom Pattern'),
    ]

    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    schedule_type = models.CharField(max_length=20, choices=SCHEDULE_TYPES)
    
    # Course Association
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name='schedules',
        null=True,
        blank=True
    )
    
    # Timing
    start_date = models.DateField()
    end_date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    timezone = models.CharField(max_length=50, default='UTC')
    
    # Recurrence
    recurrence_type = models.CharField(max_length=20, choices=RECURRENCE_TYPES, default='none')
    recurrence_pattern = models.JSONField(default=dict, blank=True)  # Custom recurrence rules
    max_occurrences = models.IntegerField(null=True, blank=True)
    
    # Location
    location = models.CharField(max_length=200, blank=True)
    room = models.ForeignKey(
        'departments.DepartmentResource',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='schedules',
        limit_choices_to={'resource_type': 'classroom'}
    )
    virtual_meeting_url = models.URLField(blank=True)
    
    # Personnel
    lecturer = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='lecturer_schedules',
        limit_choices_to={'role': 'lecturer'}
    )
    assistant_lecturer = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assistant_schedules',
        limit_choices_to={'role': 'lecturer'}
    )
    
    # Enrollment
    max_participants = models.IntegerField(null=True, blank=True)
    is_mandatory = models.BooleanField(default=False)
    requires_registration = models.BooleanField(default=False)
    
    # Status
    is_active = models.BooleanField(default=True)
    is_published = models.BooleanField(default=False)
    is_cancelled = models.BooleanField(default=False)
    
    # Conflict Detection
    has_conflicts = models.BooleanField(default=False)
    conflict_details = models.JSONField(default=list, blank=True)
    
    class Meta:
        db_table = 'scheduling_schedule'
        verbose_name = 'Schedule'
        verbose_name_plural = 'Schedules'
        indexes = [
            models.Index(fields=['institution', 'start_date', 'end_date']),
            models.Index(fields=['course']),
            models.Index(fields=['lecturer']),
            models.Index(fields=['room']),
            models.Index(fields=['schedule_type']),
            models.Index(fields=['is_active', 'is_published']),
            models.Index(fields=['has_conflicts']),
        ]

    def __str__(self):
        return f"{self.title} - {self.start_date} {self.start_time}"

    def clean(self):
        """Validate schedule data"""
        if self.start_date > self.end_date:
            raise ValidationError("Start date cannot be after end date")
        
        if self.start_time >= self.end_time:
            raise ValidationError("Start time must be before end time")
        
        # Check for holiday conflicts
        if self._conflicts_with_holidays():
            raise ValidationError("Schedule conflicts with institutional holidays")

    def _conflicts_with_holidays(self):
        """Check if schedule conflicts with holidays"""
        holidays = HolidayCalendar.objects.filter(
            institution=self.institution,
            date__range=[self.start_date, self.end_date],
            affects_attendance=True
        )
        return holidays.exists()

    def detect_conflicts(self):
        """Detect scheduling conflicts"""
        conflicts = []
        
        # Lecturer conflicts
        if self.lecturer:
            lecturer_conflicts = Schedule.objects.filter(
                institution=self.institution,
                lecturer=self.lecturer,
                start_date__lte=self.end_date,
                end_date__gte=self.start_date,
                is_active=True,
                is_cancelled=False
            ).exclude(pk=self.pk)
            
            for conflict in lecturer_conflicts:
                if self._time_overlaps(conflict):
                    conflicts.append({
                        'type': 'lecturer_conflict',
                        'conflict_with': conflict.title,
                        'conflict_id': conflict.id,
                        'details': f'Lecturer {self.lecturer.get_full_name()} is already scheduled'
                    })
        
        # Room conflicts
        if self.room:
            room_conflicts = Schedule.objects.filter(
                institution=self.institution,
                room=self.room,
                start_date__lte=self.end_date,
                end_date__gte=self.start_date,
                is_active=True,
                is_cancelled=False
            ).exclude(pk=self.pk)
            
            for conflict in room_conflicts:
                if self._time_overlaps(conflict):
                    conflicts.append({
                        'type': 'room_conflict',
                        'conflict_with': conflict.title,
                        'conflict_id': conflict.id,
                        'details': f'Room {self.room.name} is already occupied'
                    })
        
        # Student conflicts (for course schedules)
        if self.course:
            enrolled_students = self.course.enrollments.filter(status='enrolled')
            for enrollment in enrolled_students:
                student_conflicts = Schedule.objects.filter(
                    institution=self.institution,
                    course__enrollments__student=enrollment.student,
                    start_date__lte=self.end_date,
                    end_date__gte=self.start_date,
                    is_active=True,
                    is_cancelled=False
                ).exclude(pk=self.pk)
                
                for conflict in student_conflicts:
                    if self._time_overlaps(conflict):
                        conflicts.append({
                            'type': 'student_conflict',
                            'conflict_with': conflict.title,
                            'conflict_id': conflict.id,
                            'student': enrollment.student.get_full_name(),
                            'details': f'Student {enrollment.student.get_full_name()} has conflicting schedule'
                        })
        
        self.has_conflicts = len(conflicts) > 0
        self.conflict_details = conflicts
        self.save(update_fields=['has_conflicts', 'conflict_details'])
        
        return conflicts

    def _time_overlaps(self, other_schedule):
        """Check if this schedule overlaps with another"""
        # Same day check
        if self.start_date <= other_schedule.end_date and self.end_date >= other_schedule.start_date:
            # Time overlap check
            return (self.start_time < other_schedule.end_time and 
                   self.end_time > other_schedule.start_time)
        return False

    def generate_occurrences(self):
        """Generate individual schedule occurrences"""
        from .tasks import generate_schedule_occurrences
        generate_schedule_occurrences.delay(self.id)


class ScheduleOccurrence(TimeStampedModel, SoftDeleteModel, AuditModel, TenantModel):
    """
    Individual occurrences of recurring schedules
    """
    parent_schedule = models.ForeignKey(
        Schedule,
        on_delete=models.CASCADE,
        related_name='occurrences'
    )
    
    # Specific timing
    occurrence_date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=[
            ('scheduled', 'Scheduled'),
            ('in_progress', 'In Progress'),
            ('completed', 'Completed'),
            'cancelled', 'Cancelled'),
            ('postponed', 'Postponed'),
        ],
        default='scheduled'
    )
    
    # Attendance tracking
    attendance_session = models.OneToOneField(
        'attendance.AttendanceSession',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='schedule_occurrence'
    )
    
    # Notes
    notes = models.TextField(blank=True)
    cancellation_reason = models.TextField(blank=True)
    
    # Override settings (for individual occurrences)
    override_location = models.CharField(max_length=200, blank=True)
    override_room = models.ForeignKey(
        'departments.DepartmentResource',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='override_occurrences'
    )
    override_lecturer = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='override_occurrences',
        limit_choices_to={'role': 'lecturer'}
    )
    
    class Meta:
        db_table = 'scheduling_schedule_occurrence'
        verbose_name = 'Schedule Occurrence'
        verbose_name_plural = 'Schedule Occurrences'
        unique_together = ['parent_schedule', 'occurrence_date']
        indexes = [
            models.Index(fields=['parent_schedule', 'occurrence_date']),
            models.Index(fields=['occurrence_date', 'status']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return f"{self.parent_schedule.title} - {self.occurrence_date}"


class ScheduleTemplate(TimeStampedModel, SoftDeleteModel, AuditModel, TenantModel):
    """
    Reusable schedule templates
    """
    TEMPLATE_TYPES = [
        ('course', 'Course Template'),
        ('exam', 'Exam Template'),
        ('meeting', 'Meeting Template'),
        ('event', 'Event Template'),
    ]

    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    template_type = models.CharField(max_length=20, choices=TEMPLATE_TYPES)
    
    # Template structure
    template_data = models.JSONField(default=dict)  # Schedule structure
    default_settings = models.JSONField(default=dict)  # Default values
    
    # Usage tracking
    usage_count = models.IntegerField(default=0)
    last_used = models.DateTimeField(null=True, blank=True)
    
    # Sharing
    is_public = models.BooleanField(default=False)  # Available to all departments
    departments = models.ManyToManyField(
        Department,
        blank=True,
        related_name='schedule_templates'
    )
    
    class Meta:
        db_table = 'scheduling_schedule_template'
        verbose_name = 'Schedule Template'
        verbose_name_plural = 'Schedule Templates'
        indexes = [
            models.Index(fields=['institution', 'template_type']),
            models.Index(fields=['is_public']),
            models.Index(fields=['usage_count']),
        ]

    def __str__(self):
        return f"{self.name} - {self.template_type}"


class ScheduleConflict(TimeStampedModel, AuditModel, TenantModel):
    """
    Track and manage schedule conflicts
    """
    CONFLICT_TYPES = [
        ('lecturer', 'Lecturer Conflict'),
        ('room', 'Room Conflict'),
        ('student', 'Student Conflict'),
        ('resource', 'Resource Conflict'),
        ('holiday', 'Holiday Conflict'),
        ('maintenance', 'Maintenance Conflict'),
    ]

    SEVERITY_LEVELS = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ]

    STATUS_CHOICES = [
        ('open', 'Open'),
        ('reviewing', 'Reviewing'),
        ('resolved', 'Resolved'),
        ('ignored', 'Ignored'),
    ]

    conflict_type = models.CharField(max_length=20, choices=CONFLICT_TYPES)
    severity = models.CharField(max_length=20, choices=SEVERITY_LEVELS)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')
    
    # Conflicting schedules
    schedule_1 = models.ForeignKey(
        Schedule,
        on_delete=models.CASCADE,
        related_name='conflicts_as_1'
    )
    schedule_2 = models.ForeignKey(
        Schedule,
        on_delete=models.CASCADE,
        related_name='conflicts_as_2'
    )
    
    # Conflict details
    description = models.TextField()
    conflict_date = models.DateField()
    conflict_time_start = models.TimeField()
    conflict_time_end = models.TimeField()
    
    # Resolution
    resolution_notes = models.TextField(blank=True)
    resolved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='resolved_conflicts'
    )
    resolved_at = models.DateTimeField(null=True, blank=True)
    
    # Auto-resolution suggestions
    suggested_solutions = models.JSONField(default=list, blank=True)
    auto_resolvable = models.BooleanField(default=False)
    
    class Meta:
        db_table = 'scheduling_schedule_conflict'
        verbose_name = 'Schedule Conflict'
        verbose_name_plural = 'Schedule Conflicts'
        unique_together = ['schedule_1', 'schedule_2', 'conflict_date']
        indexes = [
            models.Index(fields=['institution', 'status']),
            models.Index(fields=['conflict_type']),
            models.Index(fields=['severity']),
            models.Index(fields=['conflict_date']),
        ]

    def __str__(self):
        return f"{self.conflict_type} - {self.conflict_date}"


class ScheduleAdjustment(TimeStampedModel, AuditModel, TenantModel):
    """
    Track schedule adjustments and changes
    """
    ADJUSTMENT_TYPES = [
        ('time_change', 'Time Change'),
        ('date_change', 'Date Change'),
        ('location_change', 'Location Change'),
        ('lecturer_change', 'Lecturer Change'),
        ('cancellation', 'Cancellation'),
        ('postponement', 'Postponement'),
        ('duration_change', 'Duration Change'),
    ]

    schedule = models.ForeignKey(
        Schedule,
        on_delete=models.CASCADE,
        related_name='adjustments'
    )
    adjustment_type = models.CharField(max_length=20, choices=ADJUSTMENT_TYPES)
    
    # Original values
    original_data = models.JSONField(default=dict)
    new_data = models.JSONField(default=dict)
    
    # Reason and approval
    reason = models.TextField()
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_adjustments'
    )
    approval_notes = models.TextField(blank=True)
    
    # Impact assessment
    affected_students = models.IntegerField(default=0)
    affected_lecturers = models.IntegerField(default=0)
    notification_sent = models.BooleanField(default=False)
    
    class Meta:
        db_table = 'scheduling_schedule_adjustment'
        verbose_name = 'Schedule Adjustment'
        verbose_name_plural = 'Schedule Adjustments'
        indexes = [
            models.Index(fields=['schedule', 'created_at']),
            models.Index(fields=['adjustment_type']),
            models.Index(fields=['approved_by']),
        ]

    def __str__(self):
        return f"{self.schedule.title} - {self.adjustment_type}"


class SchedulePreference(TimeStampedModel, TenantModel):
    """
    User scheduling preferences
    """
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='schedule_preferences'
    )
    
    # Time preferences
    preferred_start_time = models.TimeField(null=True, blank=True)
    preferred_end_time = models.TimeField(null=True, blank=True)
    preferred_days = models.JSONField(default=list)  # [1,2,3,4,5] for Mon-Fri
    
    # Location preferences
    preferred_rooms = models.ManyToManyField(
        'departments.DepartmentResource',
        blank=True,
        related_name='preferred_by'
    )
    preferred_locations = models.JSONField(default=list, blank=True)
    
    # Teaching preferences
    max_consecutive_classes = models.IntegerField(default=3)
    min_break_between_classes = models.IntegerField(default=15)  # minutes
    preferred_class_duration = models.IntegerField(default=60)  # minutes
    
    # Availability
    unavailable_times = models.JSONField(default=list, blank=True)  # Blocked time slots
    preferred_workload = models.IntegerField(default=20)  # hours per week
    
    class Meta:
        db_table = 'scheduling_schedule_preference'
        verbose_name = 'Schedule Preference'
        verbose_name_plural = 'Schedule Preferences'
        unique_together = ['user', 'institution']
        indexes = [
            models.Index(fields=['user', 'institution']),
        ]

    def __str__(self):
        return f"Preferences for {self.user.get_full_name()}"


class ScheduleAnalytics(TimeStampedModel, TenantModel):
    """
    Schedule analytics and statistics
    """
    date = models.DateField()
    
    # Utilization metrics
    total_schedules = models.IntegerField(default=0)
    active_schedules = models.IntegerField(default=0)
    cancelled_schedules = models.IntegerField(default=0)
    
    # Room utilization
    total_rooms = models.IntegerField(default=0)
    occupied_rooms = models.IntegerField(default=0)
    room_utilization_percentage = models.FloatField(default=0.0)
    
    # Lecturer workload
    total_lecturer_hours = models.FloatField(default=0.0)
    average_lecturer_workload = models.FloatField(default=0.0)
    overloaded_lecturers = models.IntegerField(default=0)
    
    # Conflict metrics
    total_conflicts = models.IntegerField(default=0)
    resolved_conflicts = models.IntegerField(default=0)
    conflict_resolution_rate = models.FloatField(default=0.0)
    
    # Student metrics
    total_student_hours = models.FloatField(default=0.0)
    average_student_schedule_density = models.FloatField(default=0.0)
    
    class Meta:
        db_table = 'scheduling_schedule_analytics'
        verbose_name = 'Schedule Analytics'
        verbose_name_plural = 'Schedule Analytics'
        unique_together = ['institution', 'date']
        indexes = [
            models.Index(fields=['institution', 'date']),
            models.Index(fields=['date']),
        ]

    def __str__(self):
        return f"Analytics for {self.institution.name} - {self.date}"
