"""
Surveys views for Attendrix - Survey and feedback engine
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
from apps.surveys.models import (
    Survey, SurveyQuestion, SurveyResponse, SurveyAnswer,
    SurveyTemplate, SurveyAnalytics, SurveyInvitation, SurveyNotification
)
from apps.surveys.serializers import (
    SurveySerializer, SurveyQuestionSerializer, SurveyResponseSerializer, SurveyAnswerSerializer,
    SurveyTemplateSerializer, SurveyAnalyticsSerializer, SurveyInvitationSerializer, SurveyNotificationSerializer,
    SurveyCreateFromTemplateSerializer, SurveyResponseSubmissionSerializer, SurveyQuestionResponseSerializer,
    BulkSurveyInvitationSerializer, SurveyAnalyticsRequestSerializer, SurveyReportSerializer,
    SurveyCopySerializer, SurveySearchSerializer
)
from apps.surveys.tasks import (
    generate_survey_analytics, send_survey_invitations,
    process_survey_notifications, cleanup_old_survey_data,
    analyze_survey_sentiment
)
import json


class SurveyViewSet(viewsets.ModelViewSet):
    """
    Survey viewset
    """
    serializer_class = SurveySerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['status', 'visibility', 'anonymous_responses']
    search_fields = ['title', 'description']
    ordering_fields = ['created_at', 'title', 'start_date', 'end_date']
    ordering = ['-created_at']

    def get_queryset(self):
        """Filter surveys by institution and user role"""
        user = self.request.user
        queryset = Survey.objects.filter(
            institution=user.institution,
            is_deleted=False
        )
        
        # Filter based on user role
        if user.is_student():
            # Students can see public and targeted surveys
            queryset = queryset.filter(
                Q(visibility='public') |
                Q(target_roles__contains=[user.role]) |
                Q(target_users=user)
            )
        elif user.is_lecturer():
            # Lecturers can see public, department-targeted, and course-targeted surveys
            queryset = queryset.filter(
                Q(visibility='public') |
                Q(target_roles__contains=[user.role]) |
                Q(target_users=user) |
                Q(target_departments__in=user.departments.all()) |
                Q(target_courses__in=user.courseenrollments.filter(status='enrolled').values_list('course', flat=True))
            )
        elif user.is_institution_admin():
            # Institution admins can see all surveys in their institution
            queryset = queryset.filter(user__institution=user.institution)
        elif user.is_super_admin():
            # Super admins can see all surveys
            pass
        
        return queryset.distinct()

    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        """Activate survey"""
        survey = self.get_object()
        
        if survey.status == 'active':
            return Response({
                'error': 'Survey is already active'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        survey.status = 'active'
        survey.save()
        
        # Log activation
        ActivityLog.objects.create(
            user=request.user,
            institution=survey.institution,
            action_type='update',
            action_description=f'Survey activated: {survey.title}',
            severity='medium'
        )
        
        return Response({
            'message': 'Survey activated successfully'
        })

    @action(detail=True, methods=['post'])
    def pause(self, request, pk=None):
        """Pause survey"""
        survey = self.get_object()
        
        if survey.status != 'active':
            return Response({
                'error': 'Only active surveys can be paused'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        survey.status = 'paused'
        survey.save()
        
        # Log pause
        ActivityLog.objects.create(
            user=request.user,
            institution=survey.institution,
            action_type='update',
            action_description=f'Survey paused: {survey.title}',
            severity='medium'
        )
        
        return Response({
            'message': 'Survey paused successfully'
        })

    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        """Complete survey"""
        survey = self.get_object()
        
        if survey.status == 'completed':
            return Response({
                'error': 'Survey is already completed'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        survey.status = 'completed'
        survey.end_date = timezone.now()
        survey.save()
        
        # Log completion
        ActivityLog.objects.create(
            user=request.user,
            institution=survey.institution,
            action_type='update',
            action_description=f'Survey completed: {survey.title}',
            severity='medium'
        )
        
        return Response({
            'message': 'Survey completed successfully'
        })

    @action(detail=True, methods=['get'])
    def questions(self, request, pk=None):
        """Get survey questions"""
        survey = self.get_object()
        questions = survey.questions.filter(is_deleted=False).order_by('order', 'page_number')
        
        serializer = SurveyQuestionSerializer(questions, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def responses(self, request, pk=None):
        """Get survey responses"""
        survey = self.get_object()
        
        # Filter based on user role
        user = request.user
        if user.is_student():
            # Students can only see their own responses
            responses = survey.responses.filter(user=user, is_deleted=False)
        else:
            # Others can see all responses
            responses = survey.responses.filter(is_deleted=False)
        
        # Apply filters
        status_filter = request.query_params.get('status')
        if status_filter:
            responses = responses.filter(status=status_filter)
        
        page = self.paginate_queryset(responses)
        serializer = SurveyResponseSerializer(page, many=True)
        return self.get_paginated_response(serializer.data)

    @action(detail=True, methods=['get'])
    def analytics(self, request, pk=None):
        """Get survey analytics"""
        survey = self.get_object()
        
        # Get analytics types
        analytics_types = request.query_params.getlist('types', ['response_rate', 'completion_rate'])
        
        # Get date range
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        
        if not start_date:
            start_date = survey.created_at.date()
        else:
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
        
        if not end_date:
            end_date = timezone.now().date()
        else:
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
        
        analytics_data = []
        
        for analytics_type in analytics_types:
            try:
                analytics = SurveyAnalytics.objects.get(
                    survey=survey,
                    analytics_type=analytics_type,
                    reference_date=end_date
                )
                analytics_data.append(SurveyAnalyticsSerializer(analytics).data)
            except SurveyAnalytics.DoesNotExist:
                # Create analytics if they don't exist
                analytics = SurveyAnalytics.objects.create(
                    survey=survey,
                    analytics_type=analytics_type,
                    reference_date=end_date
                )
                analytics_data.append(SurveyAnalyticsSerializer(analytics).data)
        
        return Response({
            'survey': SurveySerializer(survey).data,
            'analytics': analytics_data,
            'period': {
                'start_date': start_date,
                'end_date': end_date
            }
        })

    @action(detail=True, methods=['post'])
    def copy(self, request, pk=None):
        """Copy survey"""
        survey = self.get_object()
        serializer = SurveyCopySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Create copy
        new_survey = Survey.objects.create(
            institution=survey.institution,
            title=serializer.validated_data['title'],
            description=serializer.validated_data.get('description', survey.description),
            status='draft',
            visibility=survey.visibility,
            estimated_duration=survey.estimated_duration,
            anonymous_responses=survey.anonymous_responses,
            require_authentication=survey.require_authentication,
            allow_multiple_responses=survey.allow_multiple_responses,
            show_results_to_respondents=survey.show_results_to_respondents,
            completion_message=survey.completion_message,
            redirect_url=survey.redirect_url,
            created_by=request.user
        )
        
        # Copy questions if requested
        if serializer.validated_data['copy_questions']:
            for question in survey.questions.filter(is_deleted=False):
                SurveyQuestion.objects.create(
                    survey=new_survey,
                    question_text=question.question_text,
                    question_type=question.question_type,
                    help_text=question.help_text,
                    is_required=question.is_required,
                    is_randomizable=question.is_randomizable,
                    show_on_same_page=question.show_on_same_page,
                    order=question.order,
                    page_number=question.page_number,
                    min_length=question.min_length,
                    max_length=question.max_length,
                    min_value=question.min_value,
                    max_value=question.max_value,
                    pattern=question.pattern,
                    choices=question.choices,
                    allow_other_option=question.allow_other_option,
                    other_option_label=question.other_option_label,
                    rating_min=question.rating_min,
                    rating_max=question.rating_max,
                    rating_labels=question.rating_labels,
                    matrix_rows=question.matrix_rows,
                    matrix_columns=question.matrix_columns,
                    max_file_size=question.max_file_size,
                    allowed_file_types=question.allowed_file_types
                )
        
        # Copy targeting if requested
        if serializer.validated_data['copy_targeting']:
            new_survey.target_roles = survey.target_roles
            new_survey.target_users.set(survey.target_users.all())
            new_survey.target_departments.set(survey.target_departments.all())
            new_survey.target_courses.set(survey.target_courses.all())
        
        # Copy settings if requested
        if serializer.validated_data['copy_settings']:
            new_survey.is_required = survey.is_required
            new_survey.max_responses = survey.max_responses
            new_survey.start_date = survey.start_date
            new_survey.end_date = survey.end_date
        
        new_survey.save()
        
        # Log copy
        ActivityLog.objects.create(
            user=request.user,
            institution=survey.institution,
            action_type='create',
            action_description=f'Survey copied: {new_survey.title} from {survey.title}',
            severity='low'
        )
        
        return Response({
            'message': 'Survey copied successfully',
            'survey': SurveySerializer(new_survey).data
        })

    @action(detail=False, methods=['post'])
    def create_from_template(self, request):
        """Create survey from template"""
        serializer = SurveyCreateFromTemplateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        user = request.user
        template_id = serializer.validated_data['template_id']
        title = serializer.validated_data['title']
        
        try:
            template = SurveyTemplate.objects.get(
                id=template_id,
                institution=user.institution
            )
        except SurveyTemplate.DoesNotExist:
            return Response({
                'error': 'Template not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Create survey from template
        survey = template.create_survey(title, **serializer.validated_data)
        
        # Log creation
        ActivityLog.objects.create(
            user=user,
            institution=survey.institution,
            action_type='create',
            action_description=f'Survey created from template: {survey.title}',
            severity='medium'
        )
        
        return Response({
            'message': 'Survey created from template successfully',
            'survey': SurveySerializer(survey).data
        })

    @action(detail=False, methods=['get'])
    def search(self, request):
        """Search surveys"""
        serializer = SurveySearchSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        
        user = request.user
        query = serializer.validated_data['query']
        status = serializer.validated_data.get('status', 'all')
        template_type = serializer.validated_data.get('template_type')
        created_by = serializer.validated_data.get('created_by')
        target_role = serializer.validated_data.get('target_role')
        page = serializer.validated_data.get('page', 1)
        page_size = serializer.validated_data.get('page_size', 20)
        
        # Build query
        queryset = Survey.objects.filter(
            institution=user.institution,
            is_deleted=False
        )
        
        if query:
            queryset = queryset.filter(
                Q(title__icontains=query) |
                Q(description__icontains=query)
            )
        
        if status != 'all':
            queryset = queryset.filter(status=status)
        
        if template_type:
            queryset = queryset.filter(
                id__in=SurveyTemplate.objects.filter(
                    template_type=template_type,
                    institution=user.institution
                ).values_list('survey_id', flat=True)
            )
        
        if created_by:
            queryset = queryset.filter(created_by_id=created_by)
        
        if target_role:
            queryset = queryset.filter(target_roles__contains=[target_role])
        
        # Apply role-based filtering
        if user.is_student():
            queryset = queryset.filter(
                Q(visibility='public') |
                Q(target_roles__contains=[user.role]) |
                Q(target_users=user)
            )
        elif user.is_lecturer():
            queryset = queryset.filter(
                Q(visibility='public') |
                Q(target_roles__contains=[user.role]) |
                Q(target_users=user) |
                Q(target_departments__in=user.departments.all()) |
                Q(target_courses__in=user.courseenrollments.filter(status='enrolled').values_list('course', flat=True))
            )
        
        # Paginate
        offset = (page - 1) * page_size
        limit = page_size
        total_count = queryset.count()
        
        surveys = queryset[offset:offset + limit]
        
        return Response({
            'results': SurveySerializer(surveys, many=True).data,
            'pagination': {
                'page': page,
                'page_size': page_size,
                'total_count': total_count,
                'total_pages': (total_count + page_size - 1) // page_size
            }
        })


class SurveyQuestionViewSet(viewsets.ModelViewSet):
    """
    Survey question viewset
    """
    serializer_class = SurveyQuestionSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['question_type', 'is_required', 'page_number']
    search_fields = ['question_text', 'help_text']
    ordering_fields = ['order', 'page_number', 'question_text']
    ordering = ['order', 'page_number']

    def get_queryset(self):
        """Filter questions by institution and user role"""
        user = self.request.user
        queryset = SurveyQuestion.objects.filter(
            institution=user.institution,
            is_deleted=False
        )
        
        # Filter based on user role and survey access
        if user.is_student():
            # Students can only see questions from surveys they can access
            accessible_surveys = Survey.objects.filter(
                Q(visibility='public') |
                Q(target_roles__contains=[user.role]) |
                Q(target_users=user)
            )
            queryset = queryset.filter(survey__in=accessible_surveys)
        elif user.is_lecturer():
            # Lecturers can see questions from surveys they can access
            accessible_surveys = Survey.objects.filter(
                Q(visibility='public') |
                Q(target_roles__contains=[user.role]) |
                Q(target_users=user) |
                Q(target_departments__in=user.departments.all()) |
                Q(target_courses__in=user.courseenrollments.filter(status='enrolled').values_list('course', flat=True))
            )
            queryset = queryset.filter(survey__in=accessible_surveys)
        elif user.is_institution_admin():
            # Institution admins can see all questions in their institution
            queryset = queryset.filter(survey__institution=user.institution)
        elif user.is_super_admin():
            # Super admins can see all questions
            pass
        
        return queryset.distinct()

    @action(detail=True, methods=['get'])
    def answers(self, request, pk=None):
        """Get answers for this question"""
        question = self.get_object()
        
        # Check if user can access survey
        user = request.user
        if not question.survey.can_respond(user)[0]:
            return Response({
                'error': 'Permission denied'
            }, status=status.HTTP_403_FORBIDDEN)
        
        answers = question.answers.filter(response__is_deleted=False)
        
        # Calculate statistics
        total_answers = answers.count()
        answer_stats = {}
        
        if question.question_type in ['choice', 'dropdown']:
            # Count responses for each choice
            for choice in question.choices:
                choice_value = choice['value']
                count = answers.filter(value=choice_value).count()
                answer_stats[choice_value] = {
                    'label': choice['label'],
                    'count': count,
                    'percentage': (count / total_answers * 100) if total_answers > 0 else 0
                }
        
        elif question.question_type == 'checkbox':
            # Count responses for each choice (multiple selections allowed)
            for choice in question.choices:
                choice_value = choice['value']
                count = answers.filter(value__contains=choice_value).count()
                answer_stats[choice_value] = {
                    'label': choice['label'],
                    'count': count,
                    'percentage': (count / total_answers * 100) if total_answers > 0 else 0
                }
        
        elif question.question_type in ['rating', 'scale']:
            # Calculate average rating
            rating_values = []
            for answer in answers:
                try:
                    rating_values.append(float(answer.value))
                except (ValueError, TypeError):
                    pass
            
            if rating_values:
                avg_rating = sum(rating_values) / len(rating_values)
                answer_stats['average'] = round(avg_rating, 2)
                answer_stats['distribution'] = {}
                
                for i in range(question.rating_min, question.rating_max + 1):
                    count = rating_values.count(i)
                    answer_stats['distribution'][i] = {
                        'count': count,
                        'percentage': (count / len(rating_values) * 100)
                    }
        
        return Response({
            'question': SurveyQuestionSerializer(question).data,
            'total_answers': total_answers,
            'statistics': answer_stats
        })


class SurveyResponseViewSet(viewsets.ModelViewSet):
    """
    Survey response viewset
    """
    serializer_class = SurveyResponseSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['status', 'is_anonymous']
    search_fields = ['user__first_name', 'user__last_name']
    ordering_fields = ['created_at', 'completed_at', 'progress_percentage']
    ordering = ['-created_at']

    def get_queryset(self):
        """Filter responses by institution and user role"""
        user = self.request.user
        queryset = SurveyResponse.objects.filter(
            institution=user.institution,
            is_deleted=False
        )
        
        # Filter based on user role
        if user.is_student():
            # Students can only see their own responses
            queryset = queryset.filter(user=user)
        elif user.is_lecturer():
            # Lecturers can see responses from their courses
            queryset = queryset.filter(
                Q(user=user) |
                Q(survey__target_courses__in=user.courseenrollments.filter(status='enrolled').values_list('course', flat=True))
            )
        elif user.is_institution_admin():
            # Institution admins can see all responses in their institution
            queryset = queryset.filter(user__institution=user.institution)
        elif user.is_super_admin():
            # Super admins can see all responses
            pass
        
        return queryset.distinct()

    @action(detail=True, methods=['get'])
    def answers(self, request, pk=None):
        """Get answers for this response"""
        response = self.get_object()
        
        # Check if user can access this response
        user = request.user
        if user.is_student() and response.user != user:
            return Response({
                'error': 'Permission denied'
            }, status=status.HTTP_403_FORBIDDEN)
        
        answers = response.answers.filter(is_deleted=False)
        serializer = SurveyAnswerSerializer(answers, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def submit_answer(self, request, pk=None):
        """Submit answer for a specific question"""
        response = self.get_object()
        
        if response.status == 'completed':
            return Response({
                'error': 'Cannot submit answers to completed response'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        serializer = SurveyQuestionResponseSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        question_id = serializer.validated_data['question_id']
        value = serializer.validated_data['value']
        
        try:
            question = SurveyQuestion.objects.get(id=question_id, survey=response.survey)
        except SurveyQuestion.DoesNotExist:
            return Response({
                'error': 'Question not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Validate answer
        try:
            question.validate_response(value)
        except ValidationError as e:
            return Response({
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Set answer
        answer = response.set_answer(question, value)
        
        return Response({
            'message': 'Answer submitted successfully',
            'answer': SurveyAnswerSerializer(answer).data
        })

    @action(detail=True, methods=['post'])
    def submit_answers(self, request, pk=None):
        """Submit multiple answers"""
        response = self.get_object()
        
        if response.status == 'completed':
            return Response({
                'error': 'Cannot submit answers to completed response'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        serializer = SurveyResponseSubmissionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        answers_data = serializer.validated_data['answers']
        is_completed = serializer.validated_data.get('is_completed', False)
        
        submitted_answers = []
        errors = []
        
        for question_id, value in answers_data.items():
            try:
                question = SurveyQuestion.objects.get(id=question_id, survey=response.survey)
                
                # Validate answer
                question.validate_response(value)
                
                # Set answer
                answer = response.set_answer(question, value)
                submitted_answers.append(SurveyAnswerSerializer(answer).data)
                
            except SurveyQuestion.DoesNotExist:
                errors.append(f"Question {question_id} not found")
            except ValidationError as e:
                errors.append(f"Question {question_id}: {str(e)}")
        
        if errors:
            return Response({
                'error': 'Some answers could not be submitted',
                'errors': errors
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Mark as completed if requested
        if is_completed:
            response.complete()
        
        return Response({
            'message': f'Submitted {len(submitted_answers)} answers successfully',
            'answers': submitted_answers,
            'is_completed': response.status == 'completed'
        })

    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        """Complete survey response"""
        response = self.get_object()
        
        if response.status == 'completed':
            return Response({
                'error': 'Response is already completed'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        response.complete()
        
        return Response({
            'message': 'Response completed successfully'
        })


class SurveyTemplateViewSet(viewsets.ModelViewSet):
    """
    Survey template viewset
    """
    serializer_class = SurveyTemplateSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['template_type', 'is_public', 'is_default']
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'template_type', 'created_at']
    ordering = ['name']

    def get_queryset(self):
        """Filter templates by institution and user role"""
        user = self.request.user
        queryset = SurveyTemplate.objects.filter(
            institution=user.institution,
            is_deleted=False
        )
        
        # Filter based on user role
        if user.is_student():
            # Students can only see public templates
            queryset = queryset.filter(is_public=True)
        elif user.is_lecturer():
            # Lecturers can see public templates and their own
            queryset = queryset.filter(
                Q(is_public=True) |
                Q(created_by=user)
            )
        elif user.is_institution_admin():
            # Institution admins can see all templates in their institution
            pass
        elif user.is_super_admin():
            # Super admins can see all templates
            pass
        
        return queryset.distinct()

    @action(detail=True, methods=['post'])
    def create_survey(self, request, pk=None):
        """Create survey from template"""
        template = self.get_object()
        
        serializer = SurveyCopySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Create survey from template
        survey = template.create_survey(**serializer.validated_data)
        
        # Log creation
        ActivityLog.objects.create(
            user=request.user,
            institution=survey.institution,
            action_type='create',
            action_description=f'Survey created from template: {survey.title}',
            severity='medium'
        )
        
        return Response({
            'message': 'Survey created from template successfully',
            'survey': SurveySerializer(survey).data
        })


class SurveyInvitationViewSet(viewsets.ModelViewSet):
    """
    Survey invitation viewset
    """
    serializer_class = SurveyInvitationSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['status']
    search_fields = ['user__first_name', 'user__last_name']
    ordering_fields = ['sent_at', 'status']
    ordering = ['-sent_at']

    def get_queryset(self):
        """Filter invitations by institution and user role"""
        user = self.request.user
        queryset = SurveyInvitation.objects.filter(
            institution=user.institution,
            is_deleted=False
        )
        
        # Filter based on user role
        if user.is_student():
            # Students can only see their own invitations
            queryset = queryset.filter(user=user)
        elif user.is_lecturer():
            # Lecturers can see invitations for their courses
            queryset = queryset.filter(
                Q(user=user) |
                Q(survey__target_courses__in=user.courseenrollments.filter(status='enrolled').values_list('course', flat=True))
            )
        elif user.is_institution_admin():
            # Institution admins can see all invitations in their institution
            queryset = queryset.filter(user__institution=user.institution)
        elif user.is_super_admin():
            # Super admins can see all invitations
            pass
        
        return queryset.distinct()

    @action(detail=True, methods=['post'])
    def resend(self, request, pk=None):
        """Resend invitation"""
        invitation = self.get_object()
        
        if invitation.status in ['completed', 'expired']:
            return Response({
                'error': 'Cannot resend completed or expired invitations'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Reset invitation
        invitation.status = 'sent'
        invitation.email_opened = False
        invitation.link_clicked = False
        invitation.reminders_sent += 1
        invitation.save()
        
        # Send notification
        from apps.surveys.tasks import send_survey_invitation
        send_survey_invitation.delay(invitation.id)
        
        return Response({
            'message': 'Invitation resent successfully'
        })

    @action(detail=False, methods=['post'])
    def bulk_create(self, request):
        """Create bulk invitations"""
        serializer = BulkSurveyInvitationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        user = request.user
        survey_id = serializer.validated_data['survey_id']
        user_ids = serializer.validated_data['user_ids']
        personal_message = serializer.validated_data.get('personal_message', '')
        sender_name = serializer.validated_data.get('sender_name', user.get_full_name())
        expires_at = serializer.validated_data.get('expires_at')
        
        try:
            survey = Survey.objects.get(id=survey_id, institution=user.institution)
        except Survey.DoesNotExist:
            return Response({
                'error': 'Survey not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        invitations_created = []
        errors = []
        
        for user_id in user_ids:
            try:
                target_user = User.objects.get(id=user_id, institution=user.institution)
                
                # Check if invitation already exists
                if SurveyInvitation.objects.filter(survey=survey, user=target_user).exists():
                    errors.append(f"Invitation already exists for {target_user.get_full_name()}")
                    continue
                
                invitation = SurveyInvitation.objects.create(
                    survey=survey,
                    user=target_user,
                    personal_message=personal_message,
                    sender_name=sender_name,
                    expires_at=expires_at
                )
                
                # Send notification
                from apps.surveys.tasks import send_survey_invitation
                send_survey_invitation.delay(invitation.id)
                
                invitations_created.append(invitation.id)
                
            except User.DoesNotExist:
                errors.append(f"User {user_id} not found")
        
        return Response({
            'message': f'Created {len(invitations_created)} invitations',
            'invitations_created': invitations_created,
            'errors': errors
        })


class SurveyAnalyticsViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Survey analytics viewset
    """
    serializer_class = SurveyAnalyticsSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['analytics_type']
    search_fields = ['metadata']
    ordering_fields = ['reference_date', 'analytics_type']
    ordering = ['-reference_date']

    def get_queryset(self):
        """Filter analytics by institution and user role"""
        user = self.request.user
        queryset = SurveyAnalytics.objects.filter(
            institution=user.institution
        )
        
        # Filter based on user role
        if user.is_student():
            # Students can only see analytics for surveys they can access
            accessible_surveys = Survey.objects.filter(
                Q(visibility='public') |
                Q(target_roles__contains=[user.role]) |
                Q(target_users=user)
            )
            queryset = queryset.filter(survey__in=accessible_surveys)
        elif user.is_lecturer():
            # Lecturers can see analytics for surveys they can access
            accessible_surveys = Survey.objects.filter(
                Q(visibility='public') |
                Q(target_roles__contains=[user.role]) |
                Q(target_users=user) |
                Q(target_departments__in=user.departments.all()) |
                Q(target_courses__in=user.courseenrollments.filter(status='enrolled').values_list('course', flat=True))
            )
            queryset = queryset.filter(survey__in=accessible_surveys)
        elif user.is_institution_admin():
            # Institution admins can see all analytics in their institution
            queryset = queryset.filter(survey__institution=user.institution)
        elif user.is_super_admin():
            # Super admins can see all analytics
            pass
        
        return queryset.distinct()

    @action(detail=False, methods=['post'])
    def generate(self, request):
        """Generate analytics for surveys"""
        serializer = SurveyAnalyticsRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        user = request.user
        survey_id = serializer.validated_data['survey_id']
        analytics_types = serializer.validated_data['analytics_types']
        start_date = serializer.validated_data.get('start_date')
        end_date = serializer.validated_data.get('end_date')
        
        try:
            survey = Survey.objects.get(id=survey_id, institution=user.institution)
        except Survey.DoesNotExist:
            return Response({
                'error': 'Survey not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Trigger analytics generation
        generate_survey_analytics.delay(
            survey.id,
            analytics_types,
            start_date,
            end_date
        )
        
        return Response({
            'message': 'Analytics generation started',
            'survey': SurveySerializer(survey).data
        })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def generate_survey_report(request):
    """
    Generate survey report
    """
    serializer = SurveyReportSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    
    user = request.user
    survey_id = serializer.validated_data['survey_id']
    report_type = serializer.validated_data['report_type']
    format_type = serializer.validated_data['format']
    
    try:
        survey = Survey.objects.get(id=survey_id, institution=user.institution)
    except Survey.DoesNotExist:
        return Response({
            'error': 'Survey not found'
        }, status=status.HTTP_404_NOT_FOUND)
    
    # Trigger report generation
    from apps.surveys.tasks import generate_survey_report
    report_data = {
        'survey_id': survey.id,
        'report_type': report_type,
        'format': format_type,
        'start_date': serializer.validated_data.get('start_date'),
        'end_date': serializer.validated_data.get('end_date'),
        'status': serializer.validated_data.get('status'),
        'include_answers': serializer.validated_data.get('include_answers', True),
        'include_analytics': serializer.validated_data.get('include_analytics', True),
        'requested_by': user.id
    }
    
    generate_survey_report.delay(report_data)
    
    return Response({
        'message': 'Survey report generation started',
        'survey': SurveySerializer(survey).data,
        'report_type': report_type,
        'format': format_type
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def analyze_survey_sentiment(request):
    """
    Analyze survey sentiment
    """
    user = request.user
    survey_id = request.data.get('survey_id')
    
    try:
        survey = Survey.objects.get(id=survey_id, institution=user.institution)
    except Survey.DoesNotExist:
        return Response({
            'error': 'Survey not found'
        }, status=status.HTTP_404_NOT_FOUND)
    
    # Trigger sentiment analysis
    analyze_survey_sentiment.delay(survey.id)
    
    return Response({
        'message': 'Sentiment analysis started',
        'survey': SurveySerializer(survey).data
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def cleanup_surveys(request):
    """
    Clean up old survey data
    """
    user = request.user
    
    if not user.is_admin():
        return Response({
            'error': 'Admin access required'
        }, status=status.HTTP_403_FORBIDDEN)
    
    # Trigger cleanup
    cleanup_old_survey_data.delay(user.institution.id)
    
    return Response({
        'message': 'Survey cleanup started'
    })
