"""
Analytics tasks for Attendrix - Background processing for analytics and intelligence
"""
from celery import shared_task
from django.utils import timezone
from django.db.models import Q, Count, Avg, Sum, StdDev, F
from django.db.models.functions import Extract
from datetime import datetime, timedelta
from apps.core.models import ActivityLog
from apps.analytics.models import (
    AttendanceAnalytics, StudentPerformanceAnalytics, InstitutionalHealthIndex,
    PredictiveModel, PredictionResult, AnalyticsReport
)
from apps.attendance.models import AttendanceRecord, AttendanceSession
from apps.courses.models import Course
from apps.users.models import User
from apps.departments.models import Department
import logging
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.linear_model import LinearRegression, LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, roc_auc_score
import pickle
import json

logger = logging.getLogger(__name__)


@shared_task
def generate_attendance_analytics(institution_id, analytics_type='all', start_date=None, end_date=None):
    """
    Generate attendance analytics for institution
    """
    try:
        if not start_date:
            start_date = timezone.now().date() - timedelta(days=30)
        if not end_date:
            end_date = timezone.now().date()
        
        # Get attendance records
        records = AttendanceRecord.objects.filter(
            institution_id=institution_id,
            marked_at__date__gte=start_date,
            marked_at__date__lte=end_date,
            is_deleted=False
        ).select_related('student', 'session', 'session__course')
        
        analytics_generated = 0
        
        if analytics_type in ['all', 'student']:
            # Generate student analytics
            students = records.values('student_id').distinct()
            
            for student_data in students:
                student_id = student_data['student_id']
                student_records = records.filter(student_id=student_id)
                
                if student_records.exists():
                    _generate_student_analytics(student_id, student_records, start_date, end_date)
                    analytics_generated += 1
        
        if analytics_type in ['all', 'course']:
            # Generate course analytics
            courses = records.values('session__course_id').distinct()
            
            for course_data in courses:
                course_id = course_data['session__course_id']
                course_records = records.filter(session__course_id=course_id)
                
                if course_records.exists():
                    _generate_course_analytics(course_id, course_records, start_date, end_date)
                    analytics_generated += 1
        
        if analytics_type in ['all', 'lecturer']:
            # Generate lecturer analytics
            lecturers = records.values('session__lecturer_id').distinct()
            
            for lecturer_data in lecturers:
                lecturer_id = lecturer_data['session__lecturer_id']
                lecturer_records = records.filter(session__lecturer_id=lecturer_id)
                
                if lecturer_records.exists():
                    _generate_lecturer_analytics(lecturer_id, lecturer_records, start_date, end_date)
                    analytics_generated += 1
        
        if analytics_type in ['all', 'department']:
            # Generate department analytics
            departments = records.values('session__course__department_id').distinct()
            
            for dept_data in departments:
                dept_id = dept_data['session__course__department_id']
                dept_records = records.filter(session__course__department_id=dept_id)
                
                if dept_records.exists():
                    _generate_department_analytics(dept_id, dept_records, start_date, end_date)
                    analytics_generated += 1
        
        if analytics_type in ['all', 'institution']:
            # Generate institution analytics
            _generate_institution_analytics(institution_id, records, start_date, end_date)
            analytics_generated += 1
        
        logger.info(f"Generated {analytics_generated} attendance analytics for institution {institution_id}")
        return analytics_generated
        
    except Exception as e:
        logger.error(f"Error generating attendance analytics: {e}")
        return 0


