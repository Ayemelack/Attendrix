"""
Analytics models for Attendrix - Advanced analytics and intelligence
"""
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from apps.core.models import TimeStampedModel, TenantModel
from apps.institutions.models import Institution
from apps.users.models import User
from apps.courses.models import Course
from apps.departments.models import Department
import uuid


class AttendanceAnalytics(TimeStampedModel, TenantModel):
    """
    Comprehensive attendance analytics
    """
    ANALYTICS_TYPES = [
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
        ('semester', 'Semester'),
        ('course', 'Course'),
        ('student', 'Student'),
        ('lecturer', 'Lecturer'),
        ('department', 'Department'),
        ('institution', 'Institution'),
    ]

    analytics_type = models.CharField(max_length=20, choices=ANALYTICS_TYPES)
    reference_id = models.UUIDField(null=True, blank=True)  # Course, Student, etc.
    reference_date = models.DateField()
    
    # Attendance Metrics
    total_sessions = models.IntegerField(default=0)
    total_attendance_records = models.IntegerField(default=0)
    present_count = models.IntegerField(default=0)
    absent_count = models.IntegerField(default=0)
    late_count = models.IntegerField(default=0)
    excused_count = models.IntegerField(default=0)
    
    # Calculated Metrics
    attendance_rate = models.FloatField(default=0.0)
    punctuality_rate = models.FloatField(default=0.0)
    engagement_score = models.FloatField(default=0.0)
    consistency_score = models.FloatField(default=0.0)
    
    # Trend Analysis
    attendance_trend = models.FloatField(default=0.0)  # Percentage change
    trend_direction = models.CharField(
        max_length=10,
        choices=[
            ('improving', 'Improving'),
            ('declining', 'Declining'),
            ('stable', 'Stable'),
        ],
        default='stable'
    )
    
    # Risk Assessment
    dropout_risk_score = models.FloatField(default=0.0)  # 0-100
    performance_risk_score = models.FloatField(default=0.0)  # 0-100
    intervention_priority = models.CharField(
        max_length=10,
        choices=[
            ('low', 'Low'),
            ('medium', 'Medium'),
            ('high', 'High'),
            ('critical', 'Critical'),
        ],
        default='low'
    )
    
    # Comparative Analytics
    department_average = models.FloatField(null=True, blank=True)
    institution_average = models.FloatField(null=True, blank=True)
    percentile_rank = models.FloatField(null=True, blank=True)
    
    # Additional Data
    metadata = models.JSONField(default=dict, blank=True)
    
    class Meta:
        db_table = 'analytics_attendance'
        verbose_name = 'Attendance Analytics'
        verbose_name_plural = 'Attendance Analytics'
        unique_together = ['institution', 'analytics_type', 'reference_id', 'reference_date']
        indexes = [
            models.Index(fields=['institution', 'analytics_type', 'reference_date']),
            models.Index(fields=['analytics_type']),
            models.Index(fields=['reference_date']),
            models.Index(fields=['dropout_risk_score']),
            models.Index(fields=['intervention_priority']),
        ]

    def __str__(self):
        return f"{self.analytics_type.title()} - {self.reference_date}"


class StudentPerformanceAnalytics(TimeStampedModel, TenantModel):
    """
    Student performance analytics with predictive intelligence
    """
    student = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='performance_analytics',
        limit_choices_to={'role': 'student'}
    )
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name='student_performance_analytics',
        null=True,
        blank=True
    )
    analysis_date = models.DateField()
    
    # Academic Performance
    current_gpa = models.FloatField(null=True, blank=True)
    gpa_trend = models.FloatField(default=0.0)
    grade_distribution = models.JSONField(default=dict)  # Grade breakdown
    
    # Attendance Correlation
    attendance_correlation = models.FloatField(default=0.0)  # Correlation with grades
    attendance_impact_score = models.FloatField(default=0.0)  # How attendance affects performance
    
    # Behavioral Analytics
    class_participation_score = models.FloatField(default=0.0)
    assignment_completion_rate = models.FloatField(default=0.0)
    engagement_consistency = models.FloatField(default=0.0)
    
    # Predictive Analytics
    final_grade_prediction = models.FloatField(null=True, blank=True)
    prediction_confidence = models.FloatField(default=0.0)  # 0-100
    success_probability = models.FloatField(default=0.0)  # 0-100
    
    # Risk Factors
    at_risk_factors = models.JSONField(default=list)
    intervention_recommendations = models.JSONField(default=list)
    risk_category = models.CharField(
        max_length=10,
        choices=[
            ('excellent', 'Excellent'),
            ('good', 'Good'),
            ('average', 'Average'),
            ('at_risk', 'At Risk'),
            ('critical', 'Critical'),
        ],
        default='average'
    )
    
    # Comparative Data
    class_rank = models.IntegerField(null=True, blank=True)
    class_percentile = models.FloatField(null=True, blank=True)
    department_rank = models.IntegerField(null=True, blank=True)
    department_percentile = models.FloatField(null=True, blank=True)
    
    class Meta:
        db_table = 'analytics_student_performance'
        verbose_name = 'Student Performance Analytics'
        verbose_name_plural = 'Student Performance Analytics'
        unique_together = ['institution', 'student', 'course', 'analysis_date']
        indexes = [
            models.Index(fields=['student', 'analysis_date']),
            models.Index(fields=['course', 'analysis_date']),
            models.Index(fields=['risk_category']),
            models.Index(fields=['success_probability']),
        ]

    def __str__(self):
        return f"{self.student.get_full_name()} - {self.analysis_date}"


