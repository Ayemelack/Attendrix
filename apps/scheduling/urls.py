"""
Scheduling URLs for Attendrix
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.scheduling.views import (
    ScheduleViewSet, ScheduleOccurrenceViewSet, ScheduleTemplateViewSet,
    ScheduleConflictViewSet, SchedulePreferenceViewSet,
    bulk_create_schedules, schedule_analytics, available_slots
)

router = DefaultRouter()
router.register(r'schedules', ScheduleViewSet, basename='schedule')
router.register(r'occurrences', ScheduleOccurrenceViewSet, basename='schedule-occurrence')
router.register(r'templates', ScheduleTemplateViewSet, basename='schedule-template')
router.register(r'conflicts', ScheduleConflictViewSet, basename='schedule-conflict')
router.register(r'preferences', SchedulePreferenceViewSet, basename='schedule-preference')

app_name = 'scheduling'

urlpatterns = [
    # Viewset routes
    path('', include(router.urls)),
    
    # Additional endpoints
    path('bulk-create/', bulk_create_schedules, name='bulk-create-schedules'),
    path('analytics/', schedule_analytics, name='schedule-analytics'),
    path('available-slots/', available_slots, name='available-slots'),
]
