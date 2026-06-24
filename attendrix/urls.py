"""
Attendrix URL Configuration
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import TemplateView
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView

urlpatterns = [
    # Admin
    path('admin/', admin.site.urls),
    
    # API Documentation
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
    
    # API endpoints
    path('api/v1/', include('apps.api.urls')),
    
    # Authentication endpoints
    path('auth/', include('apps.authentication.urls')),
    
    # Application endpoints
    path('', include('apps.core.urls')),
    path('dashboard/', include('apps.core.urls')),
    path('attendance/', include('apps.attendance.urls')),
    path('scheduling/', include('apps.scheduling.urls')),
    path('analytics/', include('apps.analytics.urls')),
    path('alerts/', include('apps.alerts.urls')),
    path('communication/', include('apps.communication.urls')),
    path('leave/', include('apps.leave_management.urls')),
    path('surveys/', include('apps.surveys.urls')),
    path('gamification/', include('apps.gamification.urls')),
    
    # Health check
    path('health/', TemplateView.as_view(template_name='health.html'), name='health'),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

# Custom error pages
handler404 = 'apps.core.views.custom_404'
handler500 = 'apps.core.views.custom_500'
handler403 = 'apps.core.views.custom_403'
