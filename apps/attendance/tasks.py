"""
Attendance tasks for Attendrix - Background processing for attendance engine
"""
from celery import shared_task
from django.utils import timezone
from django.db.models import Q, Count, Avg, StdDev, F
from django.db.models.functions import Extract
from datetime import datetime, timedelta
from apps.core.models import ActivityLog, SecurityLog
from apps.attendance.models import (
    AttendanceSession, AttendanceRecord, AttendanceStatistics,
    AttendancePattern, AttendanceAlert, AttendanceSettings
)
from apps.alerts.models import Alert, Notification
from apps.communication.models import Announcement
import logging

logger = logging.getLogger(__name__)


@shared_task
def generate_attendance_analytics(session_id=None):
    """
    Generate attendance analytics for sessions or all sessions
    """
    try:
        if session_id:
            # Generate analytics for specific session
            session = AttendanceSession.objects.get(id=session_id)
            sessions = [session]
        else:
            # Generate analytics for all recent sessions
            cutoff_date = timezone.now() - timedelta(days=7)
            sessions = AttendanceSession.objects.filter(
                created_at__gte=cutoff_date,
                is_deleted=False
            )
        
        analytics_generated = 0
        
        for session in sessions:
            # Get attendance records for the session
            records = session.attendance_records.filter(is_deleted=False)
            
            if records.exists():
                # Calculate statistics
                stats = records.aggregate(
                    total=Count('id'),
                    present=Count('id', filter=Q(status='present')),
                    absent=Count('id', filter=Q(status='absent')),
                    late=Count('id', filter=Q(status='late')),
                    excused=Count('id', filter=Q(status='excused')),
                    suspicious=Count('id', filter=Q(is_suspicious=True)),
                    avg_verification_score=Avg('verification_score')
                )
                
                total = stats['total'] or 0
                attendance_rate = ((stats['present'] or 0) / total * 100) if total > 0 else 0
                punctuality_rate = (((stats['present'] or 0) - (stats['late'] or 0)) / total * 100) if total > 0 else 0
                
                # Create or update statistics record
                AttendanceStatistics.objects.update_or_create(
                    institution=session.institution,
                    statistics_type='course',
                    reference_id=session.course.id,
                    reference_date=session.start_time.date(),
                    defaults={
                        'total_sessions': 1,
                        'total_attendance_records': total,
                        'present_count': stats['present'] or 0,
                        'absent_count': stats['absent'] or 0,
                        'late_count': stats['late'] or 0,
                        'excused_count': stats['excused'] or 0,
                        'attendance_rate': attendance_rate,
                        'punctuality_rate': punctuality_rate,
                        'engagement_score': (attendance_rate * 0.7 + punctuality_rate * 0.3)
                    }
                )
                
                analytics_generated += 1
        
        logger.info(f"Generated analytics for {analytics_generated} sessions")
        return analytics_generated
        
    except Exception as e:
        logger.error(f"Error generating attendance analytics: {e}")
        return 0


