"""
Course models for academic curriculum management
"""
from django.db import models
from django.core.validators import RegexValidator, MinValueValidator, MaxValueValidator
from django.utils import timezone
from apps.core.models import TimeStampedModel, SoftDeleteModel, AuditModel, TenantModel
from apps.institutions.models import Institution, AcademicSession
from apps.users.models import User
from apps.departments.models import Department
import uuid


class Course(TimeStampedModel, SoftDeleteModel, AuditModel, TenantModel):
    """
    Course model for academic curriculum
    """
    COURSE_TYPES = [
        ('core', 'Core Course'),
        ('elective', 'Elective'),
        ('prerequisite', 'Prerequisite'),
        ('lab', 'Laboratory'),
        ('seminar', 'Seminar'),
        ('workshop', 'Workshop'),
        ('internship', 'Internship'),
        ('thesis', 'Thesis'),
        ('other', 'Other'),
    ]

    DIFFICULTY_LEVELS = [
        ('beginner', 'Beginner'),
        ('intermediate', 'Intermediate'),
        ('advanced', 'Advanced'),
        ('expert', 'Expert'),
    ]

    code = models.CharField(
        max_length=20,
        validators=[RegexValidator(r'^[A-Z0-9]+$', 'Only uppercase letters and numbers allowed')]
    )
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    course_type = models.CharField(max_length=20, choices=COURSE_TYPES)
    difficulty_level = models.CharField(max_length=20, choices=DIFFICULTY_LEVELS)
    
    # Academic Information
    department = models.ForeignKey(
        Department,
        on_delete=models.CASCADE,
        related_name='courses'
    )
    academic_session = models.ForeignKey(
        AcademicSession,
        on_delete=models.CASCADE,
        related_name='courses'
    )
    
    # Credits and Hours
    credit_hours = models.IntegerField(validators=[MinValueValidator(0)])
    lecture_hours_per_week = models.IntegerField(validators=[MinValueValidator(0)])
    lab_hours_per_week = models.IntegerField(validators=[MinValueValidator(0)])
    total_hours = models.IntegerField(validators=[MinValueValidator(0)])
    
    # Capacity
    max_students = models.IntegerField(validators=[MinValueValidator(1)])
    current_enrollment = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    
    # Prerequisites
    prerequisites = models.ManyToManyField(
        'self',
        blank=True,
        symmetrical=False,
        related_name='dependent_courses'
    )
    
    # Course Materials
    syllabus = models.FileField(upload_to='course_syllabi/', blank=True)
    course_outline = models.JSONField(default=dict, blank=True)
    learning_objectives = models.JSONField(default=list, blank=True)
    
    # Assessment
    assessment_criteria = models.JSONField(default=dict, blank=True)
    passing_grade = models.FloatField(
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        default=50.0
    )
    
    # Status
    is_active = models.BooleanField(default=True)
    is_enrollment_open = models.BooleanField(default=True)
    enrollment_deadline = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'courses_course'
        verbose_name = 'Course'
        verbose_name_plural = 'Courses'
        unique_together = ['institution', 'code', 'academic_session']
        indexes = [
            models.Index(fields=['institution', 'code']),
            models.Index(fields=['department']),
            models.Index(fields=['academic_session']),
            models.Index(fields=['course_type']),
            models.Index(fields=['difficulty_level']),
            models.Index(fields=['is_active', 'is_enrollment_open']),
        ]

    def __str__(self):
        return f"{self.code} - {self.title}"

    @property
    def is_full(self):
        """Check if course is at maximum capacity"""
        return self.current_enrollment >= self.max_students

    @property
    def enrollment_percentage(self):
        """Calculate enrollment percentage"""
        if self.max_students == 0:
            return 0
        return (self.current_enrollment / self.max_students) * 100

    @property
    def has_prerequisites(self):
        """Check if course has prerequisites"""
        return self.prerequisites.exists()

    def can_enroll(self, student):
        """Check if student can enroll in course"""
        if self.is_full or not self.is_enrollment_open:
            return False
        
        if self.enrollment_deadline and timezone.now() > self.enrollment_deadline:
            return False
        
        # Check prerequisites
        if self.has_prerequisites:
            completed_courses = CourseEnrollment.objects.filter(
                student=student,
                course__in=self.prerequisites.all(),
                status='completed'
            ).values_list('course_id', flat=True)
            
            required_prereqs = set(self.prerequisites.values_list('id', flat=True))
            if not required_prereqs.issubset(set(completed_courses)):
                return False
        
        return True


