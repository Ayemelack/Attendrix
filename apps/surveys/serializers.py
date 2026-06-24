"""
Surveys serializers for Attendrix API
"""
from rest_framework import serializers
from django.utils import timezone
from apps.surveys.models import (
    Survey, SurveyQuestion, SurveyResponse, SurveyAnswer,
    SurveyTemplate, SurveyAnalytics, SurveyInvitation, SurveyNotification
)
from apps.users.serializers import UserSerializer
from apps.departments.serializers import DepartmentSerializer
from apps.courses.serializers import CourseSerializer


class SurveySerializer(serializers.ModelSerializer):
    """
    Survey serializer
    """
    created_by_info = UserSerializer(source='created_by', read_only=True)
    updated_by_info = UserSerializer(source='updated_by', read_only=True)
    target_users_info = UserSerializer(source='target_users', many=True, read_only=True)
    target_departments_info = DepartmentSerializer(source='target_departments', many=True, read_only=True)
    target_courses_info = CourseSerializer(source='target_courses', many=True, read_only=True)
    
    class Meta:
        model = Survey
        fields = [
            'id', 'title', 'description', 'instructions', 'status', 'visibility',
            'start_date', 'end_date', 'estimated_duration', 'max_responses',
            'allow_multiple_responses', 'require_authentication', 'anonymous_responses',
            'show_results_to_respondents', 'target_roles', 'target_users', 'target_users_info',
            'target_departments', 'target_departments_info', 'target_courses', 'target_courses_info',
            'is_required', 'completion_message', 'redirect_url',
            'total_responses', 'completed_responses', 'completion_rate',
            'created_by_info', 'updated_by_info',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'total_responses', 'completed_responses', 'completion_rate',
            'created_at', 'updated_at'
        ]

    def validate(self, attrs):
        """Validate survey data"""
        start_date = attrs.get('start_date')
        end_date = attrs.get('end_date')
        
        if start_date and end_date:
            if start_date > end_date:
                raise serializers.ValidationError("Start date cannot be after end date")
        
        # Validate max_responses
        max_responses = attrs.get('max_responses')
        if max_responses and max_responses <= 0:
            raise serializers.ValidationError("Max responses must be greater than 0")
        
        return attrs

    def create(self, validated_data):
        """Create survey with validation"""
        survey = super().create(validated_data)
        
        # Log creation
        from apps.core.models import ActivityLog
        ActivityLog.objects.create(
            user=self.context['request'].user,
            institution=survey.institution,
            action_type='create',
            action_description=f'Survey created: {survey.title}',
            severity='medium'
        )
        
        return survey


