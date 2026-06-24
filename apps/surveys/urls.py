"""
Surveys URLs for Attendrix
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.surveys.views import (
    SurveyViewSet, SurveyQuestionViewSet, SurveyResponseViewSet,
    SurveyTemplateViewSet, SurveyInvitationViewSet, SurveyAnalyticsViewSet,
    generate_survey_report, analyze_survey_sentiment, cleanup_surveys
)

router = DefaultRouter()
router.register(r'surveys', SurveyViewSet, basename='survey')
router.register(r'questions', SurveyQuestionViewSet, basename='survey-question')
router.register(r'responses', SurveyResponseViewSet, basename='survey-response')
router.register(r'templates', SurveyTemplateViewSet, basename='survey-template')
router.register(r'invitations', SurveyInvitationViewSet, basename='survey-invitation')
router.register(r'analytics', SurveyAnalyticsViewSet, basename='survey-analytics')

app_name = 'surveys'

urlpatterns = [
    # Viewset routes
    path('', include(router.urls)),
    
    # Additional endpoints
    path('reports/generate/', generate_survey_report, name='generate-survey-report'),
    path('sentiment/analyze/', analyze_survey_sentiment, name='analyze-survey-sentiment'),
    path('cleanup/', cleanup_surveys, name='cleanup-surveys'),
]