class InstitutionalHealthIndex(TimeStampedModel, TenantModel):
    """
    Institutional health index with comprehensive scoring
    """
    calculation_date = models.DateField()
    
    # Component Scores (0-100 each)
    attendance_health = models.FloatField(default=0.0)
    academic_performance = models.FloatField(default=0.0)
    student_engagement = models.FloatField(default=0.0)
    faculty_performance = models.FloatField(default=0.0)
    operational_efficiency = models.FloatField(default=0.0)
    security_compliance = models.FloatField(default=0.0)
    
    # Overall Health Score
    health_score = models.FloatField(default=0.0)
    health_grade = models.CharField(
        max_length=2,
        choices=[
            ('A+', 'A+'),
            ('A', 'A'),
            ('B+', 'B+'),
            ('B', 'B'),
            ('C+', 'C+'),
            ('C', 'C'),
            ('D', 'D'),
            ('F', 'F'),
        ],
        default='C'
    )
    
    # Trend Analysis
    score_change = models.FloatField(default=0.0)  # Change from previous period
    trend_direction = models.CharField(
        max_length=10,
        choices=[
            ('improving', 'Improving'),
            ('declining', 'Declining'),
            ('stable', 'Stable'),
        ],
        default='stable'
    )
    
    # Key Metrics
    total_students = models.IntegerField(default=0)
    total_courses = models.IntegerField(default=0)
    total_lecturers = models.IntegerField(default=0)
    average_attendance_rate = models.FloatField(default=0.0)
    average_gpa = models.FloatField(default=0.0)
    retention_rate = models.FloatField(default=0.0)
    
    # Alerts and Issues
    critical_issues = models.JSONField(default=list)
    improvement_areas = models.JSONField(default=list)
    strengths = models.JSONField(default=list)
    
    class Meta:
        db_table = 'analytics_institutional_health'
        verbose_name = 'Institutional Health Index'
        verbose_name_plural = 'Institutional Health Indices'
        unique_together = ['institution', 'calculation_date']
        indexes = [
            models.Index(fields=['calculation_date']),
            models.Index(fields=['health_score']),
            models.Index(fields=['health_grade']),
        ]

    def __str__(self):
        return f"{self.institution.name} Health - {self.calculation_date}"

    def calculate_health_score(self):
        """Calculate overall health score"""
        weights = {
            'attendance_health': 0.25,
            'academic_performance': 0.25,
            'student_engagement': 0.20,
            'faculty_performance': 0.15,
            'operational_efficiency': 0.10,
            'security_compliance': 0.05
        }
        
        score = (
            self.attendance_health * weights['attendance_health'] +
            self.academic_performance * weights['academic_performance'] +
            self.student_engagement * weights['student_engagement'] +
            self.faculty_performance * weights['faculty_performance'] +
            self.operational_efficiency * weights['operational_efficiency'] +
            self.security_compliance * weights['security_compliance']
        )
        
        self.health_score = round(score, 2)
        
        # Determine grade
        if self.health_score >= 95:
            self.health_grade = 'A+'
        elif self.health_score >= 90:
            self.health_grade = 'A'
        elif self.health_grade >= 85:
            self.health_grade = 'B+'
        elif self.health_grade >= 80:
            self.health_grade = 'B'
        elif self.health_grade >= 75:
            self.health_grade = 'C+'
        elif self.health_grade >= 70:
            self.health_grade = 'C'
        elif self.health_grade >= 60:
            self.health_grade = 'D'
        else:
            self.health_grade = 'F'
        
        self.save()


