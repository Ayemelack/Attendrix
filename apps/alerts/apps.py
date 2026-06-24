"""
Alerts app configuration
"""
from django.apps import AppConfig


class AlertsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.alerts'
    verbose_name = 'Alerts'
    
    def ready(self):
        """Import signals when app is ready"""
        import apps.alerts.signals