def _generate_student_analytics(student_id, records, start_date, end_date):
    """Generate analytics for a specific student"""
    # Calculate basic statistics
    total_records = records.count()
    present_count = records.filter(status='present').count()
    absent_count = records.filter(status='absent').count()
    late_count = records.filter(status='late').count()
    excused_count = records.filter(status='excused').count()
    
    attendance_rate = (present_count / total_records * 100) if total_records > 0 else 0
    punctuality_rate = ((present_count - late_count) / total_records * 100) if total_records > 0 else 0
    
    # Calculate trends
    previous_period_start = start_date - timedelta(days=30)
    previous_period_end = start_date - timedelta(days=1)
    
    previous_records = AttendanceRecord.objects.filter(
        student_id=student_id,
        marked_at__date__gte=previous_period_start,
        marked_at__date__lte=previous_period_end,
        is_deleted=False
    )
    
    attendance_trend = 0.0
    if previous_records.exists():
        previous_attendance_rate = (
            previous_records.filter(status='present').count() / previous_records.count() * 100
        )
        attendance_trend = attendance_rate - previous_attendance_rate
    
    # Determine trend direction
    if attendance_trend > 5:
        trend_direction = 'improving'
    elif attendance_trend < -5:
        trend_direction = 'declining'
    else:
        trend_direction = 'stable'
    
    # Calculate risk scores
    dropout_risk_score = _calculate_dropout_risk(attendance_rate, attendance_trend)
    performance_risk_score = _calculate_performance_risk(attendance_rate, punctuality_rate)
    
    # Determine intervention priority
    if dropout_risk_score >= 80:
        intervention_priority = 'critical'
    elif dropout_risk_score >= 60:
        intervention_priority = 'high'
    elif dropout_risk_score >= 40:
        intervention_priority = 'medium'
    else:
        intervention_priority = 'low'
    
    # Create or update analytics record
    AttendanceAnalytics.objects.update_or_create(
        institution_id=records.first().institution_id,
        analytics_type='student',
        reference_id=student_id,
        reference_date=end_date,
        defaults={
            'total_sessions': total_records,
            'total_attendance_records': total_records,
            'present_count': present_count,
            'absent_count': absent_count,
            'late_count': late_count,
            'excused_count': excused_count,
            'attendance_rate': attendance_rate,
            'punctuality_rate': punctuality_rate,
            'engagement_score': (attendance_rate * 0.7 + punctuality_rate * 0.3),
            'consistency_score': 100 - abs(attendance_trend),
            'attendance_trend': attendance_trend,
            'trend_direction': trend_direction,
            'dropout_risk_score': dropout_risk_score,
            'performance_risk_score': performance_risk_score,
            'intervention_priority': intervention_priority
        }
    )


def _generate_course_analytics(course_id, records, start_date, end_date):
    """Generate analytics for a specific course"""
    # Calculate basic statistics
    total_records = records.count()
    present_count = records.filter(status='present').count()
    absent_count = records.filter(status='absent').count()
    late_count = records.filter(status='late').count()
    excused_count = records.filter(status='excused').count()
    
    attendance_rate = (present_count / total_records * 100) if total_records > 0 else 0
    punctuality_rate = ((present_count - late_count) / total_records * 100) if total_records > 0 else 0
    
    # Get unique students
    unique_students = records.values('student_id').distinct().count()
    
    # Create or update analytics record
    AttendanceAnalytics.objects.update_or_create(
        institution_id=records.first().institution_id,
        analytics_type='course',
        reference_id=course_id,
        reference_date=end_date,
        defaults={
            'total_sessions': records.values('session_id').distinct().count(),
            'total_attendance_records': total_records,
            'present_count': present_count,
            'absent_count': absent_count,
            'late_count': late_count,
            'excused_count': excused_count,
            'attendance_rate': attendance_rate,
            'punctuality_rate': punctuality_rate,
            'engagement_score': (attendance_rate * 0.7 + punctuality_rate * 0.3),
            'dropout_risk_score': 0,  # Not applicable for courses
            'performance_risk_score': 0,  # Not applicable for courses
            'intervention_priority': 'low'
        }
    )


def _generate_lecturer_analytics(lecturer_id, records, start_date, end_date):
    """Generate analytics for a specific lecturer"""
    # Calculate basic statistics
    total_records = records.count()
    present_count = records.filter(status='present').count()
    absent_count = records.filter(status='absent').count()
    late_count = records.filter(status='late').count()
    excused_count = records.filter(status='excused').count()
    
    attendance_rate = (present_count / total_records * 100) if total_records > 0 else 0
    punctuality_rate = ((present_count - late_count) / total_records * 100) if total_records > 0 else 0
    
    # Create or update analytics record
    AttendanceAnalytics.objects.update_or_create(
        institution_id=records.first().institution_id,
        analytics_type='lecturer',
        reference_id=lecturer_id,
        reference_date=end_date,
        defaults={
            'total_sessions': records.values('session_id').distinct().count(),
            'total_attendance_records': total_records,
            'present_count': present_count,
            'absent_count': absent_count,
            'late_count': late_count,
            'excused_count': excused_count,
            'attendance_rate': attendance_rate,
            'punctuality_rate': punctuality_rate,
            'engagement_score': (attendance_rate * 0.7 + punctuality_rate * 0.3),
            'dropout_risk_score': 0,  # Not applicable for lecturers
            'performance_risk_score': 0,  # Not applicable for lecturers
            'intervention_priority': 'low'
        }
    )


