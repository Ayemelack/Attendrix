"""
Authentication URLs for Attendrix
"""
from django.urls import path
from apps.authentication.views import (
    UserRegistrationView, CustomTokenObtainPairView, TokenRefreshView,
    LogoutView, PasswordChangeView, PasswordResetRequestView, PasswordResetConfirmView,
    UserProfileView, TwoFactorSetupView, InstitutionLoginView,
    user_info, login_history, revoke_all_sessions, system_security_status
)

app_name = 'authentication'

urlpatterns = [
    # Authentication endpoints
    path('register/', UserRegistrationView.as_view(), name='register'),
    path('login/', CustomTokenObtainPairView.as_view(), name='login'),
    path('refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('logout/', LogoutView.as_view(), name='logout'),
    
    # Password management
    path('password/change/', PasswordChangeView.as_view(), name='password_change'),
    path('password/reset/', PasswordResetRequestView.as_view(), name='password_reset'),
    path('password/reset/confirm/', PasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    
    # User profile
    path('profile/', UserProfileView.as_view(), name='user_profile'),
    path('me/', user_info, name='user_info'),
    
    # Two-factor authentication
    path('2fa/setup/', TwoFactorSetupView.as_view(), name='2fa_setup'),
    
    # Multi-tenant access
    path('institution/', InstitutionLoginView.as_view(), name='institution_login'),
    
    # Session management
    path('login-history/', login_history, name='login_history'),
    path('revoke-sessions/', revoke_all_sessions, name='revoke_sessions'),
    
    # Security monitoring (Super Admin only)
    path('security/status/', system_security_status, name='security_status'),
]
