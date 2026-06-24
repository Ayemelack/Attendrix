"""
Authentication serializers for Attendrix API
"""
from rest_framework import serializers
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.utils import timezone
from apps.users.models import User, UserProfile
from apps.institutions.models import Institution
from apps.authentication.models import LoginAttempt, SecurityToken, TwoFactorDevice
from apps.core.models import ActivityLog, SecurityLog
import uuid


class UserRegistrationSerializer(serializers.ModelSerializer):
    """
    User registration serializer
    """
    password = serializers.CharField(write_only=True, validators=[validate_password])
    password_confirm = serializers.CharField(write_only=True)
    institution_code = serializers.CharField(write_only=True, required=False)
    
    class Meta:
        model = User
        fields = [
            'email', 'first_name', 'last_name', 'password', 'password_confirm',
            'role', 'phone', 'institution_code'
        ]
    
    def validate(self, attrs):
        """Validate registration data"""
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError("Passwords don't match")
        
        # Validate institution code for non-super admin roles
        if attrs['role'] != 'super_admin' and not attrs.get('institution_code'):
            raise serializers.ValidationError("Institution code is required")
        
        # Validate institution exists and is active
        institution_code = attrs.get('institution_code')
        if institution_code:
            try:
                institution = Institution.objects.get(
                    code=institution_code,
                    is_active=True
                )
                if not institution.is_subscription_active:
                    raise serializers.ValidationError("Institution subscription is not active")
                attrs['institution'] = institution
            except Institution.DoesNotExist:
                raise serializers.ValidationError("Invalid institution code")
        
        return attrs
    
    def create(self, validated_data):
        """Create user with profile"""
        validated_data.pop('password_confirm')
        validated_data.pop('institution_code', None)
        
        # Create user
        user = User.objects.create_user(
            email=validated_data['email'],
            password=validated_data['password'],
            **{k: v for k, v in validated_data.items() if k != 'password'}
        )
        
        # Create user profile
        UserProfile.objects.create(user=user)
        
        # Log activity
        ActivityLog.objects.create(
            user=user,
            institution=user.institution,
            action_type='create',
            action_description=f'User account created for {user.email}',
            severity='low'
        )
        
        return user


class UserLoginSerializer(serializers.Serializer):
    """
    User login serializer
    """
    email = serializers.EmailField()
    password = serializers.CharField()
    institution_code = serializers.CharField(required=False)
    two_factor_code = serializers.CharField(required=False)
    remember_me = serializers.BooleanField(default=False)
    
    def validate(self, attrs):
        """Validate login credentials"""
        email = attrs.get('email').lower()
        password = attrs.get('password')
        institution_code = attrs.get('institution_code')
        
        # Authenticate user
        user = authenticate(
            request=self.context.get('request'),
            username=email,
            password=password
        )
        
        if not user:
            raise serializers.ValidationError("Invalid credentials")
        
        # Check institution code for multi-tenant
        if institution_code and user.institution:
            if user.institution.code != institution_code:
                raise serializers.ValidationError("Invalid institution code")
        
        # Check two-factor authentication
        if user.two_factor_enabled:
            two_factor_code = attrs.get('two_factor_code')
            if not two_factor_code:
                raise serializers.ValidationError("Two-factor code is required")
            
            if not self._verify_two_factor(user, two_factor_code):
                raise serializers.ValidationError("Invalid two-factor code")
        
        attrs['user'] = user
        return attrs
    
    def _verify_two_factor(self, user, code):
        """Verify two-factor authentication code"""
        # This would integrate with TOTP, SMS, or email verification
        # For now, return True as placeholder
        return True


class PasswordChangeSerializer(serializers.Serializer):
    """
    Password change serializer
    """
    current_password = serializers.CharField()
    new_password = serializers.CharField(validators=[validate_password])
    new_password_confirm = serializers.CharField()
    
    def validate_current_password(self, value):
        """Validate current password"""
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError("Current password is incorrect")
        return value
    
    def validate(self, attrs):
        """Validate password change"""
        if attrs['new_password'] != attrs['new_password_confirm']:
            raise serializers.ValidationError("New passwords don't match")
        return attrs
    
    def save(self):
        """Change user password"""
        user = self.context['request'].user
        user.set_password(self.validated_data['new_password'])
        user.password_changed_at = timezone.now()
        user.save()
        
        # Log activity
        ActivityLog.objects.create(
            user=user,
            institution=user.institution,
            action_type='password_change',
            action_description='User changed password',
            severity='medium'
        )
        
        return user


class PasswordResetSerializer(serializers.Serializer):
    """
    Password reset request serializer
    """
    email = serializers.EmailField()
    institution_code = serializers.CharField(required=False)
    
    def validate(self, attrs):
        """Validate password reset request"""
        email = attrs.get('email').lower()
        institution_code = attrs.get('institution_code')
        
        try:
            user = User.objects.get(email=email)
            
            # Check institution if provided
            if institution_code and user.institution:
                if user.institution.code != institution_code:
                    raise serializers.ValidationError("Invalid institution code")
            
            attrs['user'] = user
            return attrs
            
        except User.DoesNotExist:
            # Don't reveal if user exists
            return attrs
    
    def save(self):
        """Create password reset token"""
        user = self.validated_data.get('user')
        if not user:
            return  # User doesn't exist, but don't reveal this
        
        # Create security token
        token = SecurityToken.objects.create(
            user=user,
            token_type='password_reset',
            token=str(uuid.uuid4()),
            expires_at=timezone.now() + timezone.timedelta(hours=24),
            ip_address=self._get_client_ip(),
            user_agent=self.context.get('request').META.get('HTTP_USER_AGENT', '')
        )
        
        # Log activity
        ActivityLog.objects.create(
            user=user,
            institution=user.institution,
            action_type='password_reset',
            action_description='Password reset requested',
            severity='medium'
        )
        
        return token
    
    def _get_client_ip(self):
        """Get client IP address"""
        request = self.context.get('request')
        if request:
            x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
            if x_forwarded_for:
                return x_forwarded_for.split(',')[0]
            return request.META.get('REMOTE_ADDR')
        return None