def _generate_department_analytics(department_id, records, start_date, end_date):
    """Generate analytics for a specific department"""
    # Calculate basic statistics
    total_records = records.count()
    present_count = records.filter(status='present').count()
    absent_count = records.filter(status='absent').count()
    late_count = records.filter(status='late').count()
    excused_count = records.filter(status='excused').count()
    
    attendance_rate = (present_count / total_records * 100) if total_records > 0 else 0
    punctuality_rate = ((present_count - late_count) / total_records * 100) if total_records > 0 else 0
    
    # Create or update analytics record
    AttendanceAnalytics.objects.update_or_create(
        institution_id=records.first().institution_id,
        analytics_type='department',
        reference_id=department_id,
        reference_date=end_date,
        defaults={
            'total_sessions': records.values('session_id').distinct().count(),
            'total_attendance_records': total_records,
            'present_count': present_count,
            'absent_count': absent_count,
            'late_count': late_count,
            'excused_count': excused_count,
            'attendance_rate': attendance_rate,
            'punctuality_rate': punctuality_rate,
            'engagement_score': (attendance_rate * 0.7 + punctuality_rate * 0.3),
            'dropout_risk_score': 0,  # Not applicable for departments
            'performance_risk_score': 0,  # Not applicable for departments
            'intervention_priority': 'low'
        }
    )


def _generate_institution_analytics(institution_id, records, start_date, end_date):
    """Generate institutional analytics"""
    # Calculate basic statistics
    total_records = records.count()
    present_count = records.filter(status='present').count()
    absent_count = records.filter(status='absent').count()
    late_count = records.filter(status='late').count()
    excused_count = records.filter(status='excused').count()
    
    attendance_rate = (present_count / total_records * 100) if total_records > 0 else 0
    punctuality_rate = ((present_count - late_count) / total_records * 100) if total_records > 0 else 0
    
    # Create or update analytics record
    AttendanceAnalytics.objects.update_or_create(
        institution_id=institution_id,
        analytics_type='institution',
        reference_id=None,
        reference_date=end_date,
        defaults={
            'total_sessions': records.values('session_id').distinct().count(),
            'total_attendance_records': total_records,
            'present_count': present_count,
            'absent_count': absent_count,
            'late_count': late_count,
            'excused_count': excused_count,
            'attendance_rate': attendance_rate,
            'punctuality_rate': punctuality_rate,
            'engagement_score': (attendance_rate * 0.7 + punctuality_rate * 0.3),
            'dropout_risk_score': 0,  # Not applicable for institution level
            'performance_risk_score': 0,  # Not applicable for institution level
            'intervention_priority': 'low'
        }
    )


def _calculate_dropout_risk(attendance_rate, attendance_trend):
    """Calculate dropout risk score"""
    risk_score = 0
    
    # Base risk from attendance rate
    if attendance_rate < 50:
        risk_score += 40
    elif attendance_rate < 60:
        risk_score += 30
    elif attendance_rate < 70:
        risk_score += 20
    elif attendance_rate < 80:
        risk_score += 10
    
    # Additional risk from trend
    if attendance_trend < -10:
        risk_score += 30
    elif attendance_trend < -5:
        risk_score += 20
    elif attendance_trend < -2:
        risk_score += 10
    
    return min(100, risk_score)


def _calculate_performance_risk(attendance_rate, punctuality_rate):
    """Calculate performance risk score"""
    risk_score = 0
    
    # Base risk from attendance rate
    if attendance_rate < 60:
        risk_score += 30
    elif attendance_rate < 70:
        risk_score += 20
    elif attendance_rate < 80:
        risk_score += 10
    
    # Additional risk from punctuality
    if punctuality_rate < 70:
        risk_score += 20
    elif punctuality_rate < 80:
        risk_score += 10
    
    return min(100, risk_score)


