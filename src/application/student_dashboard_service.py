from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from collections import defaultdict
import logging

from src.infrastructure.pg_repositories import pg_repos
from src.infrastructure.models import AttendanceRecord as PGAttendanceRecord

logger = logging.getLogger(__name__)


class StudentDashboardService:
    def __init__(self):
        self._course_cache = {}

    def _get_course_info(self, course_id: str) -> Optional[Dict[str, Any]]:
        if not course_id:
            return None
        if course_id not in self._course_cache:
            course = pg_repos.course.get(course_id)
            if not course:
                self._course_cache[course_id] = None
            else:
                lecturer_name = ''
                if course.lecturer_id:
                    lecturer = pg_repos.user.get(course.lecturer_id)
                    if lecturer:
                        profile = pg_repos.user_profile.get_by_user(course.lecturer_id)
                        if profile:
                            lecturer_name = f"{profile.first_name or ''} {profile.last_name or ''}".strip()
                        else:
                            lecturer_name = lecturer.email or ''
                self._course_cache[course_id] = {
                    'name': course.name or '',
                    'lecturer_name': lecturer_name,
                }
        return self._course_cache[course_id]

    def _enrich_session(self, session_id: str) -> Dict[str, Any]:
        session = pg_repos.attendance_session.get(session_id)
        if not session:
            return {}
        enriched = {
            'id': session.id,
            'session_code': session.session_code,
            'course_id': session.course_id,
            'lecturer_id': session.lecturer_id,
            'is_active': session.is_active,
            'start_time': session.start_time.isoformat() if session.start_time else None,
            'end_time': session.end_time.isoformat() if session.end_time else None,
            'created_at': session.created_at.isoformat() if session.created_at else None,
        }
        cinfo = self._get_course_info(session.course_id)
        if cinfo:
            enriched['course_name'] = cinfo['name']
            enriched['lecturer_name'] = cinfo['lecturer_name']
        if session.is_active and session.session_code:
            try:
                from src.application.attendance_security_service import AttendanceSecurityService
                sec_svc = AttendanceSecurityService()
                enriched['qr_code'] = sec_svc._generate_qr_code(session.session_code)
            except Exception:
                pass
        return enriched

    # ── MAIN DASHBOARD ──

    def get_dashboard_data(self, user_id: str, institution_id: str) -> Dict[str, Any]:
        from src.application.offline_queue_service import OfflineQueueService
        profile = self._get_profile(user_id)
        stats = self._get_attendance_stats(user_id)
        courses = self._get_courses(user_id)
        upcoming = self._get_upcoming_sessions(institution_id, user_id)
        recent = self._get_recent_history(user_id)
        notifications = self._get_notifications(user_id, institution_id)
        network = self._get_network_status(institution_id)
        status = self._compute_attendance_status(stats.get('rate', 0))
        trust_level = self._compute_trust_level(user_id, stats)

        queue_service = OfflineQueueService()
        queue_stats = queue_service.get_queue_stats(institution_id)
        sync_estimate = queue_service.estimate_sync_duration(institution_id)

        return {
            'profile': profile,
            'stats': stats,
            'courses': courses,
            'upcoming': upcoming,
            'recent': recent,
            'notifications': notifications,
            'network': network,
            'attendance_status': status,
            'trust_level': trust_level,
            'queue_stats': queue_stats,
            'sync_estimate': sync_estimate,
        }

    # ── PROFILE ──

    def _get_profile(self, user_id: str) -> Dict[str, Any]:
        user = pg_repos.user.get(user_id)
        if not user:
            return {}
        profile = pg_repos.user_profile.get_by_user(user_id)
        return {
            'id': user.id,
            'email': user.email,
            'first_name': profile.first_name if profile else '',
            'last_name': profile.last_name if profile else '',
            'student_id': profile.student_id if profile else '',
            'faculty': profile.department_id if profile else '',
            'phone': profile.phone if profile else '',
            'trusted_device': False,
            'vpn_detected': False,
            'last_login': user.updated_at.isoformat() if user.updated_at else None,
        }

    # ── STATS ──

    def _get_attendance_stats(self, user_id: str) -> Dict[str, Any]:
        records = pg_repos.attendance_record.get_by_student(user_id)
        total = len(records)
        present = sum(1 for r in records if r.status and r.status.value == 'present')
        late = sum(1 for r in records if r.status and r.status.value == 'late')
        absent = sum(1 for r in records if r.status and r.status.value == 'absent')
        suspicious = 0
        rate = round(present / total * 100, 1) if total > 0 else 0
        now = datetime.utcnow()
        week_ago = now - timedelta(days=7)
        weekly = [r for r in records if r.marked_at and r.marked_at > week_ago]
        weekly_present = sum(1 for r in weekly if r.status and r.status.value == 'present')
        weekly_rate = round(weekly_present / len(weekly) * 100, 1) if weekly else rate
        return {
            'total': total,
            'present': present,
            'late': late,
            'absent': absent,
            'suspicious': suspicious,
            'rate': rate,
            'weekly_rate': weekly_rate,
        }

    def _compute_attendance_status(self, rate: float) -> str:
        if rate >= 75:
            return 'safe'
        elif rate >= 50:
            return 'at_risk'
        else:
            return 'critical'

    def _compute_trust_level(self, user_id: str, stats: Dict[str, Any]) -> Dict[str, Any]:
        score = 100
        score -= stats.get('suspicious', 0) * 5
        score = max(0, min(100, score))
        label = 'high' if score >= 80 else 'medium' if score >= 50 else 'low'
        return {'score': score, 'label': label}

    # ── COURSES ──

    def _get_courses(self, user_id: str) -> List[Dict[str, Any]]:
        records = pg_repos.attendance_record.get_by_student(user_id)
        session_ids = list(set(r.session_id for r in records if r.session_id))
        sessions = {}
        for sid in session_ids:
            s = pg_repos.attendance_session.get(sid)
            if s:
                sessions[s.id] = s

        course_data = defaultdict(
            lambda: {'total': 0, 'present': 0, 'late': 0, 'absent': 0,
                     'course_name': '', 'lecturer_name': '', 'suspicious': 0}
        )
        for rec in records:
            session = sessions.get(rec.session_id)
            if session:
                enriched = self._enrich_session(session.id)
                cid = enriched.get('course_id', 'unknown')
                course_data[cid]['total'] += 1
                status = rec.status.value if rec.status else 'present'
                if status == 'present':
                    course_data[cid]['present'] += 1
                elif status == 'late':
                    course_data[cid]['late'] += 1
                elif status == 'absent':
                    course_data[cid]['absent'] += 1
                course_data[cid]['course_name'] = enriched.get('course_name', '') or 'Unknown'
                course_data[cid]['lecturer_name'] = enriched.get('lecturer_name', '') or ''

        enrollments = pg_repos.course_enrollment.get_by_student(user_id)
        for e in enrollments:
            cid = e.course_id
            if cid and cid not in course_data:
                cinfo = self._get_course_info(cid)
                course_data[cid] = {
                    'total': 0, 'present': 0, 'late': 0, 'absent': 0,
                    'course_name': cinfo['name'] if cinfo else 'Unknown',
                    'lecturer_name': cinfo['lecturer_name'] if cinfo else '',
                    'suspicious': 0
                }

        courses = []
        for cid, data in course_data.items():
            rate = round(data['present'] / data['total'] * 100, 1) if data['total'] > 0 else 0
            risk = 'low' if rate >= 75 else 'medium' if rate >= 50 else 'high'
            courses.append({
                'course_id': cid,
                'course_name': data['course_name'],
                'lecturer_name': data['lecturer_name'],
                'total': data['total'],
                'present': data['present'],
                'late': data['late'],
                'absent': data['absent'],
                'suspicious': data['suspicious'],
                'rate': rate,
                'risk': risk,
            })
        return courses

    # ── SESSIONS ──

    def _get_upcoming_sessions(self, institution_id: str, user_id: str = None) -> List[Dict[str, Any]]:
        sessions = pg_repos.attendance_session.query(institution_id=institution_id)
        enrolled_course_ids = None
        if user_id:
            enrollments = pg_repos.course_enrollment.get_by_student(user_id)
            enrolled_course_ids = {e.course_id for e in enrollments if e.course_id}
        if enrolled_course_ids:
            sessions = [s for s in sessions if s.course_id in enrolled_course_ids]
        enriched = [self._enrich_session(s.id) for s in sessions]
        active = [s for s in enriched if s.get('is_active') == True]
        completed = [s for s in enriched if s.get('is_active') == False]
        return (active + completed)[:10]

    # ── HISTORY ──

    def _get_recent_history(self, user_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        records = pg_repos.attendance_record.get_recent_attendance(user_id, limit)
        result = []
        for r in records:
            enriched = self._enrich_session(r.session_id) if r.session_id else {}
            result.append({
                'id': r.id,
                'session_id': r.session_id,
                'status': r.status.value if r.status else 'unknown',
                'marked_at': r.marked_at.isoformat() if r.marked_at else (r.created_at.isoformat() if r.created_at else ''),
                'course_name': enriched.get('course_name', 'Unknown'),
                'lecturer_name': enriched.get('lecturer_name', ''),
                'is_suspicious': False,
            })
        return result

    # ── NETWORK ──

    def _get_network_status(self, institution_id: str) -> Dict[str, Any]:
        return {
            'status': 'connected',
            'online_nodes': 0,
            'degraded_nodes': 0,
            'offline_nodes': 0,
            'avg_latency_ms': 0,
            'broker_online': False,
            'nodes': [],
            'broker': {
                'name': 'Core Broker',
                'messages_per_sec': 0,
                'connected_nodes': 0,
                'total_nodes': 0,
                'uptime_hours': 0,
            },
        }

    # ── NOTIFICATIONS ──

    def _get_notifications(self, user_id: str, institution_id: str) -> List[Dict[str, Any]]:
        notifications = []
        try:
            alerts = pg_repos.security_logs.get_security_alerts(institution_id, limit=5)
            for a in alerts:
                if a.user_id and a.user_id != user_id:
                    continue
                notifications.append({
                    'type': 'security',
                    'severity': a.severity or 'low',
                    'message': a.description or '',
                    'created_at': a.created_at.isoformat() if a.created_at else '',
                    'risk_score': 0,
                })
        except Exception:
            pass
        stats = self._get_attendance_stats(user_id)
        if stats.get('rate', 100) < 75:
            notifications.append({
                'type': 'warning',
                'severity': 'critical',
                'message': 'Your attendance rate is below 75%',
                'created_at': datetime.utcnow().isoformat(),
                'risk_score': 0,
            })
        elif stats.get('rate', 100) < 85:
            notifications.append({
                'type': 'warning',
                'severity': 'medium',
                'message': 'Your attendance rate is approaching the minimum threshold',
                'created_at': datetime.utcnow().isoformat(),
                'risk_score': 0,
            })
        return notifications[:10]

    # ── ANALYTICS ──

    def get_analytics(self, user_id: str, institution_id: str) -> Dict[str, Any]:
        records = pg_repos.attendance_record.get_by_student(user_id)
        courses = self._get_courses(user_id)
        stats = self._get_attendance_stats(user_id)

        daily_rates = self._compute_daily_trend(records)
        lowest_course = min(courses, key=lambda c: c['rate']) if courses else None
        total_late = stats.get('late', 0)
        total_suspicious = stats.get('suspicious', 0)

        return {
            'daily_rates': daily_rates,
            'lowest_course': lowest_course,
            'total_late': total_late,
            'total_suspicious': total_suspicious,
            'courses': courses,
        }

    def _compute_daily_trend(self, records: List) -> List[Dict[str, Any]]:
        daily = defaultdict(lambda: {'total': 0, 'present': 0})
        for r in records:
            day = (r.marked_at or r.created_at).strftime('%Y-%m-%d') if (r.marked_at or r.created_at) else ''
            if day:
                daily[day]['total'] += 1
                if r.status and r.status.value == 'present':
                    daily[day]['present'] += 1
        days = []
        for i in range(13, -1, -1):
            d = (datetime.utcnow() - timedelta(days=i)).strftime('%Y-%m-%d')
            info = daily.get(d, {'total': 0, 'present': 0})
            rate = round(info['present'] / info['total'] * 100, 1) if info['total'] > 0 else None
            days.append({'date': d, 'rate': rate, 'is_future': info['total'] == 0})
        return days

    # ── SECURITY ──

    def get_security_data(self, user_id: str, institution_id: str) -> Dict[str, Any]:
        return {
            'trusted_device': False,
            'vpn_detected': False,
            'last_login': '',
            'events': [],
        }

    # ── VERIFY SCAN ──

    def verify_scan(self, session_code: str, user_id: str,
                    device_fingerprint: str = '') -> Dict[str, Any]:
        normalized_code = session_code.strip().upper()

        from src.application.attendance_security_service import AttendanceSecurityService
        att_sec = AttendanceSecurityService()
        server_validation = att_sec.validate_server_session(normalized_code)

        if not server_validation.get('valid'):
            logger.warning(f"verify_scan: server validation failed for code='{normalized_code}' user='{user_id}': {server_validation.get('error')}")
            return {'error': server_validation.get('error', 'Invalid session code')}

        session = server_validation['session']

        stored_code = (session.get('session_code') or '').strip().upper()
        if normalized_code != stored_code:
            return {'error': 'Invalid Session Code \u2192 STOP PROCESS'}

        trust_score = 95
        checks = {'Campus WiFi': True, 'Secure Session': True, 'Device Verified': True}
        if not device_fingerprint:
            trust_score -= 10
            checks['Device Verified'] = False
        now = datetime.utcnow()
        created = session.get('created_at', '')
        try:
            if created:
                start = datetime.fromisoformat(created.replace('Z', '+00:00'))
                elapsed = (now - start).total_seconds()
                if elapsed > 3600:
                    trust_score -= 15
                    checks['Secure Session'] = False
        except Exception:
            pass

        return {
            'verified': True,
            'session': {
                'course_name': session.get('course_name', '') or 'Unknown',
                'course_id': session.get('course_id', ''),
                'lecturer_name': session.get('lecturer_name', '') or '',
            },
            'trust_score': max(0, trust_score),
            'checks': checks,
        }

    # ── PAGINATED HISTORY ──

    def get_attendance_history(self, user_id: str, institution_id: str,
                               page: int = 1, per_page: int = 20) -> Dict[str, Any]:
        records = pg_repos.attendance_record.get_by_student(user_id)
        total = len(records)
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        page_records = records[start_idx:end_idx]

        history = []
        for r in page_records:
            enriched = self._enrich_session(r.session_id) if r.session_id else {}
            history.append({
                'id': r.id,
                'session_id': r.session_id,
                'status': r.status.value if r.status else 'unknown',
                'marked_at': r.marked_at.isoformat() if r.marked_at else (r.created_at.isoformat() if r.created_at else ''),
                'course_name': enriched.get('course_name', 'Unknown'),
                'course_id': enriched.get('course_id', ''),
                'lecturer_name': enriched.get('lecturer_name', ''),
                'is_suspicious': False,
            })

        return {
            'history': history,
            'total': total,
            'page': page,
            'per_page': per_page,
            'total_pages': max(1, (total + per_page - 1) // per_page),
        }

    # ── SCHEDULE ──

    def get_schedule(self, user_id: str, institution_id: str) -> List[Dict[str, Any]]:
        return self._get_upcoming_sessions(institution_id, user_id)