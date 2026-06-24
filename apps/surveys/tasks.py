"""
Surveys tasks for Attendrix - Background processing for survey and feedback engine
"""
from celery import shared_task
from django.utils import timezone
from django.db.models import Q, Count, Avg, Sum, StdDev
from django.db.models.functions import Extract
from datetime import datetime, timedelta
from apps.core.models import ActivityLog
from apps.surveys.models import (
    Survey, SurveyQuestion, SurveyResponse, SurveyAnswer,
    SurveyTemplate, SurveyAnalytics, SurveyInvitation, SurveyNotification
)
from apps.alerts.models import Notification, NotificationTemplate
from apps.users.models import User
import logging

logger = logging.getLogger(__name__)


@shared_task
def generate_survey_analytics(survey_id, analytics_types, start_date=None, end_date=None):
    """
    Generate survey analytics for specified types
    """
    try:
        survey = Survey.objects.get(id=survey_id)
        
        if not start_date:
            start_date = survey.created_at.date()
        if not end_date:
            end_date = timezone.now().date()
        
        analytics_generated = 0
        
        for analytics_type in analytics_types:
            if analytics_type == 'response_rate':
                _generate_response_rate_analytics(survey, start_date, end_date)
                analytics_generated += 1
            elif analytics_type == 'completion_rate':
                _generate_completion_rate_analytics(survey, start_date, end_date)
                analytics_generated += 1
            elif analytics_type == 'question_analytics':
                _generate_question_analytics(survey, start_date, end_date)
                analytics_generated += 1
            elif analytics_type == 'demographic_analytics':
                _generate_demographic_analytics(survey, start_date, end_date)
                analytics_generated += 1
            elif analytics_type == 'trend_analytics':
                _generate_trend_analytics(survey, start_date, end_date)
                analytics_generated += 1
            elif analytics_type == 'sentiment_analysis':
                _generate_sentiment_analytics(survey, start_date, end_date)
                analytics_generated += 1
        
        logger.info(f"Generated {analytics_generated} analytics for survey {survey_id}")
        return analytics_generated
        
    except Exception as e:
        logger.error(f"Error generating survey analytics: {e}")
        return 0


def _generate_response_rate_analytics(survey, start_date, end_date):
    """Generate response rate analytics"""
    # Calculate potential respondents
    potential_respondents = 0
    
    if survey.target_users.exists():
        potential_respondents = survey.target_users.count()
    else:
        # Estimate based on target roles
        potential_respondents = User.objects.filter(
            institution=survey.institution,
            role__in=survey.target_roles
        ).count()
    
    # Get actual responses
    total_responses = SurveyResponse.objects.filter(
        survey=survey,
        created_at__date__gte=start_date,
        created_at__date__lte=end_date,
        is_deleted=False
    ).count()
    
    # Create or update analytics
    SurveyAnalytics.objects.update_or_create(
        survey=survey,
        analytics_type='response_rate',
        reference_date=end_date,
        defaults={
            'total_responses': total_responses,
            'response_rate': (total_responses / potential_respondents * 100) if potential_respondents > 0 else 0
        }
    )


def _generate_completion_rate_analytics(survey, start_date, end_date):
    """Generate completion rate analytics"""
    responses = SurveyResponse.objects.filter(
        survey=survey,
        created_at__date__gte=start_date,
        created_at__date__lte=end_date,
        is_deleted=False
    )
    
    total_responses = responses.count()
    completed_responses = responses.filter(status='completed').count()
    
    # Calculate average completion time
    completed_responses_with_time = responses.filter(
        status='completed',
        completed_at__isnull=False
    )
    
    completion_times = []
    for response in completed_responses_with_time:
        if response.completed_at and response.started_at:
            time_diff = response.completed_at - response.started_at
            completion_times.append(time_diff.total_seconds() / 60)  # Convert to minutes
    
    avg_completion_time = sum(completion_times) / len(completion_times) if completion_times else 0
    
    # Create or update analytics
    SurveyAnalytics.objects.update_or_create(
        survey=survey,
        analytics_type='completion_rate',
        reference_date=end_date,
        defaults={
            'total_responses': total_responses,
            'completed_responses': completed_responses,
            'completion_rate': (completed_responses / total_responses * 100) if total_responses > 0 else 0,
            'average_completion_time': avg_completion_time
        }
    )


