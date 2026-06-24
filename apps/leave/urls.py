"""
Leave management URLs for Attendrix
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.leave.views import (
    LeaveTypeViewSet, LeaveBalanceViewSet, LeaveRequestViewSet, LeaveApprovalViewSet,
    LeaveCalendarViewSet, LeaveHolidayViewSet, LeaveAnalyticsViewSet, LeavePolicyViewSet,
    generate_leave_report, check_leave_conflicts, add_calendar_event
)

router = DefaultRouter()
router.register(r'types', LeaveTypeViewSet, basename='leave-type')
router.register(r'balances', LeaveBalanceViewSet, basename='leave-balance')
router.register(r'requests', LeaveRequestViewSet, basename='leave-request')
router.register(r'approvals', LeaveApprovalViewSet, basename='leave-approval')
router.register(r'calendars', LeaveCalendarViewSet, basename='leave-calendar')
router.register(r'holidays', LeaveHolidayViewSet, basename='leave-holiday')
router.register(r'analytics', LeaveAnalyticsViewSet, basename='leave-analytics')
router.register(r'policy', LeavePolicyViewSet, basename='leave-policy')

app_name = 'leave'

urlpatterns = [
    # Viewset routes
    path('', include(router.urls)),
    
    # Additional endpoints
    path('reports/generate/', generate_leave_report, name='generate-leave-report'),
    path('conflicts/check/', check_leave_conflicts, name='check-leave-conflicts'),
    path('calendars/events/add/', add_calendar_event, name='add-calendar-event'),
]