@shared_task
def calculate_institutional_health(institution_id):
    """
    Calculate institutional health index
    """
    try:
        # Get current date
        today = timezone.now().date()
        
        # Get attendance analytics for last 30 days
        start_date = today - timedelta(days=30)
        
        attendance_analytics = AttendanceAnalytics.objects.filter(
            institution_id=institution_id,
            reference_date__gte=start_date,
            reference_date__lte=today
        )
        
        if not attendance_analytics.exists():
            logger.warning(f"No attendance data found for institution {institution_id}")
            return 0
        
        # Calculate component scores
        attendance_health = attendance_analytics.aggregate(
            avg_rate=Avg('attendance_rate')
        )['avg_rate'] or 0
        
        # Academic performance (placeholder - would integrate with grades)
        academic_performance = 75.0  # Placeholder
        
        # Student engagement
        student_engagement = attendance_analytics.aggregate(
            avg_engagement=Avg('engagement_score')
        )['avg_engagement'] or 0
        
        # Faculty performance (placeholder)
        faculty_performance = 80.0  # Placeholder
        
        # Operational efficiency (placeholder)
        operational_efficiency = 85.0  # Placeholder
        
        # Security compliance (placeholder)
        security_compliance = 90.0  # Placeholder
        
        # Calculate overall health score
        weights = {
            'attendance_health': 0.25,
            'academic_performance': 0.25,
            'student_engagement': 0.20,
            'faculty_performance': 0.15,
            'operational_efficiency': 0.10,
            'security_compliance': 0.05
        }
        
        health_score = (
            attendance_health * weights['attendance_health'] +
            academic_performance * weights['academic_performance'] +
            student_engagement * weights['student_engagement'] +
            faculty_performance * weights['faculty_performance'] +
            operational_efficiency * weights['operational_efficiency'] +
            security_compliance * weights['security_compliance']
        )
        
        # Determine grade
        if health_score >= 95:
            health_grade = 'A+'
        elif health_score >= 90:
            health_grade = 'A'
        elif health_grade >= 85:
            health_grade = 'B+'
        elif health_grade >= 80:
            health_grade = 'B'
        elif health_grade >= 75:
            health_grade = 'C+'
        elif health_grade >= 70:
            health_grade = 'C'
        elif health_grade >= 60:
            health_grade = 'D'
        else:
            health_grade = 'F'
        
        # Get key metrics
        total_students = User.objects.filter(
            institution_id=institution_id,
            role='student',
            is_active=True
        ).count()
        
        total_courses = Course.objects.filter(
            institution_id=institution_id,
            is_deleted=False
        ).count()
        
        total_lecturers = User.objects.filter(
            institution_id=institution_id,
            role='lecturer',
            is_active=True
        ).count()
        
        # Create or update health index
        health_index, created = InstitutionalHealthIndex.objects.update_or_create(
            institution_id=institution_id,
            calculation_date=today,
            defaults={
                'attendance_health': attendance_health,
                'academic_performance': academic_performance,
                'student_engagement': student_engagement,
                'faculty_performance': faculty_performance,
                'operational_efficiency': operational_efficiency,
                'security_compliance': security_compliance,
                'health_score': health_score,
                'health_grade': health_grade,
                'total_students': total_students,
                'total_courses': total_courses,
                'total_lecturers': total_lecturers,
                'average_attendance_rate': attendance_health,
                'average_gpa': academic_performance,
                'retention_rate': 95.0  # Placeholder
            }
        )
        
        # Calculate trend
        if not created:
            previous_health = InstitutionalHealthIndex.objects.filter(
                institution_id=institution_id,
                calculation_date__lt=today
            ).order_by('-calculation_date').first()
            
            if previous_health:
                health_index.score_change = health_score - previous_health.health_score
                
                if health_index.score_change > 2:
                    health_index.trend_direction = 'improving'
                elif health_index.score_change < -2:
                    health_index.trend_direction = 'declining'
                else:
                    health_index.trend_direction = 'stable'
                
                health_index.save()
        
        # Identify issues and improvements
        health_index.critical_issues = []
        health_index.improvement_areas = []
        health_index.strengths = []
        
        # Critical issues
        if attendance_health < 70:
            health_index.critical_issues.append('Low attendance rates')
        if academic_performance < 70:
            health_index.critical_issues.append('Poor academic performance')
        
        # Improvement areas
        if attendance_health < 80:
            health_index.improvement_areas.append('Improve attendance tracking')
        if student_engagement < 80:
            health_index.improvement_areas.append('Enhance student engagement')
        
        # Strengths
        if attendance_health >= 85:
            health_index.strengths.append('Good attendance rates')
        if security_compliance >= 90:
            health_index.strengths.append('Strong security compliance')
        
        health_index.save()
        
        logger.info(f"Calculated institutional health for institution {institution_id}: {health_score}")
        return 1
        
    except Exception as e:
        logger.error(f"Error calculating institutional health: {e}")
        return 0