@shared_task
def detect_attendance_anomalies(institution_id):
    """
    Detect attendance anomalies and patterns
    """
    try:
        institution_id = str(institution_id)
        
        # Get recent attendance records
        cutoff_date = timezone.now() - timedelta(days=30)
        records = AttendanceRecord.objects.filter(
            institution_id=institution_id,
            marked_at__gte=cutoff_date,
            is_deleted=False
        ).select_related('student', 'session', 'session__course')
        
        anomalies_detected = 0
        
        # Group by student
        students = {}
        for record in records:
            student_id = record.student.id
            if student_id not in students:
                students[student_id] = {
                    'student': record.student,
                    'records': [],
                    'courses': set()
                }
            students[student_id]['records'].append(record)
            students[student_id]['courses'].add(record.session.course.id)
        
        # Analyze each student's attendance pattern
        for student_id, data in students.items():
            student = data['student']
            student_records = data['records']
            
            # Calculate basic statistics
            total_records = len(student_records)
            present_count = len([r for r in student_records if r.status == 'present'])
            late_count = len([r for r in student_records if r.status == 'late'])
            absent_count = len([r for r in student_records if r.status == 'absent'])
            
            attendance_rate = (present_count / total_records * 100) if total_records > 0 else 0
            
            # Check for anomalies
            anomalies = []
            
            # Low attendance rate
            if attendance_rate < 70:
                anomalies.append({
                    'type': 'low_attendance',
                    'severity': 'high',
                    'value': attendance_rate,
                    'threshold': 70
                })
            
            # High suspicious activity
            suspicious_count = len([r for r in student_records if r.is_suspicious])
            if suspicious_count > total_records * 0.3:  # More than 30% suspicious
                anomalies.append({
                    'type': 'high_suspicious_activity',
                    'severity': 'critical',
                    'value': suspicious_count,
                    'threshold': total_records * 0.3
                })
            
            # Inconsistent timing patterns
            check_in_times = [r.check_in_time.time() for r in student_records if r.check_in_time]
            if len(check_in_times) > 5:
                time_variance = _calculate_time_variance(check_in_times)
                if time_variance > 1800:  # 30 minutes variance
                    anomalies.append({
                        'type': 'inconsistent_timing',
                        'severity': 'medium',
                        'value': time_variance,
                        'threshold': 1800
                    })
            
            # Create attendance pattern record
            pattern_type = 'normal'
            confidence_score = 100
            risk_level = 'low'
            
            if anomalies:
                # Determine pattern type and risk level
                high_severity_count = len([a for a in anomalies if a['severity'] == 'high'])
                critical_severity_count = len([a for a in anomalies if a['severity'] == 'critical'])
                
                if critical_severity_count > 0:
                    pattern_type = 'suspicious'
                    risk_level = 'critical'
                    confidence_score = 90
                elif high_severity_count > 0:
                    pattern_type = 'erratic'
                    risk_level = 'high'
                    confidence_score = 75
                else:
                    pattern_type = 'declining'
                    risk_level = 'medium'
                    confidence_score = 60
                
                # Create pattern record
                AttendancePattern.objects.update_or_create(
                    institution_id=institution_id,
                    student=student,
                    course=None,  # Overall pattern
                    analysis_start_date=cutoff_date,
                    analysis_end_date=timezone.now().date(),
                    defaults={
                        'pattern_type': pattern_type,
                        'confidence_score': confidence_score,
                        'risk_level': risk_level,
                        'average_attendance_rate': attendance_rate,
                        'consistency_score': 100 - confidence_score,
                        'anomaly_count': len(anomalies),
                        'last_anomaly_date': timezone.now(),
                        'total_sessions_analyzed': total_records
                    }
                )
                
                # Create alerts for high-risk patterns
                if risk_level in ['high', 'critical']:
                    AttendanceAlert.objects.create(
                        institution_id=institution_id,
                        alert_type='pattern_anomaly',
                        severity=risk_level,
                        title=f'Attendance Pattern Anomaly Detected',
                        description=f'{student.get_full_name()} shows {pattern_type} attendance pattern with {len(anomalies)} anomalies',
                        student=student,
                        alert_data={
                            'pattern_type': pattern_type,
                            'anomalies': anomalies,
                            'attendance_rate': attendance_rate
                        }
                    )
                
                anomalies_detected += 1
        
        logger.info(f"Detected {anomalies_detected} attendance anomalies for institution {institution_id}")
        return anomalies_detected
        
    except Exception as e:
        logger.error(f"Error detecting attendance anomalies: {e}")
        return 0


def _calculate_time_variance(times):
    """
    Calculate variance in times (in seconds)
    """
    if len(times) < 2:
        return 0
    
    # Convert times to seconds from midnight
    seconds = [t.hour * 3600 + t.minute * 60 + t.second for t in times]
    
    # Calculate variance
    mean = sum(seconds) / len(seconds)
    variance = sum((x - mean) ** 2 for x in seconds) / len(seconds)
    
    return variance


