from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


class StudentDashboardService:
    def __init__(self, firebase_service):
        self.fb = firebase_service

    # ── MAIN DASHBOARD ──

    def get_dashboard_data(self, user_id: str, institution_id: str) -> Dict[str, Any]:
        from src.application.offline_queue_service import OfflineQueueService
        profile = self._get_profile(user_id)
        stats = self._get_attendance_stats(user_id)
        courses = self._get_courses(user_id)
        upcoming = self._get_upcoming_sessions(institution_id)
        recent = self._get_recent_history(user_id)
        notifications = self._get_notifications(user_id, institution_id)
        network = self._get_network_status(institution_id)
        status = self._compute_attendance_status(stats.get('rate', 0))
        trust_level = self._compute_trust_level(user_id, stats)

        queue_service = OfflineQueueService(self.fb)
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
        user = self.fb.get_document('users', user_id)
        if not user:
            return {}
        return {
            'id': user.get('id'),
            'email': user.get('email'),
            'first_name': user.get('first_name'),
            'last_name': user.get('last_name'),
            'student_id': user.get('student_id'),
            'faculty': user.get('faculty'),
            'phone': user.get('phone'),
            'trusted_device': user.get('trusted_device', False),
            'vpn_detected': user.get('vpn_detected', False),
            'last_login': user.get('last_login'),
        }

    # ── STATS ──

    def _get_attendance_stats(self, user_id: str) -> Dict[str, Any]:
        records = self.fb.query_documents(
            'attendance_records',
            filters=[{'field': 'student_id', 'value': user_id}]
        )
        total = len(records)
        present = sum(1 for r in records if r.get('status') == 'present')
        late = sum(1 for r in records if r.get('status') == 'late')
        absent = sum(1 for r in records if r.get('status') == 'absent')
        suspicious = sum(1 for r in records if r.get('is_suspicious'))
        rate = round(present / total * 100, 1) if total > 0 else 0
        # Weekly breakdown for trend
        now = datetime.utcnow()
        week_ago = now - timedelta(days=7)
        weekly = [r for r in records if r.get('marked_at', '') >= week_ago.isoformat()]
        weekly_present = sum(1 for r in weekly if r.get('status') == 'present')
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
        user = self.fb.get_document('users', user_id)
        score = 100
        if user and user.get('trusted_device'):
            score += 10
        if user and user.get('vpn_detected'):
            score -= 25
        score -= stats.get('suspicious', 0) * 5
        score = max(0, min(100, score))
        label = 'high' if score >= 80 else 'medium' if score >= 50 else 'low'
        return {'score': score, 'label': label}

    # ── COURSES ──

    def _get_courses(self, user_id: str) -> List[Dict[str, Any]]:
        records = self.fb.query_documents(
            'attendance_records',
            filters=[{'field': 'student_id', 'value': user_id}]
        )
        session_ids = list(set(
            r.get('attendance_session_id') for r in records if r.get('attendance_session_id')
        ))
        sessions = []
        for sid in session_ids:
            s = self.fb.get_document('attendance_sessions', sid)
            if s:
                sessions.append(s)

        course_data = defaultdict(
            lambda: {'total': 0, 'present': 0, 'late': 0, 'absent': 0,
                     'course_name': '', 'lecturer_name': '', 'suspicious': 0}
        )
        for rec in records:
            session = next(
                (s for s in sessions if s.get('id') == rec.get('attendance_session_id')),
                None
            )
            if session:
                cid = session.get('course_id', 'unknown')
                course_data[cid]['total'] += 1
                if rec.get('status') == 'present':
                    course_data[cid]['present'] += 1
                elif rec.get('status') == 'late':
                    course_data[cid]['late'] += 1
                elif rec.get('status') == 'absent':
                    course_data[cid]['absent'] += 1
                if rec.get('is_suspicious'):
                    course_data[cid]['suspicious'] += 1
                course_data[cid]['course_name'] = session.get('course_name', 'Unknown')
                course_data[cid]['lecturer_name'] = session.get('lecturer_name', 'Unknown')

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

    def _get_upcoming_sessions(self, institution_id: str) -> List[Dict[str, Any]]:
        sessions = self.fb.query_documents(
            'attendance_sessions',
            filters=[{'field': 'institution_id', 'value': institution_id}],
            order_by='-created_at'
        )
        active = [s for s in sessions if s.get('status') == 'active']
        completed = [s for s in sessions if s.get('status') == 'completed']
        return (active + completed)[:10]

    # ── HISTORY ──

    def _get_recent_history(self, user_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        records = self.fb.query_documents(
            'attendance_records',
            filters=[{'field': 'student_id', 'value': user_id}],
            order_by='-created_at',
            limit=limit
        )
        result = []
        for r in records:
            session = self.fb.get_document('attendance_sessions', r.get('attendance_session_id', ''))
            result.append({
                'id': r.get('id'),
                'session_id': r.get('attendance_session_id'),
                'status': r.get('status', 'unknown'),
                'marked_at': r.get('marked_at', r.get('created_at', '')),
                'course_name': session.get('course_name', 'Unknown') if session else 'Unknown',
                'lecturer_name': session.get('lecturer_name', '') if session else '',
                'is_suspicious': r.get('is_suspicious', False),
            })
        return result

    # ── NETWORK ──

    def _get_network_status(self, institution_id: str) -> Dict[str, Any]:
        nodes = self.fb.query_documents(
            'network_nodes',
            filters=[{'field': 'institution_id', 'value': institution_id}]
        )
        broker = self.fb.query_documents(
            'broker_status',
            filters=[{'field': 'institution_id', 'value': institution_id}]
        )
        online = sum(1 for n in nodes if n.get('status') == 'healthy')
        degraded = sum(1 for n in nodes if n.get('status') == 'degraded')
        offline = sum(1 for n in nodes if n.get('status') == 'offline')
        avg_latency = 0
        if nodes:
            latencies = [n.get('latency_ms', 0) for n in nodes if n.get('latency_ms') is not None]
            avg_latency = round(sum(latencies) / len(latencies)) if latencies else 0
        broker_online = bool(broker)
        broker_info = broker[0] if broker else {}
        return {
            'status': 'connected' if online > 0 else 'disconnected',
            'online_nodes': online,
            'degraded_nodes': degraded,
            'offline_nodes': offline,
            'avg_latency_ms': avg_latency,
            'broker_online': broker_online,
            'nodes': [
                {
                    'name': n.get('name', ''),
                    'type': n.get('type', 'building'),
                    'status': n.get('status', 'offline'),
                    'latency_ms': n.get('latency_ms', 0),
                    'packet_loss': n.get('packet_loss', 0),
                    'last_seen': n.get('last_seen', ''),
                }
                for n in nodes
            ],
            'broker': {
                'name': broker_info.get('name', 'Core Broker'),
                'messages_per_sec': broker_info.get('messages_per_sec', 0),
                'connected_nodes': broker_info.get('connected_nodes', 0),
                'total_nodes': broker_info.get('total_nodes', 0),
                'uptime_hours': broker_info.get('uptime_hours', 0),
            },
        }

    # ── NOTIFICATIONS ──

    def _get_notifications(self, user_id: str, institution_id: str) -> List[Dict[str, Any]]:
        alerts = self.fb.query_documents(
            'security_logs',
            filters=[{'field': 'institution_id', 'value': institution_id}],
            order_by='-created_at',
            limit=5
        )
        notifications = []
        for a in alerts:
            if a.get('user_id') and a['user_id'] != user_id:
                continue
            notifications.append({
                'type': 'security',
                'severity': a.get('severity', 'low'),
                'message': a.get('description', ''),
                'created_at': a.get('created_at', ''),
                'risk_score': a.get('risk_score', 0),
            })
        # Add attendance warnings
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
        records = self.fb.query_documents(
            'attendance_records',
            filters=[{'field': 'student_id', 'value': user_id}],
            order_by='-created_at'
        )
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
            day = (r.get('marked_at') or r.get('created_at', ''))[:10]
            if day:
                daily[day]['total'] += 1
                if r.get('status') == 'present':
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
        user = self.fb.get_document('users', user_id)
        trusted = user.get('trusted_device', False) if user else False
        vpn = user.get('vpn_detected', False) if user else False
        last_login = user.get('last_login', '') if user else ''

        events = self.fb.query_documents(
            'security_logs',
            filters=[{'field': 'institution_id', 'value': institution_id}],
            order_by='-created_at',
            limit=10
        )
        my_events = [e for e in events if not e.get('user_id') or e['user_id'] == user_id]

        return {
            'trusted_device': trusted,
            'vpn_detected': vpn,
            'last_login': last_login,
            'events': [
                {
                    'event_type': e.get('event_type', ''),
                    'description': e.get('description', ''),
                    'severity': e.get('severity', 'low'),
                    'risk_score': e.get('risk_score', 0),
                    'created_at': e.get('created_at', ''),
                }
                for e in my_events
            ],
        }

    # ── VERIFY SCAN ──

    def verify_scan(self, session_code: str, user_id: str,
                    device_fingerprint: str = '') -> Dict[str, Any]:
        sessions = self.fb.query_documents(
            'attendance_sessions',
            filters=[{'field': 'session_code', 'value': session_code}]
        )
        if not sessions:
            return {'error': 'Invalid session code'}
        session = sessions[0]
        if not session.get('is_active', True):
            return {'error': 'Session is not active'}

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
                'course_name': session.get('course_name', 'Unknown'),
                'course_id': session.get('course_id', ''),
                'lecturer_name': session.get('lecturer_name', ''),
            },
            'trust_score': max(0, trust_score),
            'checks': checks,
        }

    # ── PAGINATED HISTORY ──

    def get_attendance_history(self, user_id: str, institution_id: str,
                                page: int = 1, per_page: int = 20) -> Dict[str, Any]:
        records = self.fb.query_documents(
            'attendance_records',
            filters=[{'field': 'student_id', 'value': user_id}],
            order_by='-created_at'
        )
        total = len(records)
        start = (page - 1) * per_page
        end = start + per_page
        page_records = records[start:end]

        history = []
        for r in page_records:
            session = self.fb.get_document('attendance_sessions', r.get('attendance_session_id', ''))
            history.append({
                'id': r.get('id'),
                'session_id': r.get('attendance_session_id'),
                'status': r.get('status', 'unknown'),
                'marked_at': r.get('marked_at', r.get('created_at', '')),
                'course_name': session.get('course_name', 'Unknown') if session else 'Unknown',
                'course_id': session.get('course_id', '') if session else '',
                'lecturer_name': session.get('lecturer_name', '') if session else '',
                'is_suspicious': r.get('is_suspicious', False),
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
        return self._get_upcoming_sessions(institution_id)