class PredictiveModel(TimeStampedModel, TenantModel):
    """
    Machine learning models for predictive analytics
    """
    MODEL_TYPES = [
        ('dropout_prediction', 'Dropout Prediction'),
        ('performance_prediction', 'Performance Prediction'),
        ('attendance_prediction', 'Attendance Prediction'),
        ('risk_assessment', 'Risk Assessment'),
        ('enrollment_forecasting', 'Enrollment Forecasting'),
    ]
    
    model_type = models.CharField(max_length=30, choices=MODEL_TYPES)
    model_name = models.CharField(max_length=100)
    version = models.CharField(max_length=20, default='1.0')
    
    # Model Configuration
    algorithm = models.CharField(max_length=50)  # Linear Regression, Random Forest, etc.
    features = models.JSONField(default=list)  # List of features used
    hyperparameters = models.JSONField(default=dict)  # Model hyperparameters
    
    # Performance Metrics
    accuracy = models.FloatField(null=True, blank=True)
    precision = models.FloatField(null=True, blank=True)
    recall = models.FloatField(null=True, blank=True)
    f1_score = models.FloatField(null=True, blank=True)
    auc_score = models.FloatField(null=True, blank=True)
    
    # Training Data
    training_data_size = models.IntegerField(default=0)
    training_date = models.DateTimeField(null=True, blank=True)
    validation_data_size = models.IntegerField(default=0)
    
    # Status
    is_active = models.BooleanField(default=True)
    is_deployed = models.BooleanField(default=False)
    last_prediction_date = models.DateTimeField(null=True, blank=True)
    
    # Model File (for storing trained models)
    model_file = models.FileField(upload_to='predictive_models/', blank=True)
    
    class Meta:
        db_table = 'analytics_predictive_model'
        verbose_name = 'Predictive Model'
        verbose_name_plural = 'Predictive Models'
        unique_together = ['institution', 'model_type', 'model_name', 'version']
        indexes = [
            models.Index(fields=['model_type']),
            models.Index(fields=['is_active']),
            models.Index(fields=['is_deployed']),
        ]

    def __str__(self):
        return f"{self.model_name} - {self.model_type}"


class PredictionResult(TimeStampedModel, TenantModel):
    """
    Results from predictive models
    """
    model = models.ForeignKey(
        PredictiveModel,
        on_delete=models.CASCADE,
        related_name='predictions'
    )
    
    # Target Entity
    student = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='predictions',
        null=True,
        blank=True,
        limit_choices_to={'role': 'student'}
    )
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name='predictions',
        null=True,
        blank=True
    )
    department = models.ForeignKey(
        Department,
        on_delete=models.CASCADE,
        related_name='predictions',
        null=True,
        blank=True
    )
    
    # Prediction Results
    prediction_value = models.FloatField()  # Predicted value
    confidence_score = models.FloatField(default=0.0)  # 0-100
    prediction_date = models.DateField()
    
    # Classification Results
    predicted_class = models.CharField(max_length=50, blank=True)
    class_probabilities = models.JSONField(default=dict)  # Probabilities for each class
    
    # Feature Importance
    feature_contributions = models.JSONField(default=dict)  # How each feature contributed
    
    # Actual Result (for model evaluation)
    actual_value = models.FloatField(null=True, blank=True)
    actual_class = models.CharField(max_length=50, blank=True)
    prediction_correct = models.BooleanField(null=True, blank=True)
    
    # Additional Data
    metadata = models.JSONField(default=dict, blank=True)
    
    class Meta:
        db_table = 'analytics_prediction_result'
        verbose_name = 'Prediction Result'
        verbose_name_plural = 'Prediction Results'
        indexes = [
            models.Index(fields=['model', 'prediction_date']),
            models.Index(fields=['student']),
            models.Index(fields=['course']),
            models.Index(fields=['prediction_date']),
            models.Index(fields=['prediction_correct']),
        ]

    def __str__(self):
        return f"{self.model.model_name} - {self.prediction_date}"