@shared_task
def send_attendance_reminders():
    """
    Send attendance reminders to students and lecturers
    """
    try:
        reminders_sent = 0
        
        # Get upcoming sessions (next 2 hours)
        upcoming_start = timezone.now()
        upcoming_end = timezone.now() + timedelta(hours=2)
        
        upcoming_sessions = AttendanceSession.objects.filter(
            start_time__gte=upcoming_start,
            start_time__lte=upcoming_end,
            is_active=True,
            is_deleted=False
        ).select_related('course', 'lecturer')
        
        for session in upcoming_sessions:
            # Send reminder to lecturer
            if session.lecturer:
                Notification.objects.create(
                    user=session.lecturer,
                    institution=session.institution,
                    title='Upcoming Attendance Session',
                    message=f'Your attendance session "{session.title}" starts at {session.start_time.strftime("%H:%M")}',
                    notification_type='attendance_reminder',
                    metadata={
                        'session_id': session.id,
                        'session_code': session.session_code,
                        'start_time': session.start_time.isoformat()
                    }
                )
                reminders_sent += 1
            
            # Send reminder to enrolled students
            enrolled_students = session.course.enrollments.filter(status='enrolled')
            for enrollment in enrolled_students:
                # Check if student hasn't already marked attendance
                if not AttendanceRecord.objects.filter(
                    session=session,
                    student=enrollment.student,
                    is_deleted=False
                ).exists():
                    Notification.objects.create(
                        user=enrollment.student,
                        institution=session.institution,
                        title='Upcoming Class',
                        message=f'Your class "{session.course.title}" starts at {session.start_time.strftime("%H:%M")}. Session code: {session.session_code}',
                        notification_type='attendance_reminder',
                        metadata={
                            'session_id': session.id,
                            'session_code': session.session_code,
                            'course_title': session.course.title,
                            'start_time': session.start_time.isoformat()
                        }
                    )
                    reminders_sent += 1
        
        logger.info(f"Sent {reminders_sent} attendance reminders")
        return reminders_sent
        
    except Exception as e:
        logger.error(f"Error sending attendance reminders: {e}")
        return 0


@shared_task
def cleanup_old_attendance_records():
    """
    Clean up old attendance records based on retention policy
    """
    try:
        # Get attendance settings for each institution
        from apps.institutions.models import Institution
        institutions = Institution.objects.filter(is_active=True)
        
        cleaned_records = 0
        
        for institution in institutions:
            # Get retention settings (default 2 years)
            try:
                settings = AttendanceSettings.objects.get(institution=institution)
                retention_days = 730  # 2 years default
            except AttendanceSettings.DoesNotExist:
                retention_days = 730
            
            cutoff_date = timezone.now() - timedelta(days=retention_days)
            
            # Soft delete old records
            old_records = AttendanceRecord.objects.filter(
                institution=institution,
                marked_at__lt=cutoff_date,
                is_deleted=False
            )
            
            count = old_records.count()
            old_records.update(is_deleted=True)
            
            cleaned_records += count
        
        logger.info(f"Cleaned up {cleaned_records} old attendance records")
        return cleaned_records
        
    except Exception as e:
        logger.error(f"Error cleaning up old attendance records: {e}")
        return 0


