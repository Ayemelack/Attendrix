"""
Authentication views for Attendrix
"""
from rest_framework import status, generics, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView
from django.contrib.auth import login, logout
from django.utils import timezone
from django.conf import settings
from apps.users.models import User, UserProfile
from apps.institutions.models import Institution
from apps.core.models import ActivityLog, SecurityLog
from apps.authentication.models import LoginAttempt, SecurityToken, TwoFactorDevice
from apps.authentication.serializers import (
    UserRegistrationSerializer, UserLoginSerializer, PasswordChangeSerializer,
    PasswordResetSerializer, PasswordResetConfirmSerializer, UserProfileSerializer,
    TwoFactorSetupSerializer, InstitutionLoginSerializer, RefreshTokenSerializer
)
from apps.core.permissions import IsOwner, IsSuperAdmin
import uuid


class UserRegistrationView(generics.CreateAPIView):
    """
    User registration endpoint
    """
    serializer_class = UserRegistrationSerializer
    permission_classes = [permissions.AllowAny]
    
    def create(self, request, *args, **kwargs):
        """Register new user"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        
        # Generate JWT tokens
        refresh = RefreshToken.for_user(user)
        
        # Create refresh token record
        from apps.core.models import RefreshToken as RefreshTokenModel
        RefreshTokenModel.objects.create(
            user=user,
            token=str(refresh),
            expires_at=timezone.now() + timezone.timedelta(days=7),
            ip_address=self._get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', '')
        )
        
        return Response({
            'message': 'User registered successfully',
            'user': {
                'id': user.id,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'role': user.role,
                'institution': user.institution.name if user.institution else None
            },
            'tokens': {
                'access': str(refresh.access_token),
                'refresh': str(refresh)
            }
        }, status=status.HTTP_201_CREATED)
    
    def _get_client_ip(self, request):
        """Get client IP address"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0]
        return request.META.get('REMOTE_ADDR')


class CustomTokenObtainPairView(TokenObtainPairView):
    """
    Custom JWT token view with enhanced security
    """
    serializer_class = UserLoginSerializer
    permission_classes = [permissions.AllowAny]
    
    def post(self, request, *args, **kwargs):
        """Obtain JWT tokens with security logging"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        user = serializer.validated_data['user']
        remember_me = serializer.validated_data.get('remember_me', False)
        
        # Generate JWT tokens
        refresh = RefreshToken.for_user(user)
        
        # Set token expiration based on remember me
        if remember_me:
            refresh.set_exp(lifetime=timezone.timedelta(days=30))
        
        # Create refresh token record
        from apps.core.models import RefreshToken as RefreshTokenModel
        refresh_token = RefreshTokenModel.objects.create(
            user=user,
            token=str(refresh),
            expires_at=refresh.current_time + refresh.lifetime,
            ip_address=self._get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', '')
        )
        
        # Update user activity
        user.update_last_active()
        
        return Response({
            'message': 'Login successful',
            'user': {
                'id': user.id,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'role': user.role,
                'institution': user.institution.name if user.institution else None,
                'permissions': self._get_user_permissions(user),
                'two_factor_enabled': user.two_factor_enabled
            },
            'tokens': {
                'access': str(refresh.access_token),
                'refresh': str(refresh),
                'expires_in': refresh.lifetime.total_seconds()
            }
        })
    
    def _get_client_ip(self, request):
        """Get client IP address"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0]
        return request.META.get('REMOTE_ADDR')
    
    def _get_user_permissions(self, user):
        """Get user permissions based on role"""
        from apps.authentication.models import Permission, RolePermission
        
        permissions = RolePermission.objects.filter(
            role=user.role,
            is_active=True
        ).select_related('permission')
        
        return [perm.permission.code for perm in permissions]