@shared_task
def generate_performance_predictions(institution_id, model_type, student_ids=None, course_id=None):
    """
    Generate performance predictions using ML models
    """
    try:
        # Get the appropriate model
        model = PredictiveModel.objects.filter(
            institution_id=institution_id,
            model_type=model_type,
            is_deployed=True
        ).first()
        
        if not model:
            logger.warning(f"No deployed model found for {model_type}")
            return 0
        
        # Prepare data
        if model_type == 'dropout_prediction':
            predictions = _predict_dropout_risk(model, student_ids)
        elif model_type == 'performance_prediction':
            predictions = _predict_academic_performance(model, student_ids)
        elif model_type == 'attendance_prediction':
            predictions = _predict_attendance(model, student_ids)
        elif model_type == 'risk_assessment':
            predictions = _predict_risk_assessment(model, student_ids)
        else:
            logger.warning(f"Unsupported model type: {model_type}")
            return 0
        
        # Save predictions
        predictions_saved = 0
        for pred_data in predictions:
            PredictionResult.objects.create(
                institution_id=institution_id,
                model=model,
                student_id=pred_data['student_id'],
                prediction_value=pred_data['prediction_value'],
                confidence_score=pred_data['confidence_score'],
                prediction_date=timezone.now().date(),
                predicted_class=pred_data.get('predicted_class'),
                class_probabilities=pred_data.get('class_probabilities', {}),
                feature_contributions=pred_data.get('feature_contributions', {}),
                metadata=pred_data.get('metadata', {})
            )
            predictions_saved += 1
        
        # Update model's last prediction date
        model.last_prediction_date = timezone.now()
        model.save()
        
        logger.info(f"Generated {predictions_saved} predictions using {model_type} model")
        return predictions_saved
        
    except Exception as e:
        logger.error(f"Error generating performance predictions: {e}")
        return 0


def _predict_dropout_risk(model, student_ids):
    """Predict dropout risk using ML model"""
    # This would use the trained model from model.model_file
    # For now, return placeholder predictions
    
    predictions = []
    
    if student_ids:
        for student_id in student_ids:
            # Get student's attendance data
            attendance_data = AttendanceAnalytics.objects.filter(
                institution_id=model.institution_id,
                analytics_type='student',
                reference_id=student_id
            ).order_by('-reference_date')[:10]  # Last 10 periods
            
            if attendance_data.exists():
                # Simple heuristic prediction (would use ML model)
                latest_data = attendance_data.first()
                risk_score = latest_data.dropout_risk_score
                
                # Add some randomness for demonstration
                import random
                risk_score += random.uniform(-5, 5)
                risk_score = max(0, min(100, risk_score))
                
                confidence = 85.0  # Placeholder
                
                predictions.append({
                    'student_id': student_id,
                    'prediction_value': risk_score,
                    'confidence_score': confidence,
                    'predicted_class': 'high_risk' if risk_score > 70 else 'medium_risk' if risk_score > 40 else 'low_risk',
                    'class_probabilities': {
                        'low_risk': max(0, 100 - risk_score),
                        'medium_risk': min(100, max(0, risk_score - 40) * 2.5),
                        'high_risk': max(0, (risk_score - 70) * 3.33)
                    },
                    'metadata': {
                        'model_version': model.version,
                        'algorithm': model.algorithm
                    }
                })
    
    return predictions