@shared_task
def generate_daily_attendance_reports():
    """
    Generate daily attendance reports for institutions
    """
    try:
        today = timezone.now().date()
        
        from apps.institutions.models import Institution
        institutions = Institution.objects.filter(is_active=True)
        
        reports_generated = 0
        
        for institution in institutions:
            # Get today's sessions
            today_sessions = AttendanceSession.objects.filter(
                institution=institution,
                start_time__date=today,
                is_deleted=False
            ).select_related('course', 'lecturer')
            
            if today_sessions.exists():
                # Calculate daily statistics
                total_sessions = today_sessions.count()
                total_enrolled = sum(s.total_enrolled for s in today_sessions)
                total_present = sum(s.total_present for s in today_sessions)
                total_absent = sum(s.total_absent for s in today_sessions)
                
                attendance_rate = (total_present / total_enrolled * 100) if total_enrolled > 0 else 0
                
                # Create daily statistics record
                AttendanceStatistics.objects.update_or_create(
                    institution=institution,
                    statistics_type='daily',
                    reference_id=None,
                    reference_date=today,
                    defaults={
                        'total_sessions': total_sessions,
                        'total_attendance_records': total_present + total_absent,
                        'present_count': total_present,
                        'absent_count': total_absent,
                        'attendance_rate': attendance_rate,
                        'engagement_score': attendance_rate
                    }
                )
                
                # Send daily report to admins
                admin_users = institution.users.filter(role='institution_admin')
                for admin in admin_users:
                    Notification.objects.create(
                        user=admin,
                        institution=institution,
                        title='Daily Attendance Report',
                        message=f'Today\'s attendance: {attendance_rate:.1f}% across {total_sessions} sessions',
                        notification_type='daily_report',
                        metadata={
                            'date': str(today),
                            'attendance_rate': attendance_rate,
                            'total_sessions': total_sessions
                        }
                    )
                
                reports_generated += 1
        
        logger.info(f"Generated {reports_generated} daily attendance reports")
        return reports_generated
        
    except Exception as e:
        logger.error(f"Error generating daily attendance reports: {e}")
        return 0


@shared_task
def analyze_dropout_risks():
    """
    Analyze dropout risks based on attendance patterns
    """
    try:
        from apps.institutions.models import Institution
        institutions = Institution.objects.filter(is_active=True)
        
        risks_identified = 0
        
        for institution in institutions:
            # Get students with concerning attendance patterns
            cutoff_date = timezone.now() - timedelta(days=30)
            
            at_risk_students = AttendancePattern.objects.filter(
                institution=institution,
                analysis_end_date__gte=cutoff_date,
                risk_level__in=['high', 'critical']
            ).select_related('student')
            
            for pattern in at_risk_students:
                # Calculate dropout risk score
                dropout_risk = 0
                
                if pattern.risk_level == 'critical':
                    dropout_risk = 85
                elif pattern.risk_level == 'high':
                    dropout_risk = 70
                
                # Adjust based on attendance rate
                if pattern.average_attendance_rate < 50:
                    dropout_risk = min(100, dropout_risk + 20)
                elif pattern.average_attendance_rate < 60:
                    dropout_risk = min(100, dropout_risk + 10)
                
                # Create or update alert
                AttendanceAlert.objects.update_or_create(
                    institution=institution,
                    student=pattern.student,
                    alert_type='dropout_risk',
                    severity='critical' if dropout_risk >= 80 else 'high',
                    defaults={
                        'title': 'Dropout Risk Alert',
                        'description': f'Student {pattern.student.get_full_name()} shows high dropout risk ({dropout_risk}%)',
                        'threshold_value=70.0,
                        'actual_value': dropout_risk,
                        'alert_data': {
                            'dropout_risk_score': dropout_risk,
                            'attendance_rate': pattern.average_attendance_rate,
                            'pattern_type': pattern.pattern_type,
                            'anomaly_count': pattern.anomaly_count
                        }
                    }
                )
                
                risks_identified += 1
        
        logger.info(f"Identified {risks_identified} dropout risks")
        return risks_identified
        
    except Exception as e:
        logger.error(f"Error analyzing dropout risks: {e}")
        return 0


