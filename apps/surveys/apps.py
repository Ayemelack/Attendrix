"""
Surveys app configuration
"""
from django.apps import AppConfig


class SurveysConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.surveys'
    verbose_name = 'Surveys'
    
    def ready(self):
        """Import signals when app is ready"""
        import apps.surveys.signals