def _generate_question_analytics(survey, start_date, end_date):
    """Generate question-specific analytics"""
    questions = survey.questions.filter(is_deleted=False)
    
    question_data = {}
    
    for question in questions:
        answers = SurveyAnswer.objects.filter(
            question=question,
            response__created_at__date__gte=start_date,
            response__created_at__date__lte=end_date,
            is_deleted=False
        )
        
        total_answers = answers.count()
        
        if total_answers == 0:
            continue
        
        question_stats = {
            'total_answers': total_answers,
            'question_text': question.question_text,
            'question_type': question.question_type
        }
        
        if question.question_type in ['choice', 'dropdown']:
            # Count responses for each choice
            choice_stats = {}
            for choice in question.choices:
                choice_value = choice['value']
                count = answers.filter(value=choice_value).count()
                choice_stats[choice_value] = {
                    'label': choice['label'],
                    'count': count,
                    'percentage': (count / total_answers * 100)
                }
            question_stats['choices'] = choice_stats
        
        elif question.question_type == 'checkbox':
            # Count responses for each choice (multiple selections allowed)
            choice_stats = {}
            for choice in question.choices:
                choice_value = choice['value']
                count = answers.filter(value__contains=choice_value).count()
                choice_stats[choice_value] = {
                    'label': choice['label'],
                    'count': count,
                    'percentage': (count / total_answers * 100)
                }
            question_stats['choices'] = choice_stats
        
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
                question_stats['average'] = round(avg_rating, 2)
                question_stats['distribution'] = {}
                
                for i in range(question.rating_min, question.rating_max + 1):
                    count = rating_values.count(i)
                    question_stats['distribution'][i] = {
                        'count': count,
                        'percentage': (count / len(rating_values) * 100)
                    }
        
        elif question.question_type in ['text', 'textarea']:
            # Text analytics
            text_responses = [answer.value for answer in answers if answer.value]
            total_length = sum(len(text) for text in text_responses)
            avg_length = total_length / len(text_responses) if text_responses else 0
            
            question_stats['average_length'] = round(avg_length, 2)
            question_stats['word_count'] = sum(len(text.split()) for text in text_responses)
        
        question_data[str(question.id)] = question_stats
    
    # Create or update analytics
    SurveyAnalytics.objects.update_or_create(
        survey=survey,
        analytics_type='question_analytics',
        reference_date=end_date,
        defaults={
            'question_data': question_data
        }
    )


def _generate_demographic_analytics(survey, start_date, end_date):
    """Generate demographic analytics"""
    responses = SurveyResponse.objects.filter(
        survey=survey,
        created_at__date__gte=start_date,
        created_at__date__lte=end_date,
        is_deleted=False
    )
    
    demographic_data = {}
    
    # By role
    role_stats = {}
    for role in ['student', 'lecturer', 'institution_admin', 'super_admin', 'employee']:
        count = responses.filter(user__role=role).count()
        role_stats[role] = {
            'count': count,
            'percentage': (count / responses.count() * 100) if responses.count() > 0 else 0
        }
    demographic_data['by_role'] = role_stats
    
    # By department
    dept_stats = {}
    departments = responses.values('user__department__name').annotate(
        count=Count('id')
    ).order_by('-count')
    
    for dept in departments:
        dept_stats[dept['user__department__name']] = {
            'count': dept['count'],
            'percentage': (dept['count'] / responses.count() * 100) if responses.count() > 0 else 0
        }
    demographic_data['by_department'] = dept_stats
    
    # By course
    course_stats = {}
    courses = responses.values('user__courseenrollments__course__title').annotate(
        count=Count('id')
    ).order_by('-count')
    
    for course in courses:
        course_stats[course['user__courseenrollments__course__title']] = {
            'count': course['count'],
            'percentage': (course['count'] / responses.count() * 100) if responses.count() > 0 else 0
        }
    demographic_data['by_course'] = course_stats
    
    # Create or update analytics
    SurveyAnalytics.objects.update_or_create(
        survey=survey,
        analytics_type='demographic_analytics',
        reference_date=end_date,
        defaults={
            'demographic_data': demographic_data
        }
    )


def _generate_trend_analytics(survey, start_date, end_date):
    """Generate trend analytics"""
    trend_data = {}
    
    # Generate daily trends
    current_date = start_date
    while current_date <= end_date:
        day_responses = SurveyResponse.objects.filter(
            survey=survey,
            created_at__date=current_date,
            is_deleted=False
        )
        
        total_responses = day_responses.count()
        completed_responses = day_responses.filter(status='completed').count()
        
        trend_data[current_date.isoformat()] = {
            'total_responses': total_responses,
            'completed_responses': completed_responses,
            'completion_rate': (completed_responses / total_responses * 100) if total_responses > 0 else 0
        }
        
        current_date += timedelta(days=1)
    
    # Create or update analytics
    SurveyAnalytics.objects.update_or_create(
        survey=survey,
        analytics_type='trend_analytics',
        reference_date=end_date,
        defaults={
            'trend_data': trend_data
        }
    )