class CourseEnrollment(TimeStampedModel, AuditModel, TenantModel):
    """
    Course enrollment model for student-course relationships
    """
    ENROLLMENT_STATUS = [
        ('pending', 'Pending'),
        ('enrolled', 'Enrolled'),
        ('dropped', 'Dropped'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('withdrawn', 'Withdrawn'),
    ]

    student = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='course_enrollments',
        limit_choices_to={'role': 'student'}
    )
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name='enrollments'
    )
    status = models.CharField(max_length=20, choices=ENROLLMENT_STATUS, default='pending')
    
    # Enrollment Details
    enrollment_date = models.DateTimeField(default=timezone.now)
    completion_date = models.DateTimeField(null=True, blank=True)
    final_grade = models.FloatField(null=True, blank=True)
    grade_points = models.FloatField(null=True, blank=True)
    
    # Attendance Tracking
    total_sessions = models.IntegerField(default=0)
    attended_sessions = models.IntegerField(default=0)
    attendance_percentage = models.FloatField(default=0.0)
    
    # Assessment Tracking
    assignment_scores = models.JSONField(default=dict, blank=True)
    exam_scores = models.JSONField(default=dict, blank=True)
    participation_score = models.FloatField(default=0.0)
    
    # Notes
    instructor_notes = models.TextField(blank=True)
    admin_notes = models.TextField(blank=True)
    
    class Meta:
        db_table = 'courses_course_enrollment'
        verbose_name = 'Course Enrollment'
        verbose_name_plural = 'Course Enrollments'
        unique_together = ['student', 'course']
        indexes = [
            models.Index(fields=['student', 'status']),
            models.Index(fields=['course', 'status']),
            models.Index(fields=['enrollment_date']),
            models.Index(fields=['attendance_percentage']),
        ]

    def __str__(self):
        return f"{self.student.get_full_name()} - {self.course.code}"

    def calculate_attendance_percentage(self):
        """Calculate attendance percentage"""
        if self.total_sessions == 0:
            return 0.0
        self.attendance_percentage = (self.attended_sessions / self.total_sessions) * 100
        self.save(update_fields=['attendance_percentage'])
        return self.attendance_percentage

    def calculate_final_grade(self):
        """Calculate final grade based on assessment criteria"""
        if not self.course.assessment_criteria:
            return None
        
        total_weighted_score = 0.0
        total_weight = 0.0
        
        # Calculate weighted scores
        criteria = self.course.assessment_criteria
        if 'assignments' in criteria:
            assignment_weight = criteria['assignments'].get('weight', 0)
            assignment_score = self.calculate_assignment_average()
            total_weighted_score += assignment_score * assignment_weight
            total_weight += assignment_weight
        
        if 'exams' in criteria:
            exam_weight = criteria['exams'].get('weight', 0)
            exam_score = self.calculate_exam_average()
            total_weighted_score += exam_score * exam_weight
            total_weight += exam_weight
        
        if 'participation' in criteria:
            participation_weight = criteria['participation'].get('weight', 0)
            total_weighted_score += self.participation_score * participation_weight
            total_weight += participation_weight
        
        if total_weight > 0:
            self.final_grade = total_weighted_score / total_weight
            self.save(update_fields=['final_grade'])
        
        return self.final_grade

    def calculate_assignment_average(self):
        """Calculate average assignment score"""
        if not self.assignment_scores:
            return 0.0
        scores = list(self.assignment_scores.values())
        return sum(scores) / len(scores)

    def calculate_exam_average(self):
        """Calculate average exam score"""
        if not self.exam_scores:
            return 0.0
        scores = list(self.exam_scores.values())
        return sum(scores) / len(scores)


class CourseAssignment(TimeStampedModel, SoftDeleteModel, AuditModel, TenantModel):
    """
    Course assignments and assessments
    """
    ASSIGNMENT_TYPES = [
        ('homework', 'Homework'),
        ('quiz', 'Quiz'),
        ('exam', 'Exam'),
        ('project', 'Project'),
        ('presentation', 'Presentation'),
        ('lab_report', 'Lab Report'),
        ('essay', 'Essay'),
        ('other', 'Other'),
    ]

    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name='assignments'
    )
    title = models.CharField(max_length=200)
    description = models.TextField()
    assignment_type = models.CharField(max_length=20, choices=ASSIGNMENT_TYPES)
    
    # Dates
    assigned_date = models.DateTimeField(default=timezone.now)
    due_date = models.DateTimeField()
    submission_deadline = models.DateTimeField(null=True, blank=True)
    
    # Grading
    max_points = models.FloatField(validators=[MinValueValidator(0)])
    weight = models.FloatField(validators=[MinValueValidator(0), MaxValueValidator(100)], default=10.0)
    
    # Submission
    allow_late_submission = models.BooleanField(default=False)
    late_penalty_percentage = models.FloatField(default=0.0)
    max_attempts = models.IntegerField(default=1)
    
    # Materials
    instructions = models.FileField(upload_to='assignment_instructions/', blank=True)
    additional_materials = models.JSONField(default=list, blank=True)
    
    # Status
    is_published = models.BooleanField(default=False)
    is_graded = models.BooleanField(default=False)
    
    class Meta:
        db_table = 'courses_course_assignment'
        verbose_name = 'Course Assignment'
        verbose_name_plural = 'Course Assignments'
        indexes = [
            models.Index(fields=['course', 'due_date']),
            models.Index(fields=['assignment_type']),
            models.Index(fields=['is_published']),
        ]

    def __str__(self):
        return f"{self.title} - {self.course.code}"

    @property
    def is_overdue(self):
        """Check if assignment is overdue"""
        return timezone.now() > self.due_date

    @property
    def is_late_submission_allowed(self):
        """Check if late submission is allowed and within deadline"""
        return self.allow_late_submission and (
            not self.submission_deadline or timezone.now() <= self.submission_deadline
        )


