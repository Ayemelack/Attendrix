"""
Alerts URLs for Attendrix
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.alerts.views import (
    AlertViewSet, NotificationViewSet, NotificationTemplateViewSet,
    NotificationPreferenceViewSet, NotificationQueueViewSet, AlertRuleViewSet,
    send_bulk_notification, notification_statistics, cleanup_notifications
)

router = DefaultRouter()
router.register(r'alerts', AlertViewSet, basename='alert')
router.register(r'notifications', NotificationViewSet, basename='notification')
router.register(r'templates', NotificationTemplateViewSet, basename='notification-template')
router.register(r'preferences', NotificationPreferenceViewSet, basename='notification-preference')
router.register(r'queue', NotificationQueueViewSet, basename='notification-queue')
router.register(r'rules', AlertRuleViewSet, basename='alert-rule')

app_name = 'alerts'

urlpatterns = [
    # Viewset routes
    path('', include(router.urls)),
    
    # Additional endpoints
    path('bulk-send/', send_bulk_notification, name='send-bulk-notification'),
    path('statistics/', notification_statistics, name='notification-statistics'),
    path('cleanup/', cleanup_notifications, name='cleanup-notifications'),
]