def _generate_sentiment_analytics(survey, start_date, end_date):
    """Generate sentiment analysis"""
    # Get text-based questions
    text_questions = survey.questions.filter(
        question_type__in=['text', 'textarea'],
        is_deleted=False
    )
    
    sentiment_data = {}
    
    for question in text_questions:
        answers = SurveyAnswer.objects.filter(
            question=question,
            response__created_at__date__gte=start_date,
            response__created_at__date__lte=end_date,
            is_deleted=False
        )
        
        # Simple sentiment analysis (would use NLP library in production)
        positive_keywords = ['good', 'excellent', 'great', 'amazing', 'perfect', 'love', 'helpful', 'useful', 'effective']
        negative_keywords = ['bad', 'poor', 'terrible', 'awful', 'hate', 'useless', 'ineffective', 'difficult', 'confusing']
        
        positive_count = 0
        negative_count = 0
        neutral_count = 0
        
        for answer in answers:
            if answer.value:
                text_lower = answer.value.lower()
                if any(keyword in text_lower for keyword in positive_keywords):
                    positive_count += 1
                elif any(keyword in text_lower for keyword in negative_keywords):
                    negative_count += 1
                else:
                    neutral_count += 1
        
        total_responses = positive_count + negative_count + neutral_count
        
        sentiment_data[str(question.id)] = {
            'positive': positive_count,
            'negative': negative_count,
            'neutral': neutral_count,
            'total': total_responses,
            'positive_percentage': (positive_count / total_responses * 100) if total_responses > 0 else 0,
            'negative_percentage': (negative_count / total_responses * 100) if total_responses > 0 else 0,
            'neutral_percentage': (neutral_count / total_responses * 100) if total_responses > 0 else 0
        }
    
    # Create or update analytics
    SurveyAnalytics.objects.update_or_create(
        survey=survey,
        analytics_type='sentiment_analysis',
        reference_date=end_date,
        defaults={
            'sentiment_data': sentiment_data
        }
    )


@shared_task
def send_survey_invitations(invitation_id=None, survey_id=None, user_ids=None):
    """
    Send survey invitations to users
    """
    try:
        invitations_sent = 0
        
        if invitation_id:
            # Send single invitation
            invitation = SurveyInvitation.objects.get(id=invitation_id)
            _send_single_invitation(invitation)
            invitations_sent = 1
        elif survey_id and user_ids:
            # Send bulk invitations
            survey = Survey.objects.get(id=survey_id)
            
            for user_id in user_ids:
                try:
                    user = User.objects.get(id=user_id, institution=survey.institution)
                    
                    # Check if invitation already exists
                    if SurveyInvitation.objects.filter(survey=survey, user=user).exists():
                        continue
                    
                    invitation = SurveyInvitation.objects.create(
                        survey=survey,
                        user=user,
                        expires_at=survey.end_date or timezone.now() + timedelta(days=30)
                    )
                    
                    _send_single_invitation(invitation)
                    invitations_sent += 1
                    
                except User.DoesNotExist:
                    pass
        
        logger.info(f"Sent {invitations_sent} survey invitations")
        return invitations_sent
        
    except Exception as e:
        logger.error(f"Error sending survey invitations: {e}")
        return 0


def _send_single_invitation(invitation):
    """Send a single survey invitation"""
    # Create notification
    notification = Notification.objects.create(
        institution=invitation.survey.institution,
        recipient=invitation.user,
        title=f"Survey Invitation: {invitation.survey.title}",
        message=f"You have been invited to participate in a survey. {invitation.personal_message}",
        notification_type='survey_invitation',
        priority='medium',
        metadata={
            'survey_id': invitation.survey.id,
            'invitation_id': invitation.id,
            'invitation_token': invitation.invitation_token
        }
    )
    
    # Queue for delivery
    from apps.alerts.models import NotificationQueue
    NotificationQueue.objects.create(
        institution=invitation.survey.institution,
        notification=notification,
        priority='medium',
        channel_priority=['in_app', 'email']
    )


@shared_task
def process_survey_notifications():
    """
    Process survey notifications and reminders
    """
    try:
        from apps.institutions.models import Institution
        institutions = Institution.objects.filter(is_active=True)
        
        notifications_processed = 0
        
        for institution in institutions:
            # Get upcoming surveys
            upcoming_surveys = Survey.objects.filter(
                institution=institution,
                status='active',
                start_date__lte=timezone.now(),
                end_date__gte=timezone.now(),
                is_deleted=False
            )
            
            for survey in upcoming_surveys:
                # Send reminders for incomplete responses
                incomplete_responses = SurveyResponse.objects.filter(
                    survey=survey,
                    status='in_progress',
                    created_at__lte=timezone.now() - timedelta(days=3),
                    is_deleted=False
                )
                
                for response in incomplete_responses:
                    # Check if reminder hasn't been sent recently
                    last_notification = SurveyNotification.objects.filter(
                        survey=survey,
                        user=response.user,
                        notification_type='reminder',
                        created_at__gte=timezone.now() - timedelta(hours=24)
                    ).exists()
                    
                    if not last_notification:
                        # Send reminder
                        SurveyNotification.objects.create(
                            institution=survey.institution,
                            user=response.user,
                            title=f"Survey Reminder: {survey.title}",
                            message=f"You have an incomplete survey response. Please complete it at your earliest convenience.",
                            notification_type='reminder',
                            priority='medium'
                        )
                        notifications_processed += 1
        
        logger.info(f"Processed {notifications_processed} survey notifications")
        return notifications_processed
        
    except Exception as e:
        logger.error(f"Error processing survey notifications: {e}")
        return 0