class AnalyticsDashboard(TimeStampedModel, TenantModel):
    """
    Custom analytics dashboard configurations
    """
    dashboard_name = models.CharField(max_length=100)
    dashboard_type = models.CharField(
        max_length=20,
        choices=[
            ('student', 'Student'),
            ('lecturer', 'Lecturer'),
            ('admin', 'Administrator'),
            ('institution_admin', 'Institution Admin'),
            ('super_admin', 'Super Admin'),
        ]
    )
    
    # Dashboard Configuration
    layout = models.JSONField(default=dict)  # Widget layout and configuration
    widgets = models.JSONField(default=list)  # List of widgets and their settings
    filters = models.JSONField(default=dict)  # Available filters
    
    # Sharing and Access
    is_public = models.BooleanField(default=False)
    shared_with = models.ManyToManyField(
        User,
        blank=True,
        related_name='shared_dashboards'
    )
    
    # Default Settings
    is_default = models.BooleanField(default=False)
    auto_refresh_interval = models.IntegerField(default=300)  # seconds
    
    class Meta:
        db_table = 'analytics_dashboard'
        verbose_name = 'Analytics Dashboard'
        verbose_name_plural = 'Analytics Dashboards'
        unique_together = ['institution', 'dashboard_name', 'dashboard_type']
        indexes = [
            models.Index(fields=['dashboard_type']),
            models.Index(fields=['is_default']),
            models.Index(fields=['is_public']),
        ]

    def __str__(self):
        return f"{self.dashboard_name} - {self.dashboard_type}"


class AnalyticsReport(TimeStampedModel, TenantModel):
    """
    Generated analytics reports
    """
    REPORT_TYPES = [
        ('attendance_summary', 'Attendance Summary'),
        ('performance_analysis', 'Performance Analysis'),
        ('risk_assessment', 'Risk Assessment'),
        ('trend_analysis', 'Trend Analysis'),
        ('comparative_analysis', 'Comparative Analysis'),
        ('custom', 'Custom Report'),
    ]
    
    REPORT_FORMATS = [
        ('pdf', 'PDF'),
        ('excel', 'Excel'),
        ('csv', 'CSV'),
        ('json', 'JSON'),
        ('html', 'HTML'),
    ]
    
    report_name = models.CharField(max_length=200)
    report_type = models.CharField(max_length=30, choices=REPORT_TYPES)
    format = models.CharField(max_length=10, choices=REPORT_FORMATS)
    
    # Report Parameters
    start_date = models.DateField()
    end_date = models.DateField()
    filters = models.JSONField(default=dict)  # Applied filters
    
    # Generation Info
    generated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='generated_reports'
    )
    generated_at = models.DateTimeField(auto_now_add=True)
    
    # File Storage
    report_file = models.FileField(upload_to='analytics_reports/')
    file_size = models.BigInteger(default=0)
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('generating', 'Generating'),
            ('completed', 'Completed'),
            ('failed', 'Failed'),
        ],
        default='pending'
    )
    error_message = models.TextField(blank=True)
    
    # Access Control
    is_public = models.BooleanField(default=False)
    access_token = models.CharField(max_length=64, blank=True)  # For secure sharing
    
    class Meta:
        db_table = 'analytics_report'
        verbose_name = 'Analytics Report'
        verbose_name_plural = 'Analytics Reports'
        indexes = [
            models.Index(fields=['report_type']),
            models.Index(fields=['status']),
            fields=['generated_at'],
            fields=['start_date', 'end_date'],
        ]

    def __str__(self):
        return f"{self.report_name} - {self.report_type}"


class DataVisualization(TimeStampedModel, TenantModel):
    """
    Data visualization configurations
    """
    CHART_TYPES = [
        ('line', 'Line Chart'),
        ('bar', 'Bar Chart'),
        ('pie', 'Pie Chart'),
        ('scatter', 'Scatter Plot'),
        ('heatmap', 'Heatmap'),
        ('gauge', 'Gauge Chart'),
        ('histogram', 'Histogram'),
        ('box_plot', 'Box Plot'),
    ]
    
    chart_name = models.CharField(max_length=100)
    chart_type = models.CharField(max_length=20, choices=CHART_TYPES)
    
    # Data Configuration
    data_source = models.CharField(max_length=100)  # Model or API endpoint
    data_query = models.JSONField(default=dict)  # Query parameters
    
    # Chart Configuration
    x_axis = models.JSONField(default=dict)
    y_axis = models.JSONField(default=dict)
    series = models.JSONField(default=list)  # Data series configuration
    styling = models.JSONField(default=dict)  # Colors, fonts, etc.
    
    # Interactivity
    is_interactive = models.BooleanField(default=True)
    drill_down_config = models.JSONField(default=dict)
    
    # Display Settings
    width = models.IntegerField(default=800)
    height = models.IntegerField(default=400)
    responsive = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'analytics_data_visualization'
        verbose_name = 'Data Visualization'
        verbose_name_plural = 'Data Visualizations'
        indexes = [
            models.Index(fields=['chart_type']),
            fields=['data_source'],
        ]

    def __str__(self):
        return f"{self.chart_name} - {self.chart_type}"