@shared_task
def sync_attendance_with_external_systems():
    """
    Sync attendance data with external systems (LMS, SIS)
    """
    try:
        from apps.institutions.models import Institution
        institutions = Institution.objects.filter(is_active=True)
        
        synced_records = 0
        
        for institution in institutions:
            # Get attendance settings to check if sync is enabled
            try:
                settings = AttendanceSettings.objects.get(institution=institution)
                
                # This would integrate with external systems
                # For now, just log the action
                recent_records = AttendanceRecord.objects.filter(
                    institution=institution,
                    marked_at__gte=timezone.now() - timedelta(hours=1),
                    is_deleted=False
                ).count()
                
                if recent_records > 0:
                    logger.info(f"Would sync {recent_records} attendance records for {institution.name}")
                    synced_records += recent_records
                
            except AttendanceSettings.DoesNotExist:
                pass
        
        logger.info(f"Synced {synced_records} attendance records with external systems")
        return synced_records
        
    except Exception as e:
        logger.error(f"Error syncing attendance with external systems: {e}")
        return 0


@shared_task
def detect_proxy_attendance():
    """
    Advanced proxy attendance detection using behavioral analysis
    """
    try:
        from apps.institutions.models import Institution
        institutions = Institution.objects.filter(is_active=True)
        
        proxy_cases_detected = 0
        
        for institution in institutions:
            # Get recent attendance records
            cutoff_date = timezone.now() - timedelta(days=7)
            recent_records = AttendanceRecord.objects.filter(
                institution=institution,
                marked_at__gte=cutoff_date,
                is_deleted=False
            ).select_related('student', 'session')
            
            # Group by session
            sessions = {}
            for record in recent_records:
                session_id = record.session.id
                if session_id not in sessions:
                    sessions[session_id] = {
                        'session': record.session,
                        'records': []
                    }
                sessions[session_id]['records'].append(record)
            
            # Analyze each session for proxy patterns
            for session_id, data in sessions.items():
                session = data['session']
                records = data['records']
                
                proxy_indicators = []
                
                # Check for multiple marks from same IP in short time
                ip_groups = {}
                for record in records:
                    ip = record.ip_address
                    if ip not in ip_groups:
                        ip_groups[ip] = []
                    ip_groups[ip].append(record)
                
                for ip, ip_records in ip_groups.items():
                    if len(ip_records) > 3:  # More than 3 students from same IP
                        time_span = max(r.marked_at for r in ip_records) - min(r.marked_at for r in ip_records)
                        if time_span.total_seconds() < 300:  # Within 5 minutes
                            proxy_indicators.append({
                                'type': 'multiple_same_ip',
                                'severity': 'high',
                                'ip': ip,
                                'count': len(ip_records),
                                'time_span': time_span.total_seconds()
                            })
                
                # Check for identical device fingerprints
                fingerprint_groups = {}
                for record in records:
                    fp = record.device_fingerprint
                    if fp:
                        if fp not in fingerprint_groups:
                            fingerprint_groups[fp] = []
                        fingerprint_groups[fp].append(record)
                
                for fp, fp_records in fingerprint_groups.items():
                    if len(fp_records) > 2:  # More than 2 students with same fingerprint
                        proxy_indicators.append({
                            'type': 'identical_fingerprint',
                            'severity': 'critical',
                            'fingerprint': fp,
                            'count': len(fp_records)
                        })
                
                # Check for sequential marking patterns
                sorted_records = sorted(records, key=lambda x: x.marked_at)
                for i in range(len(sorted_records) - 1):
                    time_diff = (sorted_records[i + 1].marked_at - sorted_records[i].marked_at).total_seconds()
                    if time_diff < 5:  # Less than 5 seconds between marks
                        proxy_indicators.append({
                            'type': 'sequential_marking',
                            'severity': 'medium',
                            'time_diff': time_diff
                        })
                
                # Create alerts for proxy indicators
                if proxy_indicators:
                    for indicator in proxy_indicators:
                        # Mark records as suspicious
                        for record in records:
                            record.is_suspicious = True
                            record.security_flags = record.security_flags + [f'proxy_{indicator["type"]}']
                            record.save()
                        
                        # Create alert
                        AttendanceAlert.objects.create(
                            institution=institution,
                            alert_type='proxy_detection',
                            severity=indicator['severity'],
                            title='Proxy Attendance Detected',
                            description=f'Proxy attendance pattern detected: {indicator["type"]}',
                            session=session,
                            alert_data=indicator
                        )
                        
                        proxy_cases_detected += 1
        
        logger.info(f"Detected {proxy_cases_detected} proxy attendance cases")
        return proxy_cases_detected
        
    except Exception as e:
        logger.error(f"Error detecting proxy attendance: {e}")
        return 0


