"""
Surveys models for Attendrix - Survey and feedback engine
"""
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from django.core.exceptions import ValidationError
from apps.core.models import TimeStampedModel, SoftDeleteModel, AuditModel, TenantModel
from apps.institutions.models import Institution
from apps.users.models import User
from apps.departments.models import Department
from apps.courses.models import Course
import uuid


class Survey(TimeStampedModel, SoftDeleteModel, AuditModel, TenantModel):
    """
    Survey management
    """
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('paused', 'Paused'),
        ('completed', 'Completed'),
        ('archived', 'Archived'),
    ]

    VISIBILITY_CHOICES = [
        ('public', 'Public'),
        ('private', 'Private'),
        ('restricted', 'Restricted'),
    ]

    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    instructions = models.TextField(blank=True)
    
    # Survey Settings
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    visibility = models.CharField(max_length=20, choices=VISIBILITY_CHOICES, default='private')
    
    # Timing
    start_date = models.DateTimeField(null=True, blank=True)
    end_date = models.DateTimeField(null=True, blank=True)
    estimated_duration = models.IntegerField(
        help_text="Estimated completion time in minutes",
        validators=[MinValueValidator(1), MaxValueValidator(300)],
        default=10
    )
    
    # Response Settings
    max_responses = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1)]
    )
    allow_multiple_responses = models.BooleanField(default=False)
    require_authentication = models.BooleanField(default=True)
    anonymous_responses = models.BooleanField(default=False)
    show_results_to_respondents = models.BooleanField(default=False)
    
    # Targeting
    target_roles = models.JSONField(default=list)  # List of roles
    target_users = models.ManyToManyField(
        User,
        blank=True,
        related_name='targeted_surveys'
    )
    target_departments = models.ManyToManyField(
        Department,
        blank=True,
        related_name='targeted_surveys'
    )
    target_courses = models.ManyToManyField(
        Course,
        blank=True,
        related_name='targeted_surveys'
    )
    
    # Completion Settings
    is_required = models.BooleanField(default=False)
    completion_message = models.TextField(blank=True)
    redirect_url = models.URLField(blank=True)
    
    # Statistics
    total_responses = models.IntegerField(default=0)
    completed_responses = models.IntegerField(default=0)
    completion_rate = models.FloatField(default=0.0)
    
    class Meta:
        db_table = 'surveys_survey'
        verbose_name = 'Survey'
        verbose_name_plural = 'Surveys'
        indexes = [
            models.Index(fields=['institution', 'status']),
            models.Index(fields=['start_date', 'end_date']),
            models.Index(fields=['visibility']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f"{self.title} - {self.status}"

    def save(self, *args, **kwargs):
        # Calculate completion rate
        if self.total_responses > 0:
            self.completion_rate = (self.completed_responses / self.total_responses) * 100
        super().save(*args, **kwargs)

    def is_active(self):
        """Check if survey is currently active"""
        return (
            self.status == 'active' and
            self.start_date and
            self.start_date <= timezone.now() and
            (not self.end_date or self.end_date >= timezone.now())
        )

    def can_respond(self, user):
        """Check if user can respond to this survey"""
        if not self.is_active():
            return False, "Survey is not active"
        
        if self.require_authentication and not user.is_authenticated:
            return False, "Authentication required"
        
        if self.max_responses and self.total_responses >= self.max_responses:
            return False, "Maximum responses reached"
        
        if not self.allow_multiple_responses:
            # Check if user has already responded
            if SurveyResponse.objects.filter(
                survey=self,
                user=user,
                is_completed=True
            ).exists():
                return False, "You have already completed this survey"
        
        # Check targeting
        if self.target_roles and user.role not in self.target_roles:
            return False, "You are not in the target audience"
        
        if self.target_users.exists() and user not in self.target_users.all():
            return False, "You are not in the target audience"
        
        if self.target_departments.exists():
            user_departments = user.departments.all()
            if not any(dept in self.target_departments.all() for dept in user_departments):
                return False, "Your department is not targeted"
        
        if self.target_courses.exists():
            user_courses = user.courseenrollments.filter(status='enrolled').values_list('course', flat=True)
            if not any(course in self.target_courses.all() for course in user_courses):
                return False, "Your courses are not targeted"
        
        return True, "You can respond to this survey"


class SurveyQuestion(TimeStampedModel, SoftDeleteModel, AuditModel, TenantModel):
    """
    Survey questions
    """
    QUESTION_TYPES = [
        ('text', 'Text'),
        ('textarea', 'Paragraph'),
        ('choice', 'Multiple Choice'),
        ('checkbox', 'Checkboxes'),
        ('dropdown', 'Dropdown'),
        ('rating', 'Rating'),
        ('scale', 'Scale'),
        ('matrix', 'Matrix'),
        ('date', 'Date'),
        ('time', 'Time'),
        ('datetime', 'Date & Time'),
        ('number', 'Number'),
        ('email', 'Email'),
        ('url', 'URL'),
        ('phone', 'Phone'),
        ('file', 'File Upload'),
        ('image', 'Image'),
        ('video', 'Video'),
        ('signature', 'Signature'),
    ]

    survey = models.ForeignKey(
        Survey,
        on_delete=models.CASCADE,
        related_name='questions'
    )
    
    question_text = models.TextField()
    question_type = models.CharField(max_length=20, choices=QUESTION_TYPES)
    help_text = models.TextField(blank=True)
    
    # Question Settings
    is_required = models.BooleanField(default=True)
    is_randomizable = models.BooleanField(default=False)
    show_on_same_page = models.BooleanField(default=True)
    
    # Order
    order = models.IntegerField(default=0)
    page_number = models.IntegerField(default=1)
    
    # Validation
    min_length = models.IntegerField(null=True, blank=True)
    max_length = models.IntegerField(null=True, blank=True)
    min_value = models.FloatField(null=True, blank=True)
    max_value = models.FloatField(null=True, blank=True)
    pattern = models.CharField(max_length=200, blank=True)  # Regex pattern
    
    # Choice Options (for choice, checkbox, dropdown)
    choices = models.JSONField(default=list)
    allow_other_option = models.BooleanField(default=False)
    other_option_label = models.CharField(max_length=100, default='Other')
    
    # Rating/Scale Settings
    rating_min = models.IntegerField(default=1)
    rating_max = models.IntegerField(default=5)
    rating_labels = models.JSONField(default=dict)  # {1: "Poor", 5: "Excellent"}
    
    # Matrix Settings
    matrix_rows = models.JSONField(default=list)
    matrix_columns = models.JSONField(default=list)
    
    # File Settings
    max_file_size = models.IntegerField(default=10485760)  # 10MB in bytes
    allowed_file_types = models.JSONField(default=list)  # MIME types
    
    class Meta:
        db_table = 'surveys_survey_question'
        verbose_name = 'Survey Question'
        verbose_name_plural = 'Survey Questions'
        indexes = [
            models.Index(fields=['survey', 'order']),
            models.Index(fields=['question_type']),
            models.Index(fields=['is_required']),
        ]

    def __str__(self):
        return f"{self.survey.title} - Q{self.order}: {self.question_text[:50]}"

    def clean(self):
        """Validate question configuration"""
        if self.question_type in ['choice', 'checkbox', 'dropdown'] and not self.choices:
            raise ValidationError("Choices are required for this question type")
        
        if self.question_type == 'rating' and self.rating_min >= self.rating_max:
            raise ValidationError("Rating minimum must be less than maximum")
        
        if self.question_type == 'matrix' and (not self.matrix_rows or not self.matrix_columns):
            raise ValidationError("Matrix rows and columns are required")

    def validate_response(self, value):
        """Validate response value"""
        if self.is_required and (value is None or value == ''):
            raise ValidationError("This field is required")
        
        if value is None or value == '':
            return True
        
        # Length validation
        if self.question_type in ['text', 'textarea']:
            if self.min_length and len(value) < self.min_length:
                raise ValidationError(f"Minimum length is {self.min_length} characters")
            if self.max_length and len(value) > self.max_length:
                raise ValidationError(f"Maximum length is {self.max_length} characters")
        
        # Numeric validation
        if self.question_type in ['number', 'rating', 'scale']:
            try:
                num_value = float(value)
                if self.min_value is not None and num_value < self.min_value:
                    raise ValidationError(f"Minimum value is {self.min_value}")
                if self.max_value is not None and num_value > self.max_value:
                    raise ValidationError(f"Maximum value is {self.max_value}")
            except (ValueError, TypeError):
                raise ValidationError("Invalid number format")
        
        # Choice validation
        if self.question_type in ['choice', 'dropdown']:
            if value not in [choice['value'] for choice in self.choices]:
                raise ValidationError("Invalid choice")
        
        # Checkbox validation
        if self.question_type == 'checkbox':
            if not isinstance(value, list):
                raise ValidationError("Checkbox response must be a list")
            valid_choices = [choice['value'] for choice in self.choices]
            if self.allow_other_option:
                valid_choices.append('other')
            for choice_value in value:
                if choice_value not in valid_choices:
                    raise ValidationError(f"Invalid choice: {choice_value}")
        
        # Email validation
        if self.question_type == 'email':
            import re
            email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            if not re.match(email_pattern, value):
                raise ValidationError("Invalid email format")
        
        # URL validation
        if self.question_type == 'url':
            import re
            url_pattern = r'^https?://(?:[-\w.])+(?:[:\d]+)?(?:/(?:[\w/_.])*(?:\?(?:[\w&=%.])*)?(?:#(?:\w*))?$'
            if not re.match(url_pattern, value):
                raise ValidationError("Invalid URL format")
        
        return True


class SurveyResponse(TimeStampedModel, SoftDeleteModel, AuditModel, TenantModel):
    """
    Survey responses
    """
    STATUS_CHOICES = [
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('abandoned', 'Abandoned'),
    ]

    survey = models.ForeignKey(
        Survey,
        on_delete=models.CASCADE,
        related_name='responses'
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='survey_responses',
        null=True,
        blank=True
    )
    
    # Response Information
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='in_progress')
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    last_activity = models.DateTimeField(auto_now=True)
    
    # Progress
    current_page = models.IntegerField(default=1)
    total_pages = models.IntegerField(default=1)
    progress_percentage = models.FloatField(default=0.0)
    
    # Metadata
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    session_key = models.CharField(max_length=40, blank=True)
    device_fingerprint = models.CharField(max_length=255, blank=True)
    
    # Anonymous Response
    is_anonymous = models.BooleanField(default=False)
    anonymous_id = models.CharField(max_length=100, blank=True)
    
    class Meta:
        db_table = 'surveys_survey_response'
        verbose_name = 'Survey Response'
        verbose_name_plural = 'Survey Responses'
        indexes = [
            models.Index(fields=['survey', 'status']),
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['created_at']),
            models.Index(fields=['completed_at']),
        ]

    def __str__(self):
        if self.user:
            return f"{self.survey.title} - {self.user.get_full_name()}"
        else:
            return f"{self.survey.title} - Anonymous"

    def save(self, *args, **kwargs):
        # Update progress percentage
        if self.total_pages > 0:
            self.progress_percentage = (self.current_page / self.total_pages) * 100
        
        # Update completion status
        if self.status == 'completed' and not self.completed_at:
            self.completed_at = timezone.now()
        
        super().save(*args, **kwargs)

    def complete(self):
        """Mark response as completed"""
        self.status = 'completed'
        self.completed_at = timezone.now()
        self.current_page = self.total_pages
        self.progress_percentage = 100.0
        self.save()
        
        # Update survey statistics
        self.survey.completed_responses += 1
        self.survey.save()

    def get_answer(self, question_id):
        """Get answer for a specific question"""
        try:
            return self.answers.get(question_id=question_id)
        except SurveyAnswer.DoesNotExist:
            return None

    def set_answer(self, question, value):
        """Set answer for a question"""
        # Validate the answer
        question.validate_response(value)
        
        # Create or update answer
        answer, created = SurveyAnswer.objects.update_or_create(
            response=self,
            question=question,
            defaults={'value': str(value)}
        )
        
        return answer