class CourseSubmission(TimeStampedModel, AuditModel, TenantModel):
    """
    Student assignment submissions
    """
    assignment = models.ForeignKey(
        CourseAssignment,
        on_delete=models.CASCADE,
        related_name='submissions'
    )
    student = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='assignment_submissions',
        limit_choices_to={'role': 'student'}
    )
    
    # Submission Content
    text_content = models.TextField(blank=True)
    submitted_files = models.JSONField(default=list, blank=True)
    
    # Submission Details
    submitted_at = models.DateTimeField(default=timezone.now)
    is_late = models.BooleanField(default=False)
    attempt_number = models.IntegerField(default=1)
    
    # Grading
    score = models.FloatField(null=True, blank=True)
    max_points = models.FloatField(null=True, blank=True)
    feedback = models.TextField(blank=True)
    graded_at = models.DateTimeField(null=True, blank=True)
    graded_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='graded_submissions',
        limit_choices_to={'role': 'lecturer'}
    )
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=[
            ('draft', 'Draft'),
            ('submitted', 'Submitted'),
            ('graded', 'Graded'),
            ('returned', 'Returned'),
        ],
        default='draft'
    )
    
    class Meta:
        db_table = 'courses_course_submission'
        verbose_name = 'Course Submission'
        verbose_name_plural = 'Course Submissions'
        unique_together = ['assignment', 'student', 'attempt_number']
        indexes = [
            models.Index(fields=['assignment', 'student']),
            models.Index(fields=['student', 'status']),
            models.Index(fields=['submitted_at']),
            models.Index(fields=['is_late']),
        ]

    def __str__(self):
        return f"{self.student.get_full_name()} - {self.assignment.title}"

    def calculate_late_penalty(self):
        """Calculate late penalty if applicable"""
        if not self.is_late or self.assignment.late_penalty_percentage == 0:
            return 0.0
        
        hours_late = max(0, (self.submitted_at - self.assignment.due_date).total_seconds() / 3600)
        
        # Apply penalty based on hours late (can be customized)
        penalty_percentage = min(self.assignment.late_penalty_percentage, hours_late)
        return penalty_percentage

    def calculate_final_score(self):
        """Calculate final score after applying penalties"""
        if self.score is None:
            return None
        
        penalty = self.calculate_late_penalty()
        if penalty > 0:
            return self.score * (1 - penalty / 100)
        return self.score


class CourseMaterial(TimeStampedModel, SoftDeleteModel, AuditModel, TenantModel):
    """
    Course materials and resources
    """
    MATERIAL_TYPES = [
        ('lecture_notes', 'Lecture Notes'),
        ('textbook', 'Textbook'),
        ('reference', 'Reference'),
        ('video', 'Video'),
        ('audio', 'Audio'),
        ('presentation', 'Presentation'),
        ('document', 'Document'),
        ('link', 'External Link'),
        ('other', 'Other'),
    ]

    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name='materials'
    )
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    material_type = models.CharField(max_length=20, choices=MATERIAL_TYPES)
    
    # Content
    file = models.FileField(upload_to='course_materials/', blank=True)
    external_url = models.URLField(blank=True)
    content = models.TextField(blank=True)
    
    # Organization
    week_number = models.IntegerField(null=True, blank=True)
    order = models.IntegerField(default=0)
    tags = models.JSONField(default=list, blank=True)
    
    # Access Control
    is_public = models.BooleanField(default=True)
    access_date = models.DateTimeField(null=True, blank=True)
    download_allowed = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'courses_course_material'
        verbose_name = 'Course Material'
        verbose_name_plural = 'Course Materials'
        indexes = [
            models.Index(fields=['course', 'week_number', 'order']),
            models.Index(fields=['material_type']),
            models.Index(fields=['is_public']),
        ]

    def __str__(self):
        return f"{self.title} - {self.course.code}"


class CourseAnnouncement(TimeStampedModel, SoftDeleteModel, AuditModel, TenantModel):
    """
    Course-specific announcements
    """
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ]

    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name='announcements'
    )
    title = models.CharField(max_length=200)
    content = models.TextField()
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='medium')
    
    # Scheduling
    publish_at = models.DateTimeField(default=timezone.now)
    expire_at = models.DateTimeField(null=True, blank=True)
    
    # Targeting
    target_all_students = models.BooleanField(default=True)
    target_students = models.ManyToManyField(
        User,
        blank=True,
        related_name='course_announcements',
        limit_choices_to={'role': 'student'}
    )
    
    # Engagement
    view_count = models.IntegerField(default=0)
    acknowledgment_required = models.BooleanField(default=False)
    
    class Meta:
        db_table = 'courses_course_announcement'
        verbose_name = 'Course Announcement'
        verbose_name_plural = 'Course Announcements'
        indexes = [
            models.Index(fields=['course', 'publish_at']),
            models.Index(fields=['priority']),
            models.Index(fields=['is_active']),
        ]

    def __str__(self):
        return f"{self.title} - {self.course.code}"