@shared_task
def cleanup_old_survey_data():
    """
    Clean up old survey data
    """
    try:
        # Clean up old survey responses (older than 2 years)
        cutoff_date = timezone.now() - timedelta(days=730)
        
        old_responses = SurveyResponse.objects.filter(
            created_at__lt=cutoff_date,
            is_deleted=False
        )
        
        count = old_responses.count()
        old_responses.update(is_deleted=True)
        
        # Clean up old analytics (older than 1 year)
        analytics_cutoff_date = timezone.now() - timedelta(days=365)
        
        old_analytics = SurveyAnalytics.objects.filter(
            reference_date__lt=analytics_cutoff_date
        )
        
        analytics_count = old_analytics.count()
        old_analytics.delete()
        
        # Clean up old invitations (older than 6 months)
        invitation_cutoff_date = timezone.now() - timedelta(days=180)
        
        old_invitations = SurveyInvitation.objects.filter(
            sent_at__lt=invitation_cutoff_date,
            status__in=['completed', 'expired', 'bounced']
        )
        
        invitation_count = old_invitations.count()
        old_invitations.delete()
        
        logger.info(f"Cleaned up old survey data: {count} responses, {analytics_count} analytics, {invitation_count} invitations")
        return count + analytics_count + invitation_count
        
    except Exception as e:
        logger.error(f"Error cleaning up old survey data: {e}")
        return 0


@shared_task
def analyze_survey_sentiment(survey_id):
    """
    Analyze sentiment for survey responses
    """
    try:
        survey = Survey.objects.get(id=survey_id)
        
        # Get all text-based questions
        text_questions = survey.questions.filter(
            question_type__in=['text', 'textarea'],
            is_deleted=False
        )
        
        sentiment_scores = {}
        
        for question in text_questions:
            answers = SurveyAnswer.objects.filter(
                question=question,
                response__status='completed',
                is_deleted=False
            )
            
            # Simple sentiment analysis
            positive_words = ['good', 'excellent', 'great', 'amazing', 'perfect', 'love', 'helpful', 'useful', 'effective', 'outstanding']
            negative_words = ['bad', 'poor', 'terrible', 'awful', 'hate', 'useless', 'ineffective', 'difficult', 'confusing', 'disappointing']
            
            total_score = 0
            word_count = 0
            
            for answer in answers:
                if answer.value:
                    words = answer.value.lower().split()
                    for word in words:
                        if word in positive_words:
                            total_score += 1
                        elif word in negative_words:
                            total_score -= 1
                        word_count += 1
            
            # Normalize score (-1 to 1)
            if word_count > 0:
                normalized_score = max(-1, min(1, total_score / word_count))
            else:
                normalized_score = 0
            
            sentiment_scores[str(question.id)] = {
                'score': normalized_score,
                'word_count': word_count,
                'total_score': total_score
            }
        
        # Store sentiment analysis
        SurveyAnalytics.objects.update_or_create(
            survey=survey,
            analytics_type='sentiment_analysis',
            reference_date=timezone.now().date(),
            defaults={
                'sentiment_data': sentiment_scores
            }
        )
        
        logger.info(f"Analyzed sentiment for survey {survey_id}")
        return 1
        
    except Exception as e:
        logger.error(f"Error analyzing survey sentiment: {e}")
        return 0


@shared_task
def generate_survey_report(report_data):
    """
    Generate survey report
    """
    try:
        survey_id = report_data['survey_id']
        report_type = report_data['report_type']
        format_type = report_data['format']
        start_date = report_data.get('start_date')
        end_date = report_data.get('end_date')
        status = report_data.get('status', 'all')
        include_answers = report_data.get('include_answers', True)
        include_analytics = report_data.get('include_analytics', True)
        requested_by = report_data['requested_by']
        
        survey = Survey.objects.get(id=survey_id)
        
        # Build query based on filters
        responses_query = SurveyResponse.objects.filter(
            survey=survey,
            is_deleted=False
        )
        
        if start_date:
            responses_query = responses_query.filter(created_at__date__gte=start_date)
        
        if end_date:
            responses_query = responses_query.filter(created_at__date__lte=end_date)
        
        if status != 'all':
            responses_query = responses_query(status=status)
        
        # Get data
        responses = responses_query.select_related('user')
        
        # Generate report based on type
        if report_type == 'summary':
            report_content = _generate_summary_report(responses, survey, start_date, end_date, include_analytics)
        elif report_type == 'responses':
            report_content = _generate_responses_report(responses, survey, start_date, end_date, include_answers)
        elif report_type == 'analytics':
            report_content = _generate_analytics_report(responses, survey, start_date, end_date)
        elif report_type == 'demographics':
            report_content = _generate_demographics_report(responses, survey, start_date, end_date)
        elif report_type == 'questions':
            report_content = _generate_questions_report(responses, survey, start_date, end_date)
        elif report_type == 'export':
            report_content = _generate_export_report(responses, survey, start_date, end_date, format_type)
        
        # Save report
        if format_type == 'json':
            return report_content
        elif format_type == 'csv':
            return _generate_csv_report(report_content, survey, report_type, start_date, end_date)
        elif format_type == 'pdf':
            return _generate_pdf_report(report_content, survey, report_type, start_date, end_date)
        elif format_type == 'excel':
            return _generate_excel_report(report_content, survey, report_type, start_date, end_date)
        
        return report_content
        
    except Exception as e:
        logger.error(f"Error generating survey report: {e}")
        return None