class SurveyAnswer(TimeStampedModel, SoftDeleteModel, TenantModel):
    """
    Individual survey answers
    """
    response = models.ForeignKey(
        SurveyResponse,
        on_delete=models.CASCADE,
        related_name='answers'
    )
    question = models.ForeignKey(
        SurveyQuestion,
        on_delete=models.CASCADE,
        related_name='answers'
    )
    
    value = models.TextField()
    
    # For file uploads
    file = models.FileField(
        upload_to='survey_files/',
        null=True,
        blank=True
    )
    
    class Meta:
        db_table = 'surveys_survey_answer'
        verbose_name = 'Survey Answer'
        verbose_name_plural = 'Survey Answers'
        unique_together = ['response', 'question']
        indexes = [
            models.Index(fields=['response', 'question']),
        ]

    def __str__(self):
        return f"{self.response} - {self.question}"

    def get_display_value(self):
        """Get formatted display value"""
        if self.question.question_type == 'choice':
            choices = {choice['value']: choice['label'] for choice in self.question.choices}
            return choices.get(self.value, self.value)
        
        elif self.question.question_type == 'checkbox':
            if self.value.startswith('[') and self.value.endswith(']'):
                import json
                values = json.loads(self.value)
                choices = {choice['value']: choice['label'] for choice in self.question.choices}
                return ', '.join([choices.get(v, v) for v in values])
            return self.value
        
        elif self.question.question_type == 'rating':
            labels = self.question.rating_labels
            return labels.get(int(self.value), f"Rating: {self.value}")
        
        return self.value