class PasswordResetConfirmSerializer(serializers.Serializer):
    """
    Password reset confirmation serializer
    """
    token = serializers.CharField()
    new_password = serializers.CharField(validators=[validate_password])
    new_password_confirm = serializers.CharField()
    
    def validate_token(self, value):
        """Validate reset token"""
        try:
            token = SecurityToken.objects.get(
                token=value,
                token_type='password_reset',
                is_used=False
            )
            
            if token.is_expired:
                raise serializers.ValidationError("Token has expired")
            
            self.validated_token = token
            return value
            
        except SecurityToken.DoesNotExist:
            raise serializers.ValidationError("Invalid token")
    
    def validate(self, attrs):
        """Validate password reset confirmation"""
        if attrs['new_password'] != attrs['new_password_confirm']:
            raise serializers.ValidationError("Passwords don't match")
        return attrs
    
    def save(self):
        """Reset user password"""
        token = self.validated_token
        user = token.user
        
        # Set new password
        user.set_password(self.validated_data['new_password'])
        user.password_changed_at = timezone.now()
        user.save()
        
        # Mark token as used
        token.is_used = True
        token.used_at = timezone.now()
        token.save()
        
        # Log activity
        ActivityLog.objects.create(
            user=user,
            institution=user.institution,
            action_type='password_change',
            action_description='Password reset completed',
            severity='medium'
        )
        
        return user


class UserProfileSerializer(serializers.ModelSerializer):
    """
    User profile serializer
    """
    user_email = serializers.EmailField(source='user.email', read_only=True)
    user_role = serializers.CharField(source='user.role', read_only=True)
    user_institution = serializers.CharField(source='user.institution.name', read_only=True)
    
    class Meta:
        model = UserProfile
        fields = [
            'user_email', 'user_role', 'user_institution',
            'bio', 'profile_picture', 'date_of_birth', 'place_of_birth',
            'nationality', 'emergency_contact_name', 'emergency_contact_phone',
            'emergency_contact_relationship', 'admission_date', 'graduation_date',
            'gpa', 'academic_level', 'hire_date', 'employment_type', 'salary',
            'linkedin_url', 'twitter_url', 'website_url', 'theme', 'dashboard_layout'
        ]
        read_only_fields = ['profile_picture']


class TwoFactorSetupSerializer(serializers.Serializer):
    """
    Two-factor authentication setup serializer
    """
    device_type = serializers.ChoiceField(choices=TwoFactorDevice.DEVICE_TYPES)
    phone_number = serializers.CharField(required=False)
    email_address = serializers.EmailField(required=False)
    
    def validate(self, attrs):
        """Validate two-factor setup"""
        device_type = attrs.get('device_type')
        
        if device_type == 'sms' and not attrs.get('phone_number'):
            raise serializers.ValidationError("Phone number is required for SMS authentication")
        
        if device_type == 'email' and not attrs.get('email_address'):
            raise serializers.ValidationError("Email address is required for email authentication")
        
        return attrs
    
    def save(self):
        """Setup two-factor authentication"""
        user = self.context['request'].user
        device_type = self.validated_data['device_type']
        
        # Create two-factor device
        device = TwoFactorDevice.objects.create(
            user=user,
            device_type=device_type,
            device_name=f"{device_type.title()} Device",
            phone_number=self.validated_data.get('phone_number', ''),
            email_address=self.validated_data.get('email_address', ''),
            secret_key=self._generate_secret_key(),
            backup_codes=self._generate_backup_codes()
        )
        
        # Enable two-factor on user
        user.two_factor_enabled = True
        user.save()
        
        # Log activity
        ActivityLog.objects.create(
            user=user,
            institution=user.institution,
            action_type='create',
            action_description=f'Two-factor authentication enabled: {device_type}',
            severity='medium'
        )
        
        return device
    
    def _generate_secret_key(self):
        """Generate secret key for TOTP"""
        return str(uuid.uuid4()).replace('-', '')
    
    def _generate_backup_codes(self):
        """Generate backup codes"""
        return [str(uuid.uuid4())[:8] for _ in range(10)]


class InstitutionLoginSerializer(serializers.Serializer):
    """
    Institution login serializer for multi-tenant access
    """
    institution_code = serializers.CharField()
    
    def validate_institution_code(self, value):
        """Validate institution code"""
        try:
            institution = Institution.objects.get(
                code=value.upper(),
                is_active=True
            )
            
            if not institution.is_subscription_active:
                raise serializers.ValidationError("Institution subscription is not active")
            
            self.validated_institution = institution
            return value
            
        except Institution.DoesNotExist:
            raise serializers.ValidationError("Invalid institution code")


class RefreshTokenSerializer(serializers.Serializer):
    """
    Refresh token serializer
    """
    refresh_token = serializers.CharField()
    
    def validate_refresh_token(self, value):
        """Validate refresh token"""
        try:
            from apps.core.models import RefreshToken
            token = RefreshToken.objects.get(
                token=value,
                is_active=True
            )
            
            if token.expires_at < timezone.now():
                raise serializers.ValidationError("Refresh token has expired")
            
            self.validated_refresh_token = token
            return value
            
        except RefreshToken.DoesNotExist:
            raise serializers.ValidationError("Invalid refresh token")
