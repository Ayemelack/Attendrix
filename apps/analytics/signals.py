"""
Analytics signals for Attendrix
"""
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.utils import timezone
from apps.analytics.models import (
    AttendanceAnalytics, StudentPerformanceAnalytics, InstitutionalHealthIndex,
    PredictiveModel, PredictionResult
)
from apps.analytics.tasks import (
    generate_attendance_analytics, calculate_institutional_health,
    generate_performance_predictions
)
import logging

logger = logging.getLogger(__name__)


@receiver(post_save, sender=AttendanceAnalytics)
def attendance_analytics_post_save(sender, instance, created, **kwargs):
    """
    Handle attendance analytics post-save operations
    """
    if created:
        # Log creation
        logger.info(f"Attendance analytics created: {instance.analytics_type} for {instance.reference_date}")
        
        # Check for high-risk patterns and trigger alerts
        if instance.dropout_risk_score >= 80:
            from apps.attendance.models import AttendanceAlert
            from apps.users.models import User
            
            try:
                student = User.objects.get(id=instance.reference_id) if instance.reference_id else None
                
                if student:
                    AttendanceAlert.objects.get_or_create(
                        institution=instance.institution,
                        student=student,
                        alert_type='dropout_risk',
                        severity='critical',
                        defaults={
                            'title': 'High Dropout Risk Detected',
                            'description': f'Student {student.get_full_name()} shows high dropout risk ({instance.dropout_risk_score}% threshold)',
                            'threshold_value=70.0,
                            'actual_value': instance.dropout_risk_score,
                            'alert_data': {
                                'analytics_id': instance.id,
                                'attendance_rate': instance.attendance_rate,
                                'trend_direction': instance.trend_direction
                            }
                        }
                    )
                    
                    logger.warning(f"High dropout risk alert created for student {student.get_full_name()}")
            except User.DoesNotExist:
                pass
    
    else:
        # Log update
        logger.info(f"Attendance analytics updated: {instance.analytics_type} for {instance.reference_date}")


@receiver(post_save, sender=StudentPerformanceAnalytics)
def student_performance_analytics_post_save(sender, instance, created, **kwargs):
    """
    Handle student performance analytics post-save operations
    """
    if created:
        # Log creation
        logger.info(f"Student performance analytics created for {instance.student.get_full_name()} on {instance.analysis_date}")
        
        # Check for performance concerns
        if instance.success_probability < 50:
            from apps.attendance.models import AttendanceAlert
            
            AttendanceAlert.objects.get_or_create(
                institution=instance.institution,
                student=instance.student,
                course=instance.course,
                alert_type='performance_decline',
                severity='warning',
                defaults={
                    'title': 'Performance Decline Detected',
                    'description': f'Student {instance.student.get_full_name()} shows performance decline',
                    'threshold_value=50.0,
                    'actual_value': instance.success_probability,
                    'alert_data': {
                        'analytics_id': instance.id,
                        'current_gpa': instance.current_gpa,
                        'gpa_trend': instance.gpa_trend,
                        'success_probability': instance.success_probability
                    }
                }
            )
            
            logger.warning(f"Performance decline alert created for student {instance.student.get_full_name()}")
    
    else:
        # Log update
        logger.info(f"Student performance analytics updated for {instance.student.get_full_name()}")


@receiver(post_save, sender=InstitutionalHealthIndex)
def institutional_health_post_save(sender, instance, created, **kwargs):
    """
    Handle institutional health index post-save operations
    """
    if created:
        # Log creation
        logger.info(f"Institutional health index calculated for {instance.institution.name} on {instance.calculation_date}")
        logger.info(f"Health score: {instance.health_score}, Grade: {instance.health_grade}")
        
        # Check for critical health issues
        if instance.health_score < 60:
            from apps.alerts.models import Alert
            from apps.users.models import User
            
            # Notify institution admins
            admins = User.objects.filter(
                institution=instance.institution,
                role='institution_admin'
            )
            
            for admin in admins:
                Alert.objects.create(
                    institution=instance.institution,
                    title='Critical Institutional Health Alert',
                    message=f'Institution health score is {instance.health_score} (Grade: {instance.health_grade})',
                    alert_type='institutional_health',
                    severity='critical',
                    metadata={
                        'health_score': instance.health_score,
                        'health_grade': instance.health_grade,
                        'critical_issues': instance.critical_issues
                    }
                )
            
            logger.critical(f"Critical institutional health alert for {instance.institution.name}: {instance.health_score}")
    
    else:
        # Log update
        logger.info(f"Institutional health index updated for {instance.institution.name}")


@receiver(post_save, sender=PredictiveModel)
def predictive_model_post_save(sender, instance, created, **kwargs):
    """
    Handle predictive model post-save operations
    """
    if created:
        # Log creation
        logger.info(f"Predictive model created: {instance.model_name} - {instance.model_type}")
        
        # Check if model is deployed and has good performance
        if instance.is_deployed and instance.accuracy and instance.accuracy > 0.8:
            logger.info(f"High-performant model deployed: {instance.model_name} (accuracy: {instance.accuracy:.2f})")
        elif instance.is_deployed and instance.accuracy and instance.accuracy < 0.6:
            logger.warning(f"Low-performant model deployed: {instance.model_name} (accuracy: {instance.accuracy:.2f})")
    
    else:
        # Log update
        logger.info(f"Predictive model updated: {instance.model_name}")


@receiver(post_save, sender=PredictionResult)
def prediction_result_post_save(sender, instance, created, **kwargs):
    """
    Handle prediction result post-save operations
    """
    if created:
        # Log prediction
        logger.info(f"Prediction generated: {instance.model.model_name} for {instance.student.get_full_name() if instance.student else 'Unknown'}")
        
        # Check for high-risk predictions
        if instance.prediction_value > 80:
            from apps.attendance.models import AttendanceAlert
            
            if instance.student:
                AttendanceAlert.objects.get_or_create(
                    institution=instance.institution,
                    student=instance.student,
                    course=instance.course,
                    alert_type='prediction_alert',
                    severity='high',
                    defaults={
                        'title': 'High-Risk Prediction Alert',
                        description=f'High-risk prediction for {instance.student.get_full_name()}: {instance.predicted_class}',
                        'threshold_value=70.0,
                        'actual_value': instance.prediction_value,
                        'alert_data': {
                            'prediction_result_id': instance.id,
                            'model': instance.model.model_name,
                            'confidence': instance.confidence_score
                        }
                    }
                )
            
            logger.warning(f"High-risk prediction alert created for student {instance.student.get_full_name() if instance.student else 'Unknown'}")
    
    else:
        # Log update
        logger.info(f"Prediction result updated: {instance.id}")


@receiver(post_save, sender=AttendanceSession)
def trigger_analytics_on_session_completion(sender, instance, **kwargs):
    """
    Trigger analytics when attendance session is completed
    """
    # Check if session was just completed (deactivated)
    if hasattr(instance, '_old_is_active') and instance._old_is_active and not instance.is_active:
        # Session was just closed, generate analytics
        generate_attendance_analytics.delay(
            instance.institution.id,
            'course',
            instance.start_time.date(),
            instance.end_time.date()
        )
        
        logger.info(f"Triggered analytics generation for completed session: {instance.title}")


@receiver(post_save, sender=AttendanceSession)
def store_old_active_state(sender, instance, **kwargs):
    """
    Store old active state for comparison
    """
    if instance.pk:
        try:
            old_instance = AttendanceSession.objects.get(pk=instance.pk)
            instance._old_is_active = old_instance.is_active
        except AttendanceSession.DoesNotExist:
            pass


# Import Q for database queries
from django.db.models import Q