def _generate_summary_report(responses, survey, start_date, end_date, include_analytics):
    """Generate summary report"""
    # Calculate summary statistics
    total_responses = responses.count()
    completed_responses = responses.filter(status='completed').count()
    in_progress_responses = responses.filter(status='in_progress').count()
    abandoned_responses = responses.filter(status='abandoned').count()
    
    # Calculate completion rate
    completion_rate = (completed_responses / total_responses * 100) if total_responses > 0 else 0
    
    # Calculate average completion time
    completed_responses_with_time = responses.filter(
        status='completed',
        completed_at__isnull=False
    )
    
    completion_times = []
    for response in completed_responses_with_time:
        if response.completed_at and response.started_at:
            time_diff = response.completed_at - response.started_at
            completion_times.append(time_diff.total_seconds() / 60)  # Convert to minutes
    
    avg_completion_time = sum(completion_times) / len(completion_times) if completion_times else 0
    
    # Build report content
    report_content = {
        'survey': {
            'title': survey.title,
            'description': survey.description,
            'status': survey.status,
            'created_at': survey.created_at.isoformat(),
            'start_date': survey.start_date.isoformat() if survey.start_date else None,
            'end_date': survey.end_date.isoformat() if survey.end_date else None
        },
        'period': {
            'start_date': start_date.isoformat() if start_date else None,
            'end_date': end_date.isoformat() if end_date else None
        },
        'summary': {
            'total_responses': total_responses,
            'completed_responses': completed_responses,
            'in_progress_responses': in_progress_responses,
            'abandoned_responses': abandoned_responses,
            'completion_rate': round(completion_rate, 2),
            'average_completion_time': round(avg_completion_time, 2)
        }
    }
    
    if include_analytics:
        # Add analytics
        report_content['analytics'] = _get_analytics_summary(survey, start_date, end_date)
    
    return report_content


def _generate_responses_report(responses, survey, start_date, end_date, include_answers):
    """Generate responses report"""
    report_content = {
        'survey': {
            'title': survey.title,
            'description': survey.description
        },
        'period': {
            'start_date': start_date.isoformat() if start_date else None,
            'end_date': end_date.isoformat() if end_date else None
        },
        'responses': []
    }
    
    for response in responses[:1000]:  # Limit to 1000 responses for performance
        response_data = {
            'id': response.id,
            'user': response.user.get_full_name() if response.user else 'Anonymous',
            'status': response.status,
            'started_at': response.started_at.isoformat() if response.started_at else None,
            'completed_at': response.completed_at.isoformat() if response.completed_at else None,
            'progress_percentage': response.progress_percentage,
            'is_anonymous': response.is_anonymous,
            'ip_address': response.ip_address,
            'created_at': response.created_at.isoformat()
        }
        
        if include_answers:
            response_data['answers'] = []
            for answer in response.answers.filter(is_deleted=False):
                answer_data = {
                    'question_id': answer.question.id,
                    'question_text': answer.question.question_text,
                    'question_type': answer.question.question_type,
                    'value': answer.value,
                    'display_value': answer.get_display_value()
                }
                response_data['answers'].append(answer_data)
        
        report_content['responses'].append(response_data)
    
    return report_content


def _generate_analytics_report(responses, survey, start_date, end_date):
    """Generate analytics report"""
    # Get analytics for the period
    analytics = SurveyAnalytics.objects.filter(
        survey=survey,
        reference_date__gte=start_date,
        reference_date__lte=end_date
    ).order_by('reference_date')
    
    report_content = {
        'survey': {
            'title': survey.title,
            'description': survey.description
        },
        'period': {
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat()
        },
        'analytics': []
    }
    
    for analytic in analytics:
        report_content['analytics'].append({
            'date': analytic.reference_date.isoformat(),
            'analytics_type': analytic.analytics_type,
            'total_responses': analytic.total_responses,
            'completed_responses': analytic.completed_responses,
            'response_rate': analytic.response_rate,
            'completion_rate': analytic.completion_rate,
            'average_completion_time': analytic.average_completion_time,
            'question_data': analytic.question_data,
            'demographic_data': analytic.demographic_data,
            'trend_data': analytic.trend_data,
            'sentiment_data': analytic.sentiment_data
        })
    
    return report_content


