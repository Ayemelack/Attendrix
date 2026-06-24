from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    CommunicationGroupViewSet, MessageViewSet, AnnouncementViewSet,
    AnnouncementAcknowledgmentViewSet, MessageThreadViewSet
)

router = DefaultRouter()
router.register(r'groups', CommunicationGroupViewSet, basename='communication-group')
router.register(r'messages', MessageViewSet, basename='message')
router.register(r'announcements', AnnouncementViewSet, basename='announcement')
router.register(r'acknowledgments', AnnouncementAcknowledgmentViewSet, basename='announcement-acknowledgment')
router.register(r'threads', MessageThreadViewSet, basename='message-thread')

urlpatterns = [
    path('', include(router.urls)),
]