class TokenRefreshView(generics.GenericAPIView):
    """
    Refresh JWT token
    """
    serializer_class = RefreshTokenSerializer
    permission_classes = [permissions.AllowAny]
    
    def post(self, request, *args, **kwargs):
        """Refresh access token"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        refresh_token = serializer.validated_refresh_token
        user = refresh_token.user
        
        # Generate new tokens
        refresh = RefreshToken.for_user(user)
        
        # Update refresh token
        refresh_token.token = str(refresh)
        refresh_token.expires_at = timezone.now() + timezone.timedelta(days=7)
        refresh_token.last_used = timezone.now()
        refresh_token.usage_count += 1
        refresh_token.save()
        
        return Response({
            'tokens': {
                'access': str(refresh.access_token),
                'refresh': str(refresh),
                'expires_in': refresh.lifetime.total_seconds()
            }
        })


class LogoutView(generics.GenericAPIView):
    """
    Logout user and revoke tokens
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request, *args, **kwargs):
        """Logout user and revoke refresh token"""
        user = request.user
        
        # Get refresh token from request
        refresh_token = request.data.get('refresh_token')
        if refresh_token:
            try:
                from apps.core.models import RefreshToken as RefreshTokenModel
                token = RefreshTokenModel.objects.get(
                    user=user,
                    token=refresh_token,
                    is_active=True
                )
                token.is_active = False
                token.save()
            except RefreshTokenModel.DoesNotExist:
                pass
        
        # Logout user
        logout(request)
        
        # Log activity
        ActivityLog.objects.create(
            user=user,
            institution=user.institution,
            action_type='logout',
            action_description='User logged out',
            ip_address=self._get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            severity='low'
        )
        
        return Response({'message': 'Logout successful'})
    
    def _get_client_ip(self, request):
        """Get client IP address"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0]
        return request.META.get('REMOTE_ADDR')


class PasswordChangeView(generics.GenericAPIView):
    """
    Change user password
    """
    serializer_class = PasswordChangeSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request, *args, **kwargs):
        """Change user password"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        user = serializer.save()
        
        # Revoke all refresh tokens for security
        from apps.core.models import RefreshToken as RefreshTokenModel
        RefreshTokenModel.objects.filter(user=user).update(is_active=False)
        
        return Response({'message': 'Password changed successfully'})


class PasswordResetRequestView(generics.GenericAPIView):
    """
    Request password reset
    """
    serializer_class = PasswordResetSerializer
    permission_classes = [permissions.AllowAny]
    
    def post(self, request, *args, **kwargs):
        """Request password reset"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        token = serializer.save()
        
        if token:
            # Send password reset email (implementation needed)
            self._send_password_reset_email(token)
        
        return Response({
            'message': 'If an account with that email exists, a password reset link has been sent.'
        })
    
    def _send_password_reset_email(self, token):
        """Send password reset email"""
        # This would integrate with email service
        # For now, just log it
        ActivityLog.objects.create(
            user=token.user,
            institution=token.user.institution,
            action_type='password_reset',
            action_description=f'Password reset email sent to {token.user.email}',
            severity='medium'
        )


class PasswordResetConfirmView(generics.GenericAPIView):
    """
    Confirm password reset
    """
    serializer_class = PasswordResetConfirmSerializer
    permission_classes = [permissions.AllowAny]
    
    def post(self, request, *args, **kwargs):
        """Confirm password reset"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        user = serializer.save()
        
        return Response({'message': 'Password reset successful'})


class UserProfileView(generics.RetrieveUpdateAPIView):
    """
    User profile view
    """
    serializer_class = UserProfileSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwner]
    
    def get_object(self):
        """Get user profile"""
        profile, created = UserProfile.objects.get_or_create(user=self.request.user)
        return profile