def _generate_demographics_report(responses, survey, start_date, end_date):
    """Generate demographics report"""
    # Calculate demographic statistics
    role_stats = {}
    for role in ['student', 'lecturer', 'institution_admin', 'super_admin', 'employee']:
        count = responses.filter(user__role=role).count()
        role_stats[role] = count
    
    dept_stats = {}
    departments = responses.values('user__department__name').annotate(
        count=Count('id')
    ).order_by('-count')
    
    for dept in departments:
        dept_stats[dept['user__department__name']] = dept['count']
    
    course_stats = {}
    courses = responses.values('user__courseenrollments__course__title').annotate(
        count=Count('id')
    ).order_by('-count')
    
    for course in courses:
        course_stats[course['user__courseenrollments__course__title']] = course['count']
    
    report_content = {
        'survey': {
            'title': survey.title,
            'description': survey.description
        },
        'period': {
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat()
        },
        'demographics': {
            'by_role': role_stats,
            'by_department': dept_stats,
            'by_course': course_stats
        }
    }
    
    return report_content


def _generate_questions_report(responses, survey, start_date, end_date):
    """Generate questions report"""
    questions = survey.questions.filter(is_deleted=False).order_by('order')
    
    report_content = {
        'survey': {
            'title': survey.title,
            'description': survey.description
        },
        'period': {
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat()
        },
        'questions': []
    }
    
    for question in questions:
        answers = SurveyAnswer.objects.filter(
            question=question,
            response__created_at__date__gte=start_date,
            response__created_at__date__lte=end_date,
            is_deleted=False
        )
        
        question_data = {
            'id': question.id,
            'question_text': question.question_text,
            'question_type': question.question_type,
            'is_required': question.is_required,
            'total_answers': answers.count()
        }
        
        if question.question_type in ['choice', 'dropdown']:
            choice_stats = {}
            for choice in question.choices:
                choice_value = choice['value']
                count = answers.filter(value=choice_value).count()
                choice_stats[choice_value] = {
                    'label': choice['label'],
                    'count': count,
                    'percentage': (count / answers.count() * 100) if answers.count() > 0 else 0
                }
            question_data['choices'] = choice_stats
        
        elif question.question_type in ['rating', 'scale']:
            rating_values = []
            for answer in answers:
                try:
                    rating_values.append(float(answer.value))
                except (ValueError, TypeError):
                    pass
            
            if rating_values:
                avg_rating = sum(rating_values) / len(rating_values)
                question_data['average'] = round(avg_rating, 2)
                question_data['distribution'] = {}
                
                for i in range(question.rating_min, question.rating_max + 1):
                    count = rating_values.count(i)
                    question_data['distribution'][i] = count
        
        elif question.question_type in ['text', 'textarea']:
            text_responses = [answer.value for answer in answers if answer.value]
            total_length = sum(len(text) for text in text_responses)
            avg_length = total_length / len(text_responses) if text_responses else 0
            word_count = sum(len(text.split()) for text in text_responses)
            
            question_data['average_length'] = round(avg_length, 2)
            question_data['word_count'] = word_count
        
        report_content['questions'].append(question_data)
    
    return report_content


def _generate_export_report(responses, survey, start_date, end_date, format_type):
    """Generate export report"""
    # This would generate data in the specified format
    # For now, return JSON data
    return _generate_summary_report(responses, survey, start_date, end_date, True)


def _get_analytics_summary(survey, start_date, end_date):
    """Get analytics summary for the period"""
    # Get all analytics for the period
    analytics = SurveyAnalytics.objects.filter(
        survey=survey,
        reference_date__gte=start_date,
        reference_date__lte=end_date
    )
    
    # Calculate overall statistics
    total_responses = analytics.aggregate(
        total=Count('total_responses'),
        completed=Count('completed_responses'),
        avg_completion=Avg('average_completion_time')
    )
    
    # Calculate average metrics
    avg_response_rate = (total['total'] / survey.target_users.count() * 100) if survey.target_users.exists() else 0
    avg_completion_rate = (total['completed'] / total['total'] * 100) if total['total'] > 0 else 0
    
    return {
        'total_responses': total['total'],
        'completed_responses': total['completed'],
        'avg_response_rate': round(avg_response_rate, 2),
        'avg_completion_rate': round(avg_completion_rate, 2),
        'avg_completion_time': round(total['avg_completion_time'] or 0, 2)
    }


