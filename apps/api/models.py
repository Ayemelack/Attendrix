from django.db import models
from django.contrib.auth import get_user_model
from apps.institutions.models import Institution

User = get_user_model()


class APIKey(models.Model):
    """API keys for external integrations"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='api_keys')
    name = models.CharField(max_length=100)
    key = models.CharField(max_length=255, unique=True)
    is_active = models.BooleanField(default=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    last_used = models.DateTimeField(null=True, blank=True)
    usage_count = models.PositiveIntegerField(default=0)
    rate_limit = models.PositiveIntegerField(default=1000, help_text="Requests per hour")
    permissions = models.JSONField(default=list, help_text="List of allowed endpoints")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'API Key'
        verbose_name_plural = 'API Keys'
    
    def __str__(self):
        return f"{self.name} - {self.user.username}"


class Webhook(models.Model):
    """Webhook configurations for external integrations"""
    institution = models.ForeignKey(Institution, on_delete=models.CASCADE, related_name='webhooks')
    name = models.CharField(max_length=100)
    url = models.URLField()
    events = models.JSONField(default=list, help_text="List of events to trigger webhook")
    secret = models.CharField(max_length=255, help_text="Secret for webhook signature verification")
    is_active = models.BooleanField(default=True)
    retry_count = models.PositiveIntegerField(default=3)
    timeout = models.PositiveIntegerField(default=30)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Webhook'
        verbose_name_plural = 'Webhooks'
    
    def __str__(self):
        return f"{self.name} - {self.institution.name}"


class WebhookLog(models.Model):
    """Webhook delivery logs"""
    webhook = models.ForeignKey(Webhook, on_delete=models.CASCADE, related_name='logs')
    event_type = models.CharField(max_length=100)
    payload = models.JSONField()
    response_status = models.PositiveIntegerField(null=True, blank=True)
    response_body = models.TextField(blank=True)
    headers = models.JSONField(default=dict)
    attempt_count = models.PositiveIntegerField(default=1)
    delivered = models.BooleanField(default=False)
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Webhook Log'
        verbose_name_plural = 'Webhook Logs'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.webhook.name} - {self.event_type} ({'Delivered' if self.delivered else 'Failed'})"


class APIUsage(models.Model):
    """API usage tracking"""
    api_key = models.ForeignKey(APIKey, on_delete=models.CASCADE, related_name='usage_logs')
    endpoint = models.CharField(max_length=200)
    method = models.CharField(max_length=10)
    status_code = models.PositiveIntegerField()
    response_time = models.PositiveIntegerField(help_text="Response time in milliseconds")
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'API Usage'
        verbose_name_plural = 'API Usage'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['api_key', 'created_at']),
            models.Index(fields=['endpoint', 'created_at']),
        ]
    
    def __str__(self):
        return f"{self.api_key.name} - {self.method} {self.endpoint}"


class Integration(models.Model):
    """Third-party integrations"""
    institution = models.ForeignKey(Institution, on_delete=models.CASCADE, related_name='integrations')
    name = models.CharField(max_length=100)
    integration_type = models.CharField(max_length=50, choices=[
        ('lms', 'Learning Management System'),
        ('sis', 'Student Information System'),
        ('hr', 'HR System'),
        ('payroll', 'Payroll System'),
        ('calendar', 'Calendar System'),
        ('email', 'Email Service'),
        ('sms', 'SMS Service'),
        ('storage', 'Cloud Storage'),
        ('analytics', 'Analytics Service'),
        ('other', 'Other'),
    ])
    configuration = models.JSONField(default=dict, help_text="Integration-specific configuration")
    is_active = models.BooleanField(default=True)
    last_sync = models.DateTimeField(null=True, blank=True)
    sync_frequency = models.CharField(max_length=20, choices=[
        ('realtime', 'Real-time'),
        ('hourly', 'Hourly'),
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('manual', 'Manual'),
    ], default='daily')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Integration'
        verbose_name_plural = 'Integrations'
        unique_together = ['institution', 'name']
    
    def __str__(self):
        return f"{self.name} - {self.institution.name}"


class IntegrationLog(models.Model):
    """Integration operation logs"""
    integration = models.ForeignKey(Integration, on_delete=models.CASCADE, related_name='logs')
    operation = models.CharField(max_length=100)
    status = models.CharField(max_length=20, choices=[
        ('success', 'Success'),
        ('error', 'Error'),
        ('pending', 'Pending'),
    ])
    request_data = models.JSONField(default=dict)
    response_data = models.JSONField(default=dict)
    error_message = models.TextField(blank=True)
    duration = models.PositiveIntegerField(help_text="Operation duration in milliseconds")
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Integration Log'
        verbose_name_plural = 'Integration Logs'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.integration.name} - {self.operation} ({self.status})"


class APIDocumentation(models.Model):
    """API documentation"""
    endpoint = models.CharField(max_length=200)
    method = models.CharField(max_length=10)
    description = models.TextField()
    parameters = models.JSONField(default=dict)
    response_schema = models.JSONField(default=dict)
    example_request = models.JSONField(default=dict)
    example_response = models.JSONField(default=dict)
    is_public = models.BooleanField(default=True)
    version = models.CharField(max_length=20, default='v1')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'API Documentation'
        verbose_name_plural = 'API Documentation'
        unique_together = ['endpoint', 'method', 'version']
    
    def __str__(self):
        return f"{self.method} {self.endpoint} ({self.version})"