class TwoFactorSetupView(generics.GenericAPIView):
    """
    Setup two-factor authentication
    """
    serializer_class = TwoFactorSetupSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request, *args, **kwargs):
        """Setup two-factor authentication"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        device = serializer.save()
        
        return Response({
            'message': 'Two-factor authentication setup initiated',
            'device_id': device.id,
            'backup_codes': device.backup_codes  # Only show once
        })


class InstitutionLoginView(generics.GenericAPIView):
    """
    Institution login for multi-tenant access
    """
    serializer_class = InstitutionLoginSerializer
    permission_classes = [permissions.AllowAny]
    
    def post(self, request, *args, **kwargs):
        """Login to institution"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        institution = serializer.validated_institution
        
        return Response({
            'message': 'Institution access granted',
            'institution': {
                'id': institution.id,
                'name': institution.name,
                'code': institution.code,
                'type': institution.institution_type,
                'settings': {
                    'enable_geolocation': institution.enable_geolocation,
                    'enable_device_fingerprinting': institution.enable_device_fingerprinting,
                    'enable_predictive_analytics': institution.enable_predictive_analytics,
                    'enable_gamification': institution.enable_gamification
                }
            }
        })


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def user_info(request):
    """
    Get current user information
    """
    user = request.user
    
    return Response({
        'user': {
            'id': user.id,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'role': user.role,
            'institution': user.institution.name if user.institution else None,
            'department': user.department.name if user.department else None,
            'is_verified': user.is_verified,
            'two_factor_enabled': user.two_factor_enabled,
            'last_login': user.last_login,
            'permissions': get_user_permissions(user)
        }
    })


def get_user_permissions(user):
    """Get user permissions based on role"""
    from apps.authentication.models import Permission, RolePermission
    
    permissions = RolePermission.objects.filter(
        role=user.role,
        is_active=True
    ).select_related('permission')
    
    return [perm.permission.code for perm in permissions]


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def login_history(request):
    """
    Get user login history
    """
    user = request.user
    
    attempts = LoginAttempt.objects.filter(
        user=user
    ).order_by('-created_at')[:20]
    
    history = []
    for attempt in attempts:
        history.append({
            'attempt_type': attempt.attempt_type,
            'status': attempt.status,
            'ip_address': attempt.ip_address,
            'user_agent': attempt.user_agent,
            'created_at': attempt.created_at,
            'failure_reason': attempt.failure_reason,
            'risk_score': attempt.risk_score,
            'is_suspicious': attempt.is_suspicious
        })
    
    return Response({'history': history})


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def revoke_all_sessions(request):
    """
    Revoke all user sessions
    """
    user = request.user
    
    # Revoke all refresh tokens
    from apps.core.models import RefreshToken as RefreshTokenModel
    RefreshTokenModel.objects.filter(user=user).update(is_active=False)
    
    # Deactivate all sessions
    from apps.authentication.models import UserSession
    UserSession.objects.filter(user=user).update(is_active=False)
    
    # Log activity
    ActivityLog.objects.create(
        user=user,
        institution=user.institution,
        action_type='logout',
        action_description='All sessions revoked by user',
        ip_address=request.META.get('REMOTE_ADDR'),
        user_agent=request.META.get('HTTP_USER_AGENT', ''),
        severity='medium'
    )
    
    return Response({'message': 'All sessions revoked successfully'})


@api_view(['GET'])
@permission_classes([IsSuperAdmin])
def system_security_status(request):
    """
    Get system security status (Super Admin only)
    """
    from django.utils import timezone
    from datetime import timedelta
    
    now = timezone.now()
    last_24h = now - timedelta(hours=24)
    
    # Get security statistics
    failed_logins = LoginAttempt.objects.filter(
        status='failed',
        created_at__gte=last_24h
    ).count()
    
    suspicious_logins = LoginAttempt.objects.filter(
        is_suspicious=True,
        created_at__gte=last_24h
    ).count()
    
    security_events = SecurityLog.objects.filter(
        created_at__gte=last_24h
    ).count()
    
    active_sessions = UserSession.objects.filter(
        is_active=True,
        expires_at__gt=now
    ).count()
    
    return Response({
        'security_status': {
            'failed_logins_24h': failed_logins,
            'suspicious_logins_24h': suspicious_logins,
            'security_events_24h': security_events,
            'active_sessions': active_sessions,
            'system_health': 'healthy' if failed_logins < 100 else 'warning'
        }
    })