def _generate_csv_report(report_content, survey, report_type, start_date, end_date):
    """Generate CSV report"""
    import csv
    import io
    from django.http import HttpResponse
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="survey_{report_type}_{survey.title}_{start_date}_to_{end_date}.csv"'
    
    writer = csv.writer(response)
    
    # Write header based on report type
    if report_type == 'summary':
        writer.writerow([
            'Date', 'Total Responses', 'Completed Responses', 'Completion Rate', 'Avg Completion Time (minutes)'
        ])
        
        # Add data rows
        current_date = start_date
        while current_date <= end_date:
            analytics = SurveyAnalytics.objects.filter(
                survey=survey,
                analytics_type='completion_rate',
                reference_date=current_date
            ).first()
            
            if analytics:
                writer.writerow([
                    current_date.isoformat(),
                    analytics.total_responses,
                    analytics.completed_responses,
                    analytics.completion_rate,
                    analytics.average_completion_time
                ])
            else:
                writer.writerow([
                    current_date.isoformat(),
                    0, 0, 0, 0
                ])
            
            current_date += timedelta(days=1)
    
    elif report_type == 'responses':
        writer.writerow([
            'Response ID', 'User', 'Status', 'Started At', 'Completed At', 'Progress %', 'Is Anonymous'
        ])
        
        for response_data in report_content['responses']:
            writer.writerow([
                response_data['id'],
                response_data['user'],
                response_data['status'],
                response_data['started_at'],
                response_data['completed_at'],
                response_data['progress_percentage'],
                response_data['is_anonymous']
            ])
    
    elif report_type == 'questions':
        writer.writerow([
            'Question ID', 'Question Text', 'Question Type', 'Is Required', 'Total Answers'
        ])
        
        for question_data in report_content['questions']:
            writer.writerow([
                question_data['id'],
                question_data['question_text'],
                question_data['question_type'],
                question_data['is_required'],
                question_data['total_answers']
            ])
    
    return response


def _generate_pdf_report(report_content, survey, report_type, start_date, end_date):
    """Generate PDF report"""
    # This would integrate with a PDF library like ReportLab
    # For now, return JSON data
    return report_content


def _generate_excel_report(report_content, survey, report_type, start_date, end_date):
    """Generate Excel report"""
    # This would integrate with an Excel library like openpyxl
    # For now, return JSON data
    return report_content