class SurveyTemplate(TimeStampedModel, SoftDeleteModel, AuditModel, TenantModel):
    """
    Survey templates for quick creation
    """
    TEMPLATE_TYPES = [
        ('course_evaluation', 'Course Evaluation'),
        ('instructor_feedback', 'Instructor Feedback'),
        ('student_satisfaction', 'Student Satisfaction'),
        ('institutional_survey', 'Institutional Survey'),
        ('department_feedback', 'Department Feedback'),
        ('exit_survey', 'Exit Survey'),
        ('custom', 'Custom'),
    ]

    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    template_type = models.CharField(max_length=30, choices=TEMPLATE_TYPES)
    
    # Template Content
    survey_structure = models.JSONField(default=dict)  # Complete survey structure
    questions = models.JSONField(default=list)  # List of question definitions
    
    # Settings
    is_public = models.BooleanField(default=False)
    is_default = models.BooleanField(default=False)
    
    # Usage Tracking
    usage_count = models.IntegerField(default=0)
    last_used = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'surveys_survey_template'
        verbose_name = 'Survey Template'
        verbose_name_plural = 'Survey Templates'
        unique_together = ['institution', 'name']
        indexes = [
            models.Index(fields=['template_type']),
            models.Index(fields=['is_public']),
            models.Index(fields=['is_default']),
        ]

    def __str__(self):
        return f"{self.name} - {self.template_type}"

    def create_survey(self, title=None, **kwargs):
        """Create a new survey from this template"""
        survey_data = {
            'title': title or self.name,
            'description': self.description,
            'instructions': self.survey_structure.get('instructions', ''),
            'estimated_duration': self.survey_structure.get('estimated_duration', 10),
            'anonymous_responses': self.survey_structure.get('anonymous_responses', False),
            'require_authentication': self.survey_structure.get('require_authentication', True),
            **kwargs
        }
        
        survey = Survey.objects.create(
            institution=self.institution,
            **survey_data
        )
        
        # Create questions from template
        for i, question_data in enumerate(self.questions):
            SurveyQuestion.objects.create(
                survey=survey,
                question_text=question_data['question_text'],
                question_type=question_data['question_type'],
                help_text=question_data.get('help_text', ''),
                is_required=question_data.get('is_required', True),
                order=i + 1,
                **{k: v for k, v in question_data.items() if k not in ['question_text', 'question_type', 'help_text', 'is_required']}
            )
        
        return survey


