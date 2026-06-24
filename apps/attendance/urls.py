"""
Attendance URLs for Attendrix
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.attendance.views import (
    AttendanceSessionViewSet, AttendanceRecordViewSet, AttendanceStatisticsViewSet,
    AttendanceAlertViewSet, mark_attendance, my_attendance, generate_attendance_report,
    attendance_analytics, detect_anomalies
)

router = DefaultRouter()
router.register(r'sessions', AttendanceSessionViewSet, basename='attendance-session')
router.register(r'records', AttendanceRecordViewSet, basename='attendance-record')
router.register(r'statistics', AttendanceStatisticsViewSet, basename='attendance-statistics')
router.register(r'alerts', AttendanceAlertViewSet, basename='attendance-alert')

app_name = 'attendance'

urlpatterns = [
    # Viewset routes
    path('', include(router.urls)),
    
    # Additional endpoints
    path('mark/', mark_attendance, name='mark-attendance'),
    path('my-attendance/', my_attendance, name='my-attendance'),
    path('reports/generate/', generate_attendance_report, name='generate-attendance-report'),
    path('analytics/', attendance_analytics, name='attendance-analytics'),
    path('detect-anomalies/', detect_anomalies, name='detect-anomalies'),
]