@shared_task
def create_default_survey_templates():
    """
    Create default survey templates if they don't exist
    """
    try:
        from apps.institutions.models import Institution
        institutions = Institution.objects.filter(is_active=True)
        
        templates_created = 0
        
        for institution in institutions:
            # Create default templates
            templates = [
                {
                    'name': 'Course Evaluation Template',
                    'template_type': 'course_evaluation',
                    'description': 'Standard course evaluation template',
                    'survey_structure': {
                        'instructions': 'Please provide honest feedback about this course.',
                        'estimated_duration': 15,
                        'anonymous_responses': True,
                        'require_authentication': True
                    },
                    'questions': [
                        {
                            'question_text': 'Overall, how would you rate this course?',
                            'question_type': 'rating',
                            'is_required': True,
                            'rating_min': 1,
                            'rating_max': 5,
                            'rating_labels': {
                                1: 'Poor',
                                2: 'Fair',
                                3: 'Good',
                                4: 'Very Good',
                                5: 'Excellent'
                            }
                        },
                        {
                            'question_text': 'What did you like most about this course?',
                            'question_type': 'textarea',
                            'is_required': False
                        },
                        {
                            'question_text': 'What could be improved in this course?',
                            'question_type': 'textarea',
                            'is_required': False
                        },
                        {
                            'question_text': 'Would you recommend this course to others?',
                            'question_type': 'choice',
                            'is_required': True,
                            'choices': [
                                {'value': 'yes', 'label': 'Yes'},
                                {'value': 'no', 'label': 'No'},
                                {'value': 'maybe', 'label': 'Maybe'}
                            ]
                        }
                    ]
                },
                {
                    'name': 'Instructor Feedback Template',
                    'template_type': 'instructor_feedback',
                    'description': 'Standard instructor feedback template',
                    'survey_structure': {
                        'instructions': 'Please provide feedback about your instructor.',
                        'estimated_duration': 10,
                        'anonymous_responses': True,
                        'require_authentication': True
                    },
                    'questions': [
                        {
                            'question_text': 'How would you rate the instructor\'s teaching effectiveness?',
                            'question_type': 'rating',
                            'is_required': True,
                            'rating_min': 1,
                            'rating_max': 5,
                            'rating_labels': {
                                1: 'Poor',
                                2: 'Fair',
                                3: 'Good',
                                4: 'Very Good',
                                5: 'Excellent'
                            }
                        },
                        {
                            'question_text': 'How would you rate the instructor\'s communication skills?',
                            'question_type': 'rating',
                            'is_required': True,
                            'rating_min': 1,
                            'rating_max': 5,
                            'rating_labels': {
                                1: 'Poor',
                                2: 'Fair',
                                3: 'Good',
                                4: 'Very Good',
                                5: 'Excellent'
                            }
                        },
                        {
                            'question_text': 'How would you rate the instructor\'s availability for help?',
                            'question_type': 'rating',
                            'is_required': True,
                            'rating_min': 1,
                            'rating_max': 5,
                            'rating_labels': {
                                1: 'Poor',
                                2: 'Fair',
                                3: 'Good',
                                4: 'Very Good',
                                5: 'Excellent'
                            }
                        },
                        {
                            'question_text': 'What are the instructor\'s strengths?',
                            'question_type': 'textarea',
                            'is_required': False
                        },
                        {
                            'question_text': 'What areas could the instructor improve?',
                            'question_type': 'textarea',
                            'is_required': False
                        }
                    ]
                },
                {
                    'name': 'Student Satisfaction Survey',
                    'template_type': 'student_satisfaction',
                    'description': 'Standard student satisfaction survey',
                    'survey_structure': {
                        'instructions': 'Please share your feedback about your experience.',
                        'estimated_duration': 20,
                        'anonymous_responses': True,
                        'require_authentication': True
                    },
                    'questions': [
                        {
                            'question_text': 'How satisfied are you with your overall experience?',
                            'question_type': 'rating',
                            'is_required': True,
                            'rating_min': 1,
                            'rating_max': 5,
                            'rating_labels': {
                                1: 'Very Dissatisfied',
                                2: 'Dissatisfied',
                                3: 'Neutral',
                                4: 'Satisfied',
                                5: 'Very Satisfied'
                            }
                        },
                        {
                            'question_text': 'How likely are you to recommend our institution to others?',
                            'question_type': 'rating',
                            'is_required': True,
                            'rating_min': 1,
                            'rating_max': 10,
                            'rating_labels': {
                                1: 'Very Unlikely',
                                10: 'Very Likely'
                            }
                        },
                        {
                            'question_text': 'What do you like most about our institution?',
                            'question_type': 'textarea',
                            'is_required': False
                        },
                        {
                            'question_text': 'What improvements would you like to see?',
                            'question_type': 'textarea',
                            'is_required': False
                        },
                        {
                            'question_text': 'How satisfied are you with the academic programs?',
                            'question_type': 'rating',
                            'is_required': True,
                            'rating_min': 1,
                            'rating_max': 5,
                            'rating_labels': {
                                1: 'Very Dissatisfied',
                                2: 'Dissatisfied',
                                3: 'Neutral',
                                4: 'Satisfied',
                                5: 'Very Satisfied'
                            }
                        },
                        {
                            'question_text': 'How satisfied are you with the campus facilities?',
                            'question_type': 'rating',
                            'is_required': True,
                            'rating_min': 1,
                            'rating_max': 5,
                            'rating_labels': {
                                1: 'Very Dissatisfied',
                                2: 'Dissatisfied',
                                3: 'Neutral',
                                4: 'Satisfied',
                                5: 'Very Satisfied'
                            }
                        }
                    ]
                }
            ]
            
            for template_data in templates:
                template_data['institution_id'] = institution.id
                SurveyTemplate.objects.get_or_create(
                    **template_data
                )
                templates_created += 1
        
        logger.info(f"Created {templates_created} default survey templates")
        return templates_created
        
    except Exception as e:
        logger.error(f"Error creating default survey templates: {e}")
        return 0


@shared_task
def send_daily_survey_digest():
    """
    Send daily survey digest to institution admins
    """
    try:
        from apps.institutions.models import Institution
        institutions = Institution.objects.filter(is_active=True)
        
        digests_sent = 0
        
        for institution in institutions:
            # Get yesterday's survey statistics
            yesterday = timezone.now().date() - timedelta(days=1)
            
            yesterday_surveys = Survey.objects.filter(
                institution=institution,
                created_at__date=yesterday,
                is_deleted=False
            ).count()
            
            yesterday_responses = SurveyResponse.objects.filter(
                institution=institution,
                created_at__date=yesterday,
                is_deleted=False
            ).count()
            
            yesterday_completed = SurveyResponse.objects.filter(
                institution=institution,
                created_at__date=yesterday,
                status='completed',
                is_deleted=False
            ).count()
            
            # Create digest notification for admins
            if yesterday_surveys > 0:
                admins = User.objects.filter(
                    institution=institution,
                    role='institution_admin',
                    is_active=True
                )
                
                for admin in admins:
                    Notification.objects.create(
                        institution=institution,
                        recipient=admin,
                        title=f'Daily Survey Digest - {yesterday.strftime("%B %d, %Y")}',
                        message=f'Yesterday: {yesterday_surveys} surveys, {yesterday_responses} responses, {yesterday_completed} completed',
                        notification_type='system_update',
                        priority='low',
                        metadata={
                            'date': yesterday.isoformat(),
                            'total_surveys': yesterday_surveys,
                            'total_responses': yesterday_responses,
                            'completed_responses': yesterday_completed
                        }
                    )
                    digests_sent += 1
        
        logger.info(f"Sent {digests_sent} daily survey digests")
        return digests_sent
        
    except Exception as e:
        logger.error(f"Error sending daily survey digest: {e}")
        return 0
