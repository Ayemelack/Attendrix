import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from collections import defaultdict

from src.infrastructure.repositories import (
    institution_repo, user_repo, attendance_session_repo, attendance_record_repo,
    audit_log_repo, security_log_repo, notification_repo, class_session_repo,
    schedule_repo, course_repo, department_repo, course_enrollment_repo,
    demo_booking_repo
)
from src.domain.entities import UserRole

logger = logging.getLogger(__name__)


class SuperAdminService:

    def get_system_overview(self) -> Dict[str, Any]:
        """Aggregate global system statistics across all institutions."""
        institutions = institution_repo.list_all() or []
        all_users = user_repo.list_all() or []
        all_attendance_records = attendance_record_repo.list_all() or []
        all_sessions = attendance_session_repo.list_all() or []
        all_security = security_log_repo.list_all() or []
        all_audit = audit_log_repo.list_all() or []
        all_bookings = demo_booking_repo.list_all() or []

        role_counts = defaultdict(int)
        for u in all_users:
            role_counts[u.get('role', 'unknown')] += 1

        active_sessions = [s for s in all_sessions if s.get('is_active')]
        suspicious_records = [r for r in all_attendance_records if r.get('is_suspicious')]

        high_risk_events = [e for e in all_security if (e.get('risk_score') or 0) >= 7]
        unresolved_security = [e for e in all_security if not e.get('is_resolved')]

        today = datetime.utcnow().date()
        today_records = [r for r in all_attendance_records
                         if r.get('created_at') and self._parse_date(r['created_at']) == today]

        present = sum(1 for r in today_records if r.get('status') == 'present')
        total_today = len(today_records)
        today_rate = round((present / total_today * 100) if total_today > 0 else 0, 1)

        return {
            'total_institutions': len([i for i in institutions if i.get('is_active', True)]),
            'total_users': len(all_users),
            'total_admins': role_counts.get('institutional_admin', 0),
            'total_lecturers': role_counts.get('lecturer', 0),
            'total_students': role_counts.get('student', 0),
            'total_attendance_records': len(all_attendance_records),
            'active_sessions': len(active_sessions),
            'suspicious_records': len(suspicious_records),
            'security_events': len(all_security),
            'high_risk_events': len(high_risk_events),
            'unresolved_alerts': len(unresolved_security),
            'audit_logs': len(all_audit),
            'demo_bookings': len(all_bookings),
            'today_attendance_rate': today_rate,
            'today_records': total_today,
            'today_present': present,
        }

    def get_institutions_with_stats(self) -> List[Dict[str, Any]]:
        """Get all institutions with per-institution statistics."""
        institutions = institution_repo.list_all() or []
        all_users = user_repo.list_all() or []
        all_records = attendance_record_repo.list_all() or []

        users_by_inst = defaultdict(list)
        for u in all_users:
            users_by_inst[u.get('institution_id', '')].append(u)

        records_by_inst = defaultdict(list)
        for r in all_records:
            records_by_inst[r.get('institution_id', '')].append(r)

        result = []
        for inst in institutions:
            inst_id = inst.get('id', '')
            inst_users = users_by_inst.get(inst_id, [])
            inst_records = records_by_inst.get(inst_id, [])
            suspicious = [r for r in inst_records if r.get('is_suspicious')]
            present = sum(1 for r in inst_records if r.get('status') == 'present')
            total = len(inst_records)

            result.append({
                'id': inst_id,
                'name': inst.get('name', 'Unknown'),
                'code': inst.get('code', ''),
                'is_active': inst.get('is_active', True),
                'total_users': len(inst_users),
                'total_students': sum(1 for u in inst_users if u.get('role') == 'student'),
                'total_lecturers': sum(1 for u in inst_users if u.get('role') == 'lecturer'),
                'total_admins': sum(1 for u in inst_users if u.get('role') == 'institutional_admin'),
                'total_attendance_records': total,
                'attendance_rate': round((present / total * 100) if total > 0 else 0, 1),
                'suspicious_records': len(suspicious),
                'created_at': inst.get('created_at', ''),
            })

        return result

    def get_all_users(self, role_filter: Optional[str] = None, institution_filter: Optional[str] = None, search: Optional[str] = None, limit: int = 200) -> List[Dict[str, Any]]:
        """Get all users across the system with optional filters."""
        users = user_repo.list_all() or []

        if role_filter:
            users = [u for u in users if u.get('role') == role_filter]
        if institution_filter:
            users = [u for u in users if u.get('institution_id') == institution_filter]
        if search:
            s = search.lower()
            users = [u for u in users if s in (u.get('email', '') + u.get('first_name', '') + u.get('last_name', '')).lower()]

        institutions_map = {}
        all_institutions = institution_repo.list_all() or []
        for inst in all_institutions:
            institutions_map[inst.get('id', '')] = inst.get('name', 'Unknown')

        result = []
        for u in users[:limit]:
            result.append({
                'id': u.get('id', ''),
                'email': u.get('email', ''),
                'first_name': u.get('first_name', ''),
                'last_name': u.get('last_name', ''),
                'full_name': f"{u.get('first_name', '')} {u.get('last_name', '')}".strip(),
                'role': u.get('role', ''),
                'institution_id': u.get('institution_id', ''),
                'institution_name': institutions_map.get(u.get('institution_id', ''), 'Unknown'),
                'is_active': u.get('is_active', True),
                'email_verified': u.get('email_verified', False),
                'last_login': u.get('last_login', ''),
                'created_at': u.get('created_at', ''),
                'phone': u.get('phone', ''),
            })

        return result

    def get_activity_feed(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent activity across all institutions from audit logs."""
        logs = audit_log_repo.list_all(limit=limit, order_by='timestamp') or []
        logs.sort(key=lambda x: x.get('timestamp', ''), reverse=True)

        institutions_map = {}
        all_institutions = institution_repo.list_all() or []
        for inst in all_institutions:
            institutions_map[inst.get('id', '')] = inst.get('name', 'Unknown')

        result = []
        for log in logs[:limit]:
            result.append({
                'id': log.get('id', ''),
                'action': log.get('action', ''),
                'resource_type': log.get('resource_type', ''),
                'resource_id': log.get('resource_id', ''),
                'user_id': log.get('user_id', ''),
                'institution_id': log.get('institution_id', ''),
                'institution_name': institutions_map.get(log.get('institution_id', ''), ''),
                'ip_address': log.get('ip_address', ''),
                'timestamp': log.get('timestamp', ''),
                'details': log.get('new_values', {}),
            })
        return result

    def get_security_events(self, limit: int = 100, min_risk: int = 0) -> List[Dict[str, Any]]:
        """Get security events across all institutions."""
        events = security_log_repo.list_all(limit=limit, order_by='created_at') or []
        events.sort(key=lambda x: x.get('created_at', ''), reverse=True)

        filtered = [e for e in events if (e.get('risk_score') or 0) >= min_risk]

        institutions_map = {}
        all_institutions = institution_repo.list_all() or []
        for inst in all_institutions:
            institutions_map[inst.get('id', '')] = inst.get('name', 'Unknown')

        result = []
        for e in filtered[:limit]:
            result.append({
                'id': e.get('id', ''),
                'event_type': e.get('event_type', ''),
                'description': e.get('description', ''),
                'user_id': e.get('user_id', ''),
                'institution_id': e.get('institution_id', ''),
                'institution_name': institutions_map.get(e.get('institution_id', ''), ''),
                'ip_address': e.get('ip_address', ''),
                'risk_score': e.get('risk_score', 0),
                'is_resolved': e.get('is_resolved', False),
                'created_at': e.get('created_at', ''),
            })
        return result

    def get_attendance_overview(self) -> Dict[str, Any]:
        """Get cross-institution attendance analytics."""
        all_sessions = attendance_session_repo.list_all() or []
        all_records = attendance_record_repo.list_all() or []
        all_users = user_repo.list_all() or []

        active_sessions = [s for s in all_sessions if s.get('is_active')]
        suspicious = [r for r in all_records if r.get('is_suspicious')]

        status_counts = defaultdict(int)
        for r in all_records:
            status_counts[r.get('status', 'unknown')] += 1

        records_by_session = defaultdict(list)
        for r in all_records:
            records_by_session[r.get('attendance_session_id', '')].append(r)

        avg_per_session = round(len(all_records) / len(records_by_session)) if records_by_session else 0

        student_ids = set(u.get('id') for u in all_users if u.get('role') == 'student')
        enrolled_students = len(student_ids)
        students_with_records = len(set(r.get('student_id') for r in all_records))

        total = len(all_records)
        present = status_counts.get('present', 0)
        absent = status_counts.get('absent', 0)
        late = status_counts.get('late', 0)
        excused = status_counts.get('excused', 0)

        return {
            'total_sessions': len(all_sessions),
            'active_sessions': len(active_sessions),
            'total_records': total,
            'present': present,
            'absent': absent,
            'late': late,
            'excused': excused,
            'attendance_rate': round((present / total * 100) if total > 0 else 0, 1),
            'suspicious_records': len(suspicious),
            'avg_records_per_session': avg_per_session,
            'enrolled_students': enrolled_students,
            'students_with_attendance': students_with_records,
        }

    def get_suspicious_activity(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get all suspicious attendance records across institutions."""
        all_records = attendance_record_repo.list_all() or []
        suspicious = [r for r in all_records if r.get('is_suspicious')]
        suspicious.sort(key=lambda x: x.get('created_at', ''), reverse=True)

        user_ids = set()
        for r in suspicious:
            uid = r.get('student_id')
            if uid: user_ids.add(uid)
        users = {}
        for uid in user_ids:
            u = user_repo.get_by_id(uid)
            if u:
                users[uid] = u

        institutions_map = {}
        all_institutions = institution_repo.list_all() or []
        for inst in all_institutions:
            institutions_map[inst.get('id', '')] = inst.get('name', 'Unknown')

        result = []
        for r in suspicious[:limit]:
            student = users.get(r.get('student_id', ''), {})
            result.append({
                'id': r.get('id', ''),
                'student_name': f"{student.get('first_name', '')} {student.get('last_name', '')}".strip(),
                'student_email': student.get('email', ''),
                'institution_name': institutions_map.get(r.get('institution_id', ''), ''),
                'status': r.get('status', ''),
                'suspicion_reason': r.get('suspicion_reason', 'Unknown'),
                'ip_address': r.get('ip_address', ''),
                'user_agent': r.get('user_agent', ''),
                'marked_at': r.get('marked_at', ''),
                'created_at': r.get('created_at', ''),
            })
        return result

    def get_audit_logs(self, limit: int = 100, action_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get system-wide audit logs."""
        logs = audit_log_repo.list_all(limit=limit, order_by='timestamp') or []
        logs.sort(key=lambda x: x.get('timestamp', ''), reverse=True)

        if action_filter:
            logs = [l for l in logs if l.get('action') == action_filter]

        institutions_map = {}
        all_institutions = institution_repo.list_all() or []
        for inst in all_institutions:
            institutions_map[inst.get('id', '')] = inst.get('name', 'Unknown')

        result = []
        for log in logs[:limit]:
            result.append({
                'id': log.get('id', ''),
                'action': log.get('action', ''),
                'resource_type': log.get('resource_type', ''),
                'resource_id': log.get('resource_id', ''),
                'user_id': log.get('user_id', ''),
                'institution_name': institutions_map.get(log.get('institution_id', ''), ''),
                'ip_address': log.get('ip_address', ''),
                'user_agent': log.get('user_agent', ''),
                'timestamp': log.get('timestamp', ''),
                'old_values': log.get('old_values', {}),
                'new_values': log.get('new_values', {}),
            })
        return result

    def toggle_user_status(self, user_id: str) -> bool:
        """Toggle a user's active/inactive status."""
        user = user_repo.get_by_id(user_id)
        if not user:
            return False
        current = user.get('is_active', True)
        return user_repo.update(user_id, {'is_active': not current, 'updated_at': datetime.utcnow().isoformat()})

    def toggle_institution_status(self, institution_id: str) -> bool:
        """Toggle an institution's active/inactive status."""
        inst = institution_repo.get_by_id(institution_id)
        if not inst:
            return False
        current = inst.get('is_active', True)
        return institution_repo.update(institution_id, {'is_active': not current, 'updated_at': datetime.utcnow().isoformat()})

    def _parse_date(self, date_str: str) -> Optional[datetime.date]:
        """Parse ISO date string to date object."""
        try:
            if isinstance(date_str, datetime):
                return date_str.date()
            return datetime.fromisoformat(date_str.replace('Z', '')).date()
        except (ValueError, AttributeError):
            return None


super_admin_service = SuperAdminService()