class SurveyQuestionSerializer(serializers.ModelSerializer):
    """
    Survey question serializer
    """
    class Meta:
        model = SurveyQuestion
        fields = [
            'id', 'survey', 'question_text', 'question_type', 'help_text',
            'is_required', 'is_randomizable', 'show_on_same_page',
            'order', 'page_number',
            'min_length', 'max_length', 'min_value', 'max_value', 'pattern',
            'choices', 'allow_other_option', 'other_option_label',
            'rating_min', 'rating_max', 'rating_labels',
            'matrix_rows', 'matrix_columns',
            'max_file_size', 'allowed_file_types',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']

    def validate(self, attrs):
        """Validate question configuration"""
        question_type = attrs.get('question_type')
        choices = attrs.get('choices', [])
        
        if question_type in ['choice', 'checkbox', 'dropdown'] and not choices:
            raise serializers.ValidationError("Choices are required for this question type")
        
        if question_type == 'rating':
            rating_min = attrs.get('rating_min', 1)
            rating_max = attrs.get('rating_max', 5)
            if rating_min >= rating_max:
                raise serializers.ValidationError("Rating minimum must be less than maximum")
        
        if question_type == 'matrix':
            matrix_rows = attrs.get('matrix_rows', [])
            matrix_columns = attrs.get('matrix_columns', [])
            if not matrix_rows or not matrix_columns:
                raise serializers.ValidationError("Matrix rows and columns are required")
        
        return attrs


class SurveyAnswerSerializer(serializers.ModelSerializer):
    """
    Survey answer serializer
    """
    question_info = SurveyQuestionSerializer(source='question', read_only=True)
    
    class Meta:
        model = SurveyAnswer
        fields = [
            'id', 'response', 'question', 'question_info', 'value', 'file',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']

    def get_display_value(self, obj):
        """Get display value for the answer"""
        return obj.get_display_value()


class SurveyResponseSerializer(serializers.ModelSerializer):
    """
    Survey response serializer
    """
    user_info = UserSerializer(source='user', read_only=True)
    survey_info = SurveySerializer(source='survey', read_only=True)
    answers = SurveyAnswerSerializer(source='answers', many=True, read_only=True)
    
    class Meta:
        model = SurveyResponse
        fields = [
            'id', 'survey', 'survey_info', 'user', 'user_info', 'status',
            'started_at', 'completed_at', 'last_activity',
            'current_page', 'total_pages', 'progress_percentage',
            'ip_address', 'user_agent', 'session_key', 'device_fingerprint',
            'is_anonymous', 'anonymous_id', 'answers',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'started_at', 'completed_at', 'last_activity',
            'progress_percentage', 'created_at', 'updated_at'
        ]

    def create(self, validated_data):
        """Create survey response"""
        user = self.context['request'].user
        survey = validated_data['survey']
        
        # Check if user can respond
        can_respond, message = survey.can_respond(user)
        if not can_respond:
            raise serializers.ValidationError(message)
        
        # Create response
        response = super().create(validated_data)
        
        # Update survey statistics
        survey.total_responses += 1
        survey.save()
        
        return response

    def update(self, instance, validated_data):
        """Update survey response"""
        old_status = instance.status
        response = super().update(instance, validated_data)
        
        # Handle completion
        if old_status != 'completed' and response.status == 'completed':
            response.complete()
        
        return response


class SurveyTemplateSerializer(serializers.ModelSerializer):
    """
    Survey template serializer
    """
    class Meta:
        model = SurveyTemplate
        fields = [
            'id', 'name', 'description', 'template_type',
            'survey_structure', 'questions',
            'is_public', 'is_default',
            'usage_count', 'last_used',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['usage_count', 'last_used', 'created_at', 'updated_at']

    def create_survey(self, validated_data):
        """Create survey from template"""
        template = self.instance
        title = validated_data.get('title')
        
        survey = template.create_survey(title, **validated_data)
        
        # Update usage statistics
        template.usage_count += 1
        template.last_used = timezone.now()
        template.save()
        
        return survey


class SurveyAnalyticsSerializer(serializers.ModelSerializer):
    """
    Survey analytics serializer
    """
    survey_info = SurveySerializer(source='survey', read_only=True)
    
    class Meta:
        model = SurveyAnalytics
        fields = [
            'id', 'survey', 'survey_info', 'analytics_type', 'reference_date',
            'total_responses', 'completed_responses', 'response_rate', 'completion_rate',
            'average_completion_time', 'question_data', 'demographic_data',
            'trend_data', 'sentiment_data', 'metadata',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'total_responses', 'completed_responses', 'response_rate', 'completion_rate',
            'average_completion_time', 'created_at', 'updated_at'
        ]


class SurveyInvitationSerializer(serializers.ModelSerializer):
    """
    Survey invitation serializer
    """
    survey_info = SurveySerializer(source='survey', read_only=True)
    user_info = UserSerializer(source='user', read_only=True)
    
    class Meta:
        model = SurveyInvitation
        fields = [
            'id', 'survey', 'survey_info', 'user', 'user_info', 'status',
            'invitation_token', 'sent_at', 'opened_at', 'started_at', 'completed_at',
            'expires_at', 'personal_message', 'sender_name',
            'email_opened', 'link_clicked', 'reminders_sent',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'invitation_token', 'sent_at', 'opened_at', 'started_at', 'completed_at',
            'email_opened', 'link_clicked', 'reminders_sent', 'created_at', 'updated_at'
        ]

    def create(self, validated_data):
        """Create survey invitation"""
        invitation = super().create(validated_data)
        
        # Generate unique token
        invitation.generate_token()
        
        # Set expiration if not provided
        if not invitation.expires_at and invitation.survey.end_date:
            invitation.expires_at = invitation.survey.end_date
        elif not invitation.expires_at:
            # Default to 30 days from now
            invitation.expires_at = timezone.now() + timedelta(days=30)
            invitation.save()
        
        return invitation


class SurveyNotificationSerializer(serializers.ModelSerializer):
    """
    Survey notification serializer
    """
    survey_info = SurveySerializer(source='survey', read_only=True)
    user_info = UserSerializer(source='user', read_only=True)
    
    class Meta:
        model = SurveyNotification
        fields = [
            'id', 'survey', 'survey_info', 'user', 'user_info',
            'notification_type', 'title', 'message',
            'email_sent', 'sms_sent', 'push_sent', 'in_app_read',
            'scheduled_at', 'sent_at', 'read_at',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'email_sent', 'sms_sent', 'push_sent', 'in_app_read',
            'sent_at', 'read_at', 'created_at', 'updated_at'
        ]


class SurveyCreateFromTemplateSerializer(serializers.Serializer):
    """
    Create survey from template serializer
    """
    template_id = serializers.UUIDField()
    title = serializers.CharField(max_length=200)
    description = serializers.CharField(required=False, allow_blank=True)
    start_date = serializers.DateTimeField(required=False)
    end_date = serializers.DateTimeField(required=False)
    target_roles = serializers.ListField(
        child=serializers.CharField(),
        required=False
    )
    target_users = serializers.ListField(
        child=serializers.UUIDField(),
        required=False
    )
    target_departments = serializers.ListField(
        child=serializers.UUIDField(),
        required=False
    )
    target_courses = serializers.ListField(
        child=serializers.UUIDField(),
        required=False
    )
    
    def validate(self, attrs):
        """Validate survey creation parameters"""
        start_date = attrs.get('start_date')
        end_date = attrs.get('end_date')
        
        if start_date and end_date:
            if start_date > end_date:
                raise serializers.ValidationError("Start date cannot be after end date")
        
        return attrs


class SurveyResponseSubmissionSerializer(serializers.Serializer):
    """
    Survey response submission serializer
    """
    response_id = serializers.UUIDField(required=False)
    answers = serializers.JSONField()
    is_completed = serializers.BooleanField(default=False)
    
    def validate(self, attrs):
        """Validate response submission"""
        answers = attrs.get('answers', {})
        
        if not answers:
            raise serializers.ValidationError("At least one answer is required")
        
        return attrs


class SurveyQuestionResponseSerializer(serializers.Serializer):
    """
    Individual question response serializer
    """
    question_id = serializers.UUIDField()
    value = serializers.JSONField()
    
    def validate(self, attrs):
        """Validate question response"""
        question_id = attrs.get('question_id')
        value = attrs.get('value')
        
        if not question_id:
            raise serializers.ValidationError("Question ID is required")
        
        if value is None:
            raise serializers.ValidationError("Answer value is required")
        
        return attrs


class BulkSurveyInvitationSerializer(serializers.Serializer):
    """
    Bulk survey invitation serializer
    """
    survey_id = serializers.UUIDField()
    user_ids = serializers.ListField(child=serializers.UUIDField())
    personal_message = serializers.CharField(required=False, allow_blank=True)
    sender_name = serializers.CharField(required=False, allow_blank=True)
    expires_at = serializers.DateTimeField(required=False)
    
    def validate(self, attrs):
        """Validate bulk invitation parameters"""
        survey_id = attrs.get('survey_id')
        user_ids = attrs.get('user_ids', [])
        
        if not user_ids:
            raise serializers.ValidationError("At least one user ID is required")
        
        return attrs


class SurveyAnalyticsRequestSerializer(serializers.Serializer):
    """
    Survey analytics request serializer
    """
    survey_id = serializers.UUIDField()
    analytics_types = serializers.ListField(
        child=serializers.ChoiceField(choices=[
            ('response_rate', 'Response Rate'),
            ('completion_rate', 'Completion Rate'),
            ('question_analytics', 'Question Analytics'),
            ('demographic_analytics', 'Demographic Analytics'),
            ('trend_analytics', 'Trend Analytics'),
            ('sentiment_analysis', 'Sentiment Analysis'),
        ]),
        default=['response_rate', 'completion_rate']
    )
    start_date = serializers.DateField(required=False)
    end_date = serializers.DateField(required=False)
    
    def validate(self, attrs):
        """Validate analytics request parameters"""
        start_date = attrs.get('start_date')
        end_date = attrs.get('end_date')
        
        if start_date and end_date:
            if start_date > end_date:
                raise serializers.ValidationError("Start date cannot be after end date")
        
        return attrs


class SurveyReportSerializer(serializers.Serializer):
    """
    Survey report serializer
    """
    survey_id = serializers.UUIDField()
    report_type = serializers.ChoiceField(choices=[
        ('summary', 'Summary Report'),
        ('responses', 'Response Report'),
        ('analytics', 'Analytics Report'),
        ('demographics', 'Demographics Report'),
        ('questions', 'Question Report'),
        ('export', 'Data Export'),
    ])
    
    # Filters
    start_date = serializers.DateField(required=False)
    end_date = serializers.DateField(required=False)
    status = serializers.ChoiceField(
        choices=['all', 'completed', 'in_progress', 'abandoned'],
        default='all',
        required=False
    )
    
    # Export options
    format = serializers.ChoiceField(choices=['json', 'csv', 'pdf', 'excel'], default='json')
    include_answers = serializers.BooleanField(default=True)
    include_analytics = serializers.BooleanField(default=True)
    
    def validate(self, attrs):
        """Validate report parameters"""
        start_date = attrs.get('start_date')
        end_date = attrs.get('end_date')
        
        if start_date and end_date:
            if start_date > end_date:
                raise serializers.ValidationError("Start date cannot be after end date")
        
        return attrs


class SurveyCopySerializer(serializers.Serializer):
    """
    Survey copy serializer
    """
    title = serializers.CharField(max_length=200)
    description = serializers.CharField(required=False, allow_blank=True)
    copy_questions = serializers.BooleanField(default=True)
    copy_targeting = serializers.BooleanField(default=False)
    copy_settings = serializers.BooleanField(default=True)
    
    def validate(self, attrs):
        """Validate copy parameters"""
        title = attrs.get('title')
        
        if not title:
            raise serializers.ValidationError("Title is required")
        
        return attrs


class SurveySearchSerializer(serializers.Serializer):
    """
    Survey search serializer
    """
    query = serializers.CharField(max_length=100)
    status = serializers.ChoiceField(
        choices=['all', 'draft', 'active', 'paused', 'completed', 'archived'],
        default='all',
        required=False
    )
    template_type = serializers.CharField(required=False)
    created_by = serializers.UUIDField(required=False)
    target_role = serializers.CharField(required=False)
    
    # Pagination
    page = serializers.IntegerField(default=1)
    page_size = serializers.IntegerField(default=20)
    
    def validate(self, attrs):
        """Validate search parameters"""
        page = attrs.get('page', 1)
        page_size = attrs.get('page_size', 20)
        
        if page < 1:
            raise serializers.ValidationError("Page must be greater than 0")
        
        if page_size < 1 or page_size > 100:
            raise serializers.ValidationError("Page size must be between 1 and 100")
        
        return attrs
