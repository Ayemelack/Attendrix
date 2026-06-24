"""
Analytics URLs for Attendrix
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.analytics.views import (
    AttendanceAnalyticsViewSet, StudentPerformanceAnalyticsViewSet,
    InstitutionalHealthIndexViewSet, PredictiveModelViewSet, PredictionResultViewSet,
    analytics_query, predictive_analytics, generate_report, trend_analysis
)

router = DefaultRouter()
router.register(r'attendance', AttendanceAnalyticsViewSet, basename='attendance-analytics')
router.register(r'performance', StudentPerformanceAnalyticsViewSet, basename='performance-analytics')
router.register(r'health', InstitutionalHealthIndexViewSet, basename='institutional-health')
router.register(r'models', PredictiveModelViewSet, basename='predictive-model')
router.register(r'predictions', PredictionResultViewSet, basename='prediction-results')

app_name = 'analytics'

urlpatterns = [
    # Viewset routes
    path('', include(router.urls)),
    
    # Additional endpoints
    path('query/', analytics_query, name='analytics-query'),
    path('predictive/', predictive_analytics, name='predictive-analytics'),
    path('reports/generate/', generate_report, name='generate-report'),
    path('trends/', trend_analysis, name='trend-analysis'),
]