def _predict_academic_performance(model, student_ids):
    """Predict academic performance using ML model"""
    predictions = []
    
    if student_ids:
        for student_id in student_ids:
            # Get student's performance data
            performance_data = StudentPerformanceAnalytics.objects.filter(
                institution_id=model.institution_id,
                student_id=student_id
            ).order_by('-analysis_date')[:5]  # Last 5 periods
            
            if performance_data.exists():
                # Simple prediction based on trends
                latest_data = performance_data.first()
                
                # Predict final grade based on current GPA and trends
                predicted_grade = latest_data.current_gpa or 0.0
                if latest_data.gpa_trend:
                    predicted_grade += latest_data.gpa_trend * 0.5
                
                predicted_grade = max(0.0, min(4.0, predicted_grade))
                confidence = 80.0  # Placeholder
                
                predictions.append({
                    'student_id': student_id,
                    'prediction_value': predicted_grade,
                    'confidence_score': confidence,
                    'predicted_class': 'excellent' if predicted_grade >= 3.5 else 'good' if predicted_grade >= 3.0 else 'average' if predicted_grade >= 2.0 else 'poor',
                    'metadata': {
                        'model_version': model.version,
                        'algorithm': model.algorithm
                    }
                })
    
    return predictions


def _predict_attendance(model, student_ids):
    """Predict future attendance using ML model"""
    predictions = []
    
    if student_ids:
        for student_id in student_ids:
            # Get student's attendance data
            attendance_data = AttendanceAnalytics.objects.filter(
                institution_id=model.institution_id,
                analytics_type='student',
                reference_id=student_id
            ).order_by('-reference_date')[:10]
            
            if attendance_data.exists():
                # Simple trend-based prediction
                latest_data = attendance_data.first()
                predicted_rate = latest_data.attendance_rate
                
                # Apply trend
                if latest_data.trend_direction == 'declining':
                    predicted_rate -= 5
                elif latest_data.trend_direction == 'improving':
                    predicted_rate += 5
                
                predicted_rate = max(0, min(100, predicted_rate))
                confidence = 75.0  # Placeholder
                
                predictions.append({
                    'student_id': student_id,
                    'prediction_value': predicted_rate,
                    'confidence_score': confidence,
                    'metadata': {
                        'model_version': model.version,
                        'algorithm': model.algorithm
                    }
                })
    
    return predictions


def _predict_risk_assessment(model, student_ids):
    """Predict comprehensive risk assessment"""
    predictions = []
    
    if student_ids:
        for student_id in student_ids:
            # Get student's analytics data
            attendance_data = AttendanceAnalytics.objects.filter(
                institution_id=model.institution_id,
                analytics_type='student',
                reference_id=student_id
            ).order_by('-reference_date').first()
            
            if attendance_data:
                # Combine multiple risk factors
                attendance_risk = attendance_data.dropout_risk_score
                performance_risk = attendance_data.performance_risk_score
                
                # Weighted risk score
                overall_risk = (attendance_risk * 0.6 + performance_risk * 0.4)
                
                confidence = 85.0  # Placeholder
                
                predictions.append({
                    'student_id': student_id,
                    'prediction_value': overall_risk,
                    'confidence_score': confidence,
                    'predicted_class': 'critical' if overall_risk > 80 else 'high' if overall_risk > 60 else 'medium' if overall_risk > 40 else 'low',
                    'metadata': {
                        'attendance_risk': attendance_risk,
                        'performance_risk': performance_risk,
                        'model_version': model.version,
                        'algorithm': model.algorithm
                    }
                })
    
    return predictions


