from django.apps import AppConfig


class LeaveManagementConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.leave_management'
    verbose_name = 'Leave Management'
    
    def ready(self):
        try:
            import apps.leave_management.signals
        except ImportError:
            pass