@shared_task
def update_attendance_patterns():
    """
    Update attendance patterns for all students
    """
    try:
        from apps.institutions.models import Institution
        institutions = Institution.objects.filter(is_active=True)
        
        patterns_updated = 0
        
        for institution in institutions:
            # Get all students
            students = institution.users.filter(role='student', is_active=True)
            
            for student in students:
                # Get attendance records for last 30 days
                cutoff_date = timezone.now() - timedelta(days=30)
                records = AttendanceRecord.objects.filter(
                    student=student,
                    marked_at__gte=cutoff_date,
                    is_deleted=False
                ).select_related('session', 'session__course')
                
                if records.exists():
                    # Analyze pattern
                    pattern_data = _analyze_student_pattern(student, records)
                    
                    # Update or create pattern
                    AttendancePattern.objects.update_or_create(
                        institution=institution,
                        student=student,
                        course=None,
                        analysis_start_date=cutoff_date,
                        analysis_end_date=timezone.now().date(),
                        defaults=pattern_data
                    )
                    
                    patterns_updated += 1
        
        logger.info(f"Updated attendance patterns for {patterns_updated} students")
        return patterns_updated
        
    except Exception as e:
        logger.error(f"Error updating attendance patterns: {e}")
        return 0


def _analyze_student_pattern(student, records):
    """
    Analyze a student's attendance pattern
    """
    total_records = len(records)
    present_count = len([r for r in records if r.status == 'present'])
    late_count = len([r for r in records if r.status == 'late'])
    absent_count = len([r for r in records if r.status == 'absent'])
    
    attendance_rate = (present_count / total_records * 100) if total_records > 0 else 0
    
    # Determine pattern type
    pattern_type = 'normal'
    risk_level = 'low'
    confidence_score = 100
    
    if attendance_rate < 60:
        pattern_type = 'declining'
        risk_level = 'high'
        confidence_score = 85
    elif attendance_rate < 75:
        pattern_type = 'erratic'
        risk_level = 'medium'
        confidence_score = 70
    
    # Check for suspicious activity
    suspicious_count = len([r for r in records if r.is_suspicious])
    if suspicious_count > total_records * 0.2:
        pattern_type = 'suspicious'
        risk_level = 'critical'
        confidence_score = 95
    
    return {
        'pattern_type': pattern_type,
        'confidence_score': confidence_score,
        'risk_level': risk_level,
        'average_attendance_rate': attendance_rate,
        'attendance_variance': _calculate_attendance_variance(records),
        'consistency_score': 100 - confidence_score,
        'anomaly_count': suspicious_count,
        'last_anomaly_date': max([r.marked_at for r in records if r.is_suspicious]) if suspicious_count > 0 else None,
        'total_sessions_analyzed': total_records
    }


def _calculate_attendance_variance(records):
    """
    Calculate variance in attendance patterns
    """
    if len(records) < 2:
        return 0.0
    
    # Simple variance calculation based on status
    status_values = {'present': 1, 'late': 0.5, 'absent': 0, 'excused': 0.75}
    values = [status_values.get(r.status, 0) for r in records]
    
    mean = sum(values) / len(values)
    variance = sum((x - mean) ** 2 for x in values) / len(values)
    
    return variance