@shared_task
def update_predictive_models(model_id=None):
    """
    Update and retrain predictive models
    """
    try:
        if model_id:
            # Update specific model
            models = PredictiveModel.objects.filter(id=model_id)
        else:
            # Update all active models
            models = PredictiveModel.objects.filter(is_active=True)
        
        models_updated = 0
        
        for model in models:
            try:
                # Prepare training data
                training_data = _prepare_training_data(model)
                
                if training_data is not None and len(training_data) > 0:
                    # Train model (placeholder - would use actual ML)
                    accuracy = _train_model(model, training_data)
                    
                    # Update model performance metrics
                    model.accuracy = accuracy
                    model.training_data_size = len(training_data)
                    model.training_date = timezone.now()
                    model.is_active = True
                    model.save()
                    
                    models_updated += 1
                    
                    logger.info(f"Updated model {model.name} with accuracy: {accuracy:.2f}")
                
            except Exception as e:
                logger.error(f"Error updating model {model.name}: {e}")
                model.is_active = False
                model.save()
        
        logger.info(f"Updated {models_updated} predictive models")
        return models_updated
        
    except Exception as e:
        logger.error(f"Error updating predictive models: {e}")
        return 0


def _prepare_training_data(model):
    """Prepare training data for model"""
    # This would gather and preprocess data based on model type
    # For now, return placeholder data
    
    if model.model_type == 'dropout_prediction':
        # Get student data with dropout outcomes
        # In a real implementation, this would include actual dropout data
        pass
    elif model.model_type == 'performance_prediction':
        # Get student performance data
        pass
    
    return []


def _train_model(model, training_data):
    """Train ML model and return accuracy"""
    # This would implement actual model training
    # For now, return placeholder accuracy
    
    import random
    accuracy = random.uniform(0.7, 0.95)
    
    return accuracy


@shared_task
def generate_analytics_reports(report_data):
    """
    Generate analytics reports
    """
    try:
        # Create report record
        report = AnalyticsReport.objects.create(
            institution_id=report_data['institution_id'],
            report_name=report_data['title'],
            report_type=report_data['report_type'],
            format=report_data['format'],
            start_date=report_data['start_date'],
            end_date=report_data['end_date'],
            filters=report_data.get('filters', {}),
            generated_by_id=report_data.get('generated_by_id'),
            status='generating'
        )
        
        # Generate report based on type and format
        if report_data['report_type'] == 'attendance_summary':
            report_content = _generate_attendance_summary_report(report)
        elif report_data['report_type'] == 'performance_analysis':
            report_content = _generate_performance_analysis_report(report)
        elif report_data['report_type'] == 'risk_assessment':
            report_content = _generate_risk_assessment_report(report)
        else:
            report_content = _generate_custom_report(report)
        
        # Save report file
        if report_content:
            file_path = _save_report_file(report, report_content, report_data['format'])
            report.report_file = file_path
            report.file_size = len(report_content.encode('utf-8'))
            report.status = 'completed'
        else:
            report.status = 'failed'
            report.error_message = 'No content generated'
        
        report.save()
        
        logger.info(f"Generated analytics report: {report.report_name}")
        return 1
        
    except Exception as e:
        logger.error(f"Error generating analytics report: {e}")
        return 0


def _generate_attendance_summary_report(report):
    """Generate attendance summary report"""
    # This would generate a comprehensive attendance summary
    # For now, return placeholder content
    return f"Attendance Summary Report\nGenerated: {timezone.now()}\nPeriod: {report.start_date} to {report.end_date}"


def _generate_performance_analysis_report(report):
    """Generate performance analysis report"""
    # This would generate a comprehensive performance analysis
    return f"Performance Analysis Report\nGenerated: {timezone.now()}\nPeriod: {report.start_date} to {report.end_date}"


def _generate_risk_assessment_report(report):
    """Generate risk assessment report"""
    # This would generate a comprehensive risk assessment
    return f"Risk Assessment Report\nGenerated: {timezone.now()}\nPeriod: {report.start_date} to {report.end_date}"


def _generate_custom_report(report):
    """Generate custom report"""
    # This would generate a custom report based on specifications
    return f"Custom Report: {report.report_type}\nGenerated: {timezone.now()}\nPeriod: {report.start_date} to {report.end_date}"


def _save_report_file(report, content, format_type):
    """Save report to file"""
    import os
    from django.conf import settings
    
    # Create reports directory if it doesn't exist
    reports_dir = os.path.join(settings.MEDIA_ROOT, 'analytics_reports')
    os.makedirs(reports_dir, exist_ok=True)
    
    # Generate filename
    timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
    filename = f"{report.report_type}_{timestamp}.{format_type}"
    file_path = os.path.join(reports_dir, filename)
    
    # Save file
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    return file_path