class SurveyAnalytics(TimeStampedModel, TenantModel):
    """
    Survey analytics and statistics
    """
    ANALYTICS_TYPES = [
        ('response_rate', 'Response Rate'),
        ('completion_rate', 'Completion Rate'),
        ('question_analytics', 'Question Analytics'),
        ('demographic_analytics', 'Demographic Analytics'),
        ('trend_analytics', 'Trend Analytics'),
        ('sentiment_analysis', 'Sentiment Analysis'),
    ]

    survey = models.ForeignKey(
        Survey,
        on_delete=models.CASCADE,
        related_name='analytics'
    )
    analytics_type = models.CharField(max_length=30, choices=ANALYTICS_TYPES)
    reference_date = models.DateField()
    
    # Analytics Data
    total_responses = models.IntegerField(default=0)
    completed_responses = models.IntegerField(default=0)
    response_rate = models.FloatField(default=0.0)
    completion_rate = models.FloatField(default=0.0)
    average_completion_time = models.FloatField(default=0.0)  # in minutes
    
    # Question-specific data
    question_data = models.JSONField(default=dict)  # Per-question statistics
    
    # Demographic data
    demographic_data = models.JSONField(default=dict)  # By role, department, course
    
    # Trend data
    trend_data = models.JSONField(default=dict)  # Time-based trends
    
    # Sentiment data
    sentiment_data = models.JSONField(default=dict)  # Sentiment scores
    
    # Additional metadata
    metadata = models.JSONField(default=dict)
    
    class Meta:
        db_table = 'surveys_survey_analytics'
        verbose_name = 'Survey Analytics'
        verbose_name_plural = 'Survey Analytics'
        unique_together = ['survey', 'analytics_type', 'reference_date']
        indexes = [
            models.Index(fields=['survey', 'analytics_type']),
            models.Index(fields=['reference_date']),
        ]

    def __str__(self):
        return f"{self.survey.title} - {self.analytics_type} - {self.reference_date}"

    def calculate_response_rate(self):
        """Calculate response rate"""
        if self.survey.target_users.exists():
            potential_respondents = self.survey.target_users.count()
        else:
            # Estimate based on target roles
            from apps.users.models import User
            potential_respondents = User.objects.filter(
                institution=self.survey.institution,
                role__in=self.survey.target_roles
            ).count()
        
        if potential_respondents > 0:
            self.response_rate = (self.total_responses / potential_respondents) * 100
        
        self.save()

    def calculate_completion_rate(self):
        """Calculate completion rate"""
        if self.total_responses > 0:
            self.completion_rate = (self.completed_responses / self.total_responses) * 100
        
        self.save()


