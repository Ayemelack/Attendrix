"""
Analytics serializers for Attendrix API
"""
from rest_framework import serializers
from django.utils import timezone
from apps.analytics.models import (
    AttendanceAnalytics, StudentPerformanceAnalytics, InstitutionalHealthIndex,
    PredictiveModel, PredictionResult, AnalyticsDashboard, AnalyticsReport,
    DataVisualization
)
from apps.users.serializers import UserSerializer
from apps.courses.serializers import CourseSerializer
from apps.departments.serializers import DepartmentSerializer


class AttendanceAnalyticsSerializer(serializers.ModelSerializer):
    """
    Attendance analytics serializer
    """
    reference_info = serializers.SerializerMethodField()
    
    class Meta:
        model = AttendanceAnalytics
        fields = [
            'id', 'analytics_type', 'reference_id', 'reference_info', 'reference_date',
            'total_sessions', 'total_attendance_records', 'present_count', 'absent_count',
            'late_count', 'excused_count', 'attendance_rate', 'punctuality_rate',
            'engagement_score', 'consistency_score', 'attendance_trend', 'trend_direction',
            'dropout_risk_score', 'performance_risk_score', 'intervention_priority',
            'department_average', 'institution_average', 'percentile_rank', 'metadata',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']

    def get_reference_info(self, obj):
        """Get reference information based on analytics type"""
        if obj.analytics_type == 'student' and obj.reference_id:
            try:
                from apps.users.models import User
                student = User.objects.get(id=obj.reference_id)
                return {
                    'id': student.id,
                    'name': student.get_full_name(),
                    'email': student.email
                }
            except User.DoesNotExist:
                pass
        elif obj.analytics_type == 'course' and obj.reference_id:
            try:
                from apps.courses.models import Course
                course = Course.objects.get(id=obj.reference_id)
                return {
                    'id': course.id,
                    'title': course.title,
                    'code': course.code
                }
            except Course.DoesNotExist:
                pass
        elif obj.analytics_type == 'lecturer' and obj.reference_id:
            try:
                from apps.users.models import User
                lecturer = User.objects.get(id=obj.reference_id)
                return {
                    'id': lecturer.id,
                    'name': lecturer.get_full_name(),
                    'email': lecturer.email
                }
            except User.DoesNotExist:
                pass
        return None


class StudentPerformanceAnalyticsSerializer(serializers.ModelSerializer):
    """
    Student performance analytics serializer
    """
    student_info = UserSerializer(source='student', read_only=True)
    course_info = CourseSerializer(source='course', read_only=True)
    
    class Meta:
        model = StudentPerformanceAnalytics
        fields = [
            'id', 'student', 'student_info', 'course', 'course_info', 'analysis_date',
            'current_gpa', 'gpa_trend', 'grade_distribution',
            'attendance_correlation', 'attendance_impact_score',
            'class_participation_score', 'assignment_completion_rate', 'engagement_consistency',
            'final_grade_prediction', 'prediction_confidence', 'success_probability',
            'at_risk_factors', 'intervention_recommendations', 'risk_category',
            'class_rank', 'class_percentile', 'department_rank', 'department_percentile',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']


class InstitutionalHealthIndexSerializer(serializers.ModelSerializer):
    """
    Institutional health index serializer
    """
    class Meta:
        model = InstitutionalHealthIndex
        fields = [
            'id', 'calculation_date',
            'attendance_health', 'academic_performance', 'student_engagement',
            'faculty_performance', 'operational_efficiency', 'security_compliance',
            'health_score', 'health_grade', 'score_change', 'trend_direction',
            'total_students', 'total_courses', 'total_lecturers',
            'average_attendance_rate', 'average_gpa', 'retention_rate',
            'critical_issues', 'improvement_areas', 'strengths',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']


class PredictiveModelSerializer(serializers.ModelSerializer):
    """
    Predictive model serializer
    """
    class Meta:
        model = PredictiveModel
        fields = [
            'id', 'model_type', 'model_name', 'version', 'algorithm', 'features', 'hyperparameters',
            'accuracy', 'precision', 'recall', 'f1_score', 'auc_score',
            'training_data_size', 'training_date', 'validation_data_size',
            'is_active', 'is_deployed', 'last_prediction_date', 'model_file',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']


class PredictionResultSerializer(serializers.ModelSerializer):
    """
    Prediction result serializer
    """
    model_info = PredictiveModelSerializer(source='model', read_only=True)
    student_info = UserSerializer(source='student', read_only=True)
    course_info = CourseSerializer(source='course', read_only=True)
    department_info = DepartmentSerializer(source='department', read_only=True)
    
    class Meta:
        model = PredictionResult
        fields = [
            'id', 'model', 'model_info', 'student', 'student_info', 'course', 'course_info',
            'department', 'department_info', 'prediction_value', 'confidence_score',
            'prediction_date', 'predicted_class', 'class_probabilities', 'feature_contributions',
            'actual_value', 'actual_class', 'prediction_correct', 'metadata',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']


class AnalyticsDashboardSerializer(serializers.ModelSerializer):
    """
    Analytics dashboard serializer
    """
    shared_with_info = UserSerializer(source='shared_with', many=True, read_only=True)
    
    class Meta:
        model = AnalyticsDashboard
        fields = [
            'id', 'dashboard_name', 'dashboard_type', 'layout', 'widgets', 'filters',
            'is_public', 'shared_with', 'shared_with_info', 'is_default',
            'auto_refresh_interval', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']


class AnalyticsReportSerializer(serializers.ModelSerializer):
    """
    Analytics report serializer
    """
    generated_by_info = UserSerializer(source='generated_by', read_only=True)
    
    class Meta:
        model = AnalyticsReport
        fields = [
            'id', 'report_name', 'report_type', 'format', 'start_date', 'end_date', 'filters',
            'generated_by', 'generated_by_info', 'generated_at', 'report_file', 'file_size',
            'status', 'error_message', 'is_public', 'access_token',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['generated_at', 'file_size', 'created_at', 'updated_at']


class DataVisualizationSerializer(serializers.ModelSerializer):
    """
    Data visualization serializer
    """
    class Meta:
        model = DataVisualization
        fields = [
            'id', 'chart_name', 'chart_type', 'data_source', 'data_query',
            'x_axis', 'y_axis', 'series', 'styling',
            'is_interactive', 'drill_down_config',
            'width', 'height', 'responsive',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']


class DashboardWidgetSerializer(serializers.Serializer):
    """
    Dashboard widget configuration serializer
    """
    widget_type = serializers.ChoiceField(choices=[
        ('metric_card', 'Metric Card'),
        ('chart', 'Chart'),
        ('table', 'Table'),
        ('list', 'List'),
        ('calendar', 'Calendar'),
        ('gauge', 'Gauge'),
        ('progress', 'Progress Bar'),
    ])
    title = serializers.CharField(max_length=100)
    data_source = serializers.CharField(max_length=100)
    config = serializers.JSONField(default=dict)
    position = serializers.JSONField(default=dict)  # x, y, width, height
    filters = serializers.JSONField(default=dict)
    refresh_interval = serializers.IntegerField(default=300)


class AnalyticsQuerySerializer(serializers.Serializer):
    """
    Analytics query serializer
    """
    query_type = serializers.ChoiceField(choices=[
        ('attendance_trends', 'Attendance Trends'),
        ('performance_analytics', 'Performance Analytics'),
        ('risk_assessment', 'Risk Assessment'),
        ('comparative_analysis', 'Comparative Analysis'),
        ('predictive_insights', 'Predictive Insights'),
        ('institutional_health', 'Institutional Health'),
    ])
    
    # Date range
    start_date = serializers.DateField()
    end_date = serializers.DateField()
    
    # Filters
    student_id = serializers.UUIDField(required=False)
    course_id = serializers.UUIDField(required=False)
    department_id = serializers.UUIDField(required=False)
    lecturer_id = serializers.UUIDField(required=False)
    
    # Grouping
    group_by = serializers.ChoiceField(choices=[
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
        ('course', 'Course'),
        ('student', 'Student'),
        ('department', 'Department'),
    ], required=False)
    
    # Metrics
    metrics = serializers.ListField(
        child=serializers.CharField(),
        required=False
    )
    
    # Pagination
    page = serializers.IntegerField(default=1)
    page_size = serializers.IntegerField(default=20)
    
    def validate(self, attrs):
        """Validate query parameters"""
        start_date = attrs.get('start_date')
        end_date = attrs.get('end_date')
        
        if start_date and end_date:
            if start_date > end_date:
                raise serializers.ValidationError("Start date cannot be after end date")
            
            # Check date range is not too large
            if (end_date - start_date).days > 365:
                raise serializers.ValidationError("Date range cannot exceed 1 year")
        
        return attrs


class PredictiveAnalyticsSerializer(serializers.Serializer):
    """
    Predictive analytics request serializer
    """
    model_type = serializers.ChoiceField(choices=[
        ('dropout_prediction', 'Dropout Prediction'),
        ('performance_prediction', 'Performance Prediction'),
        ('attendance_prediction', 'Attendance Prediction'),
        ('risk_assessment', 'Risk Assessment'),
    ])
    
    # Target entities
    student_ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=False
    )
    course_id = serializers.UUIDField(required=False)
    department_id = serializers.UUIDField(required=False)
    
    # Prediction parameters
    prediction_date = serializers.DateField(required=False)
    include_confidence = serializers.BooleanField(default=True)
    include_feature_importance = serializers.BooleanField(default=True)
    
    def validate(self, attrs):
        """Validate prediction parameters"""
        model_type = attrs.get('model_type')
        
        if model_type == 'dropout_prediction' and not attrs.get('student_ids'):
            raise serializers.ValidationError("Student IDs are required for dropout prediction")
        
        if model_type == 'performance_prediction' and not attrs.get('student_ids'):
            raise serializers.ValidationError("Student IDs are required for performance prediction")
        
        return attrs


class ReportGenerationSerializer(serializers.Serializer):
    """
    Report generation serializer
    """
    report_type = serializers.ChoiceField(choices=[
        ('attendance_summary', 'Attendance Summary'),
        ('performance_analysis', 'Performance Analysis'),
        ('risk_assessment', 'Risk Assessment'),
        ('trend_analysis', 'Trend Analysis'),
        ('comparative_analysis', 'Comparative Analysis'),
        ('custom', 'Custom Report'),
    ])
    
    format = serializers.ChoiceField(choices=[
        ('pdf', 'PDF'),
        ('excel', 'Excel'),
        ('csv', 'CSV'),
        ('json', 'JSON'),
    ])
    
    # Report parameters
    title = serializers.CharField(max_length=200)
    start_date = serializers.DateField()
    end_date = serializers.DateField()
    
    # Filters
    student_ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=False
    )
    course_ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=False
    )
    department_ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=False
    )
    
    # Report content
    include_charts = serializers.BooleanField(default=True)
    include_tables = serializers.BooleanField(default=True)
    include_summary = serializers.BooleanField(default=True)
    
    # Delivery options
    email_to = serializers.ListField(
        child=serializers.EmailField(),
        required=False
    )
    
    def validate(self, attrs):
        """Validate report parameters"""
        start_date = attrs.get('start_date')
        end_date = attrs.get('end_date')
        
        if start_date and end_date:
            if start_date > end_date:
                raise serializers.ValidationError("Start date cannot be after end date")
            
            # Check date range is not too large
            if (end_date - start_date).days > 365:
                raise serializers.ValidationError("Date range cannot exceed 1 year")
        
        return attrs


class TrendAnalysisSerializer(serializers.Serializer):
    """
    Trend analysis serializer
    """
    metric = serializers.ChoiceField(choices=[
        ('attendance_rate', 'Attendance Rate'),
        ('gpa', 'GPA'),
        ('engagement_score', 'Engagement Score'),
        ('dropout_risk', 'Dropout Risk'),
        ('performance_score', 'Performance Score'),
    ])
    
    # Time period
    period = serializers.ChoiceField(choices=[
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
        ('semester', 'Semester'),
    ])
    
    start_date = serializers.DateField()
    end_date = serializers.DateField()
    
    # Analysis options
    include_forecast = serializers.BooleanField(default=False)
    forecast_periods = serializers.IntegerField(default=5)
    confidence_interval = serializers.FloatField(default=0.95)
    
    # Grouping
    group_by = serializers.ChoiceField(choices=[
        ('none', 'None'),
        ('course', 'Course'),
        ('department', 'Department'),
        ('student_level', 'Student Level'),
    ], required=False)
    
    def validate(self, attrs):
        """Validate trend analysis parameters"""
        start_date = attrs.get('start_date')
        end_date = attrs.get('end_date')
        
        if start_date and end_date:
            if start_date > end_date:
                raise serializers.ValidationError("Start date cannot be after end date")
            
            # Minimum period requirements
            period = attrs.get('period')
            min_days = {
                'daily': 7,
                'weekly': 4,
                'monthly': 3,
                'semester': 1
            }
            
            if period in min_days:
                min_period_days = min_days[period] * {
                    'daily': 1,
                    'weekly': 7,
                    'monthly': 30,
                    'semester': 90
                }[period]
                
                if (end_date - start_date).days < min_period_days:
                    raise serializers.ValidationError(f"Period must be at least {min_days} days for {period} analysis")
        
        return attrs