class SurveyInvitation(TimeStampedModel, TenantModel):
    """
    Survey invitations for targeted users
    """
    STATUS_CHOICES = [
        ('sent', 'Sent'),
        ('opened', 'Opened'),
        ('started', 'Started'),
        ('completed', 'Completed'),
        ('expired', 'Expired'),
        ('bounced', 'Bounced'),
    ]

    survey = models.ForeignKey(
        Survey,
        on_delete=models.CASCADE,
        related_name='invitations'
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='survey_invitations'
    )
    
    # Invitation Details
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='sent')
    invitation_token = models.CharField(max_length=64, unique=True)
    
    # Timing
    sent_at = models.DateTimeField(auto_now_add=True)
    opened_at = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    
    # Personalization
    personal_message = models.TextField(blank=True)
    sender_name = models.CharField(max_length=100, blank=True)
    
    # Tracking
    email_opened = models.BooleanField(default=False)
    link_clicked = models.BooleanField(default=False)
    reminders_sent = models.IntegerField(default=0)
    
    class Meta:
        db_table = 'surveys_survey_invitation'
        verbose_name = 'Survey Invitation'
        verbose_name_plural = 'Survey Invitations'
        unique_together = ['survey', 'user']
        indexes = [
            models.Index(fields=['survey', 'status']),
            models.Index(fields=['user']),
            models.Index(fields=['sent_at']),
            models.Index(fields=['expires_at']),
        ]

    def __str__(self):
        return f"{self.survey.title} - {self.user.get_full_name()}"

    def generate_token(self):
        """Generate unique invitation token"""
        import secrets
        self.invitation_token = secrets.token_urlsafe(48)
        self.save()

    def is_expired(self):
        """Check if invitation has expired"""
        return self.expires_at and self.expires_at < timezone.now()

    def mark_opened(self):
        """Mark invitation as opened"""
        if not self.email_opened:
            self.email_opened = True
            self.opened_at = timezone.now()
            self.status = 'opened'
            self.save()

    def mark_started(self):
        """Mark invitation as started"""
        if self.status not in ['started', 'completed']:
            self.link_clicked = True
            self.started_at = timezone.now()
            self.status = 'started'
            self.save()

    def mark_completed(self):
        """Mark invitation as completed"""
        self.completed_at = timezone.now()
        self.status = 'completed'
        self.save()


class SurveyNotification(TimeStampedModel, TenantModel):
    """
    Survey notifications and reminders
    """
    NOTIFICATION_TYPES = [
        ('invitation', 'Invitation'),
        ('reminder', 'Reminder'),
        ('completion', 'Completion'),
        ('deadline', 'Deadline'),
        ('thank_you', 'Thank You'),
    ]

    survey = models.ForeignKey(
        Survey,
        on_delete=models.CASCADE,
        related_name='notifications'
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='survey_notifications'
    )
    
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES)
    title = models.CharField(max_length=200)
    message = models.TextField()
    
    # Delivery Status
    email_sent = models.BooleanField(default=False)
    sms_sent = models.BooleanField(default=False)
    push_sent = models.BooleanField(default=False)
    in_app_read = models.BooleanField(default=False)
    
    # Timing
    scheduled_at = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'surveys_survey_notification'
        verbose_name = 'Survey Notification'
        verbose_name_plural = 'Survey Notifications'
        indexes = [
            models.Index(fields=['survey', 'notification_type']),
            models.Index(fields=['user']),
            models.Index(fields=['scheduled_at']),
            models.Index(fields=['sent_at']),
        ]

    def __str__(self):
        return f"{self.survey.title} - {self.notification_type} - {self.user.get_full_name()}"
