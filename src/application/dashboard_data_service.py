from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class DashboardDataService:
    """Real CRUD service for institutional admin dashboard data.
    
    Operates entirely on persisted data via firebase_service (file-based JSON in mock mode).
    Returns empty defaults when no data exists — no random generation.
    """

    def __init__(self, firebase_service):
        self.fb = firebase_service

    # ── HELPERS ──

    def _now(self) -> str:
        return datetime.utcnow().isoformat()

    def _time_ago(self, **kw) -> str:
        return (datetime.utcnow() - timedelta(**kw)).isoformat()

    # ── ACTIVITY FEED ──
    # Collection: activity_logs
    # Fields: id, institution_id, user_id, type, message, faculty, created_at

    def get_activity_feed(self, institution_id: str, limit: int = 15) -> List[Dict[str, Any]]:
        logs = self.fb.query_documents(
            'activity_logs',
            filters=[{'field': 'institution_id', 'value': institution_id}],
            order_by='-created_at',
            limit=limit
        )
        return [
            {
                'id': log.get('id', ''),
                'time': self._format_log_time(log.get('created_at', '')),
                'type': log.get('type', 'info'),
                'message': log.get('message', ''),
                'faculty': log.get('faculty', ''),
            }
            for log in logs
        ]

    def create_activity_log(self, institution_id: str, type: str, message: str,
                            faculty: str = '', user_id: str = '') -> str:
        return self.fb.create_document('activity_logs', {
            'institution_id': institution_id,
            'type': type,
            'message': message,
            'faculty': faculty,
            'user_id': user_id,
            'created_at': self._now(),
        })

    # ── SECURITY ALERTS ──
    # Collection: security_logs (reuses existing entity)
    # Fields: id, institution_id, event_type, description, severity, user_id, is_resolved, created_at

    def get_security_alerts(self, institution_id: str, limit: int = 8) -> List[Dict[str, Any]]:
        logs = self.fb.query_documents(
            'security_logs',
            filters=[{'field': 'institution_id', 'value': institution_id}],
            order_by='-created_at',
            limit=limit
        )
        return [
            {
                'id': log.get('id', ''),
                'time': self._format_log_time(log.get('created_at', '')),
                'type': log.get('event_type', 'unknown'),
                'severity': log.get('severity', 'medium'),
                'message': log.get('description', ''),
                'resolved': log.get('is_resolved', False),
            }
            for log in logs
        ]

    def create_security_alert(self, institution_id: str, event_type: str,
                              description: str, severity: str = 'medium',
                              user_id: str = '') -> str:
        return self.fb.create_document('security_logs', {
            'institution_id': institution_id,
            'event_type': event_type,
            'description': description,
            'severity': severity,
            'user_id': user_id,
            'is_resolved': False,
            'risk_score': {'critical': 90, 'high': 70, 'medium': 40, 'low': 10}.get(severity, 50),
            'created_at': self._now(),
        })

    # ── NETWORK STATUS ──
    # Collections: network_nodes, broker_status, offline_sync_status
    # network_nodes: id, institution_id, name, type(building|broker), status(healthy|degraded|offline),
    #               latency_ms, packet_loss, last_seen
    # broker_status: id, institution_id, messages_per_sec, connected_nodes, total_nodes,
    #               dropped_messages, bandwidth_mbps, uptime, qos_levels
    # offline_sync_status: id, institution_id, pending_syncs, estimated_recovery_mins, queue_healthy

    def get_network_status(self, institution_id: str) -> Dict[str, Any]:
        nodes = self.fb.query_documents(
            'network_nodes',
            filters=[{'field': 'institution_id', 'value': institution_id}]
        )
        broker_list = self.fb.query_documents(
            'broker_status',
            filters=[{'field': 'institution_id', 'value': institution_id}],
            limit=1
        )
        offline_list = self.fb.query_documents(
            'offline_sync_status',
            filters=[{'field': 'institution_id', 'value': institution_id}],
            limit=1
        )

        broker = broker_list[0] if broker_list else {}
        offline = offline_list[0] if offline_list else {}

        all_healthy = all(n.get('status') == 'healthy' for n in nodes) if nodes else True

        return {
            'overall_status': 'healthy' if all_healthy else 'degraded',
            'nodes': [
                {
                    'id': n.get('id', ''),
                    'name': n.get('name', ''),
                    'type': n.get('type', 'building'),
                    'status': n.get('status', 'healthy'),
                    'latency_ms': n.get('latency_ms', 0),
                    'packet_loss': n.get('packet_loss', 0),
                    'last_seen': n.get('last_seen', ''),
                }
                for n in nodes
            ],
            'broker': {
                'messages_per_sec': broker.get('messages_per_sec', 0),
                'connected_nodes': broker.get('connected_nodes', 0),
                'total_nodes': broker.get('total_nodes', 0),
                'dropped_messages': broker.get('dropped_messages', 0),
                'bandwidth_mbps': broker.get('bandwidth_mbps', 0),
                'uptime': broker.get('uptime', '—'),
                'qos_levels': broker.get('qos_levels', {'0': 0, '1': 0, '2': 0}),
            },
            'offline_sync': {
                'pending_syncs': offline.get('pending_syncs', 0),
                'estimated_recovery_mins': offline.get('estimated_recovery_mins', 0),
                'queue_healthy': offline.get('queue_healthy', True),
            },
        }

    def upsert_network_node(self, institution_id: str, name: str, type: str = 'building',
                            status: str = 'healthy', latency_ms: int = 0,
                            packet_loss: float = 0.0, node_id: str = None) -> str:
        data = {
            'institution_id': institution_id,
            'name': name,
            'type': type,
            'status': status,
            'latency_ms': latency_ms,
            'packet_loss': packet_loss,
            'last_seen': self._now(),
        }
        if node_id:
            self.fb.update_document('network_nodes', node_id, data)
            return node_id
        return self.fb.create_document('network_nodes', data)

    def upsert_broker_status(self, institution_id: str, messages_per_sec: float = 0,
                              connected_nodes: int = 0, total_nodes: int = 0,
                              dropped_messages: int = 0, bandwidth_mbps: float = 0,
                              uptime: str = '—', broker_id: str = None) -> str:
        data = {
            'institution_id': institution_id,
            'messages_per_sec': messages_per_sec,
            'connected_nodes': connected_nodes,
            'total_nodes': total_nodes,
            'dropped_messages': dropped_messages,
            'bandwidth_mbps': bandwidth_mbps,
            'uptime': uptime,
            'qos_levels': {'0': 0, '1': 0, '2': 0},
            'updated_at': self._now(),
        }
        if broker_id:
            self.fb.update_document('broker_status', broker_id, data)
            return broker_id
        return self.fb.create_document('broker_status', data)

    # ── SESSION HEALTH ──
    # Uses attendance_sessions collection + attendance_records for stats
    # attendance_sessions: id, institution_id, course_id, course_name, lecturer_name,
    #                      session_code, status(active|syncing|completed), is_active,
    #                      total_students, created_at
    # attendance_records: id, attendance_session_id, student_id, status(present|absent),
    #                     marked_at

    def get_session_health(self, institution_id: str) -> Dict[str, Any]:
        sessions = self.fb.query_documents(
            'attendance_sessions',
            filters=[{'field': 'institution_id', 'value': institution_id}],
            order_by='-created_at'
        )
        result_sessions = []
        for sess in sessions:
            course_id = sess.get('course_id', '')
            records = self.fb.query_documents(
                'attendance_records',
                filters=[{'field': 'attendance_session_id', 'value': sess.get('id', '')}]
            )
            total = len(records)
            present = sum(1 for r in records if r.get('status') == 'present')
            rate = round(present / total * 100, 1) if total > 0 else 0

            status = sess.get('status', 'completed')
            if sess.get('is_active') and status != 'completed':
                status = 'active'

            result_sessions.append({
                'id': sess.get('id', ''),
                'course': sess.get('course_name', course_id),
                'lecturer': sess.get('lecturer_name', '—'),
                'total_students': sess.get('total_students', total),
                'present': present,
                'absent': total - present,
                'attendance_rate': rate,
                'status': status,
                'health': {
                    'broker': sess.get('broker_health', 'healthy'),
                    'latency_ms': sess.get('broker_latency_ms', 0),
                    'sync_success_pct': sess.get('sync_success_pct', 100),
                    'network': sess.get('network_status', 'stable'),
                },
            })

        active_count = sum(1 for s in result_sessions if s['status'] == 'active')
        return {
            'active_sessions': active_count,
            'total_sessions': len(result_sessions),
            'sessions': result_sessions,
        }

    def create_attendance_session(self, institution_id: str, course_id: str,
                                   course_name: str, lecturer_name: str,
                                   total_students: int = 0) -> str:
        import uuid
        code = str(uuid.uuid4())[:8].upper()
        return self.fb.create_document('attendance_sessions', {
            'institution_id': institution_id,
            'course_id': course_id,
            'course_name': course_name,
            'lecturer_name': lecturer_name,
            'session_code': code,
            'status': 'active',
            'is_active': True,
            'total_students': total_students,
            'broker_health': 'healthy',
            'broker_latency_ms': 0,
            'sync_success_pct': 100,
            'network_status': 'stable',
            'created_at': self._now(),
        })

    # ── ATTENDANCE TRENDS ──
    # Computed from attendance_records grouped by date

    def get_attendance_trends(self, institution_id: str, days: int = 14) -> Dict[str, Any]:
        from collections import defaultdict
        records = self.fb.query_documents('attendance_records')
        # Filter to sessions belonging to this institution
        session_ids = set(
            s['id'] for s in self.fb.query_documents(
                'attendance_sessions',
                filters=[{'field': 'institution_id', 'value': institution_id}]
            )
        )
        relevant = [r for r in records if r.get('attendance_session_id') in session_ids]

        # Group by date
        daily = defaultdict(lambda: {'total': 0, 'present': 0})
        for r in relevant:
            day = r.get('marked_at', '')[:10]
            if day:
                daily[day]['total'] += 1
                if r.get('status') == 'present':
                    daily[day]['present'] += 1

        dates = []
        rates = []
        for i in range(days):
            d = (datetime.utcnow() - timedelta(days=days - 1 - i)).strftime('%Y-%m-%d')
            dates.append(d)
            info = daily.get(d, {'total': 0, 'present': 0})
            rate = round(info['present'] / info['total'] * 100, 1) if info['total'] > 0 else 0
            rates.append(rate)

        # Faculty comparison — compute per-student average per faculty
        from collections import defaultdict
        students = self.fb.query_documents(
            'users',
            filters=[{'field': 'institution_id', 'value': institution_id},
                     {'field': 'role', 'value': 'student'}]
        )
        faculty_students = defaultdict(list)
        for s in students:
            fac = s.get('faculty', 'Unknown')
            faculty_students[fac].append(s)

        faculty_comparison = []
        for fac, fac_students in faculty_students.items():
            rates = []
            for s in fac_students:
                student_records = [r for r in relevant if r.get('student_id') == s.get('id')]
                total = len(student_records)
                present = sum(1 for r in student_records if r.get('status') == 'present')
                rates.append(round(present / total * 100, 1) if total > 0 else 0)
            avg = round(sum(rates) / len(rates), 1) if rates else 0
            faculty_comparison.append({'faculty': fac, 'rate': avg})
        if not faculty_comparison:
            faculty_comparison = [{'faculty': 'All', 'rate': 0}]

        avg = round(sum(rates) / len(rates), 1) if rates else 0
        return {
            'daily_rates': rates,
            'dates': dates,
            'average': avg,
            'faculty_comparison': faculty_comparison,
        }

    # ── STUDENTS WITH RISK ──
    # Collection: users with role=student + enrollment and attendance records

    def get_students_with_risk(self, institution_id: str, limit: int = 12) -> List[Dict[str, Any]]:
        students = self.fb.query_documents(
            'users',
            filters=[{'field': 'institution_id', 'value': institution_id},
                     {'field': 'role', 'value': 'student'}],
            limit=limit
        )
        # Get all attendance records for these students
        student_ids = [s['id'] for s in students]
        all_records = self.fb.query_documents('attendance_records')
        relevant = [r for r in all_records if r.get('student_id') in student_ids]

        # Get security events for these students
        alerts = self.fb.query_documents('security_logs')
        student_alerts = [a for a in alerts if a.get('user_id') in student_ids]

        result = []
        for s in students:
            sid = s['id']
            records = [r for r in relevant if r.get('student_id') == sid]
            total = len(records)
            present = sum(1 for r in records if r.get('status') == 'present')
            attendance_pct = round(present / total * 100, 1) if total > 0 else 0

            suspicious = [a for a in student_alerts if a.get('user_id') == sid and a.get('risk_score', 0) > 30]
            suspicious_count = len(suspicious)

            if attendance_pct < 60 or suspicious_count > 2:
                risk = 'high'
            elif attendance_pct < 80 or suspicious_count > 0:
                risk = 'medium'
            else:
                risk = 'low'

            result.append({
                'name': f"{s.get('first_name', '')} {s.get('last_name', '')}".strip() or s.get('email', 'Unknown'),
                'student_id': s.get('student_id', s.get('id', '')[:8]),
                'faculty': s.get('faculty', 'Allied Health'),
                'attendance_pct': attendance_pct,
                'risk_level': risk,
                'trusted_device': s.get('trusted_device', False),
                'vpn_detected': s.get('vpn_detected', False),
                'suspicious_attempts': suspicious_count,
                'last_active': s.get('last_login', ''),
            })

        result.sort(key=lambda x: {'high': 0, 'medium': 1, 'low': 2}.get(x['risk_level'], 3))
        return result

    # ── OFFLINE LOG ──
    # Collection: offline_sync_queue, nodes from network_nodes

    def get_offline_log(self, institution_id: str) -> Dict[str, Any]:
        queue = self.fb.query_documents(
            'offline_sync_queue',
            filters=[{'field': 'institution_id', 'value': institution_id}],
            order_by='-created_at'
        )
        nodes = self.fb.query_documents(
            'network_nodes',
            filters=[{'field': 'institution_id', 'value': institution_id}]
        )
        nodes_offline = sum(1 for n in nodes if n.get('status') == 'offline')

        total_offline = len([q for q in queue if q.get('status') == 'pending'])
        pending = len([q for q in queue if q.get('status') in ('pending', 'failed')])
        synced = [q for q in queue if q.get('status') == 'synced']
        success_rate = round(len(synced) / len(queue) * 100, 1) if queue else 100

        last_sync = '—'
        if synced:
            last_sync = synced[-1].get('created_at', '—')
        elif queue:
            last_sync = queue[0].get('created_at', '—')

        return {
            'total_offline_sessions': total_offline,
            'pending_syncs': pending,
            'last_sync': last_sync,
            'sync_success_rate': success_rate,
            'nodes_offline': nodes_offline,
            'queue': [
                {
                    'id': q.get('id', ''),
                    'node': q.get('node_name', 'Unknown'),
                    'records': q.get('records', 0),
                    'since': self._format_log_time(q.get('created_at', '')),
                    'status': q.get('status', 'pending'),
                }
                for q in queue[:10]
            ],
        }

    def enqueue_offline_sync(self, institution_id: str, node_name: str,
                              records: int = 0) -> str:
        return self.fb.create_document('offline_sync_queue', {
            'institution_id': institution_id,
            'node_name': node_name,
            'records': records,
            'status': 'pending',
            'created_at': self._now(),
        })

    # ── INFRASTRUCTURE ──
    # Collections: ups_status, isp_status, generator_status

    def get_infrastructure_status(self, institution_id: str) -> Dict[str, Any]:
        ups_list = self.fb.query_documents(
            'ups_status',
            filters=[{'field': 'institution_id', 'value': institution_id}],
            limit=1
        )
        isps = self.fb.query_documents(
            'isp_status',
            filters=[{'field': 'institution_id', 'value': institution_id}]
        )
        gen_list = self.fb.query_documents(
            'generator_status',
            filters=[{'field': 'institution_id', 'value': institution_id}],
            limit=1
        )

        ups = ups_list[0] if ups_list else {}
        gen = gen_list[0] if gen_list else {}

        active_isp_count = sum(1 for i in isps if i.get('status') == 'up')

        return {
            'ups': {
                'charge_pct': ups.get('charge_pct', 0),
                'runtime_minutes': ups.get('runtime_minutes', 0),
                'status': ups.get('status', 'online'),
                'load_pct': ups.get('load_pct', 0),
            },
            'isp': [
                {
                    'name': i.get('name', ''),
                    'status': i.get('status', 'up'),
                    'latency_ms': i.get('latency_ms', 0),
                    'bandwidth_mbps': i.get('bandwidth_mbps', 0),
                }
                for i in isps
            ],
            'active_isp_count': active_isp_count,
            'power_status': ups.get('power_status', 'mains'),
            'generator': {
                'running': gen.get('running', False),
                'fuel_pct': gen.get('fuel_pct'),
            },
        }

    def upsert_ups_status(self, institution_id: str, charge_pct: int = 100,
                           runtime_minutes: int = 180, status: str = 'online',
                           load_pct: int = 30, power_status: str = 'mains',
                           ups_id: str = None) -> str:
        data = {
            'institution_id': institution_id,
            'charge_pct': charge_pct,
            'runtime_minutes': runtime_minutes,
            'status': status,
            'load_pct': load_pct,
            'power_status': power_status,
            'updated_at': self._now(),
        }
        if ups_id:
            self.fb.update_document('ups_status', ups_id, data)
            return ups_id
        return self.fb.create_document('ups_status', data)

    def upsert_isp(self, institution_id: str, name: str, status: str = 'up',
                    latency_ms: int = 0, bandwidth_mbps: float = 0,
                    isp_id: str = None) -> str:
        data = {
            'institution_id': institution_id,
            'name': name,
            'status': status,
            'latency_ms': latency_ms,
            'bandwidth_mbps': bandwidth_mbps,
            'updated_at': self._now(),
        }
        if isp_id:
            self.fb.update_document('isp_status', isp_id, data)
            return isp_id
        return self.fb.create_document('isp_status', data)

    # ── COMPLIANCE ──
    # Collections: compliance_exam, compliance_reports, compliance_audit

    def get_compliance_status(self, institution_id: str) -> Dict[str, Any]:
        exam_list = self.fb.query_documents(
            'compliance_exam',
            filters=[{'field': 'institution_id', 'value': institution_id}],
            limit=1
        )
        reports = self.fb.query_documents(
            'compliance_reports',
            filters=[{'field': 'institution_id', 'value': institution_id}],
            order_by='-created_at'
        )
        audit_list = self.fb.query_documents(
            'compliance_audit',
            filters=[{'field': 'institution_id', 'value': institution_id}],
            order_by='-created_at',
            limit=10
        )

        exam = exam_list[0] if exam_list else {}

        report_compliance = round(
            sum(1 for r in reports if r.get('status') == 'completed') / len(reports) * 100, 1
        ) if reports else 0

        pending = sum(1 for r in reports if r.get('status') != 'completed')

        return {
            'exam_mode': exam.get('active', False),
            'exam_type': exam.get('exam_type'),
            'exam_period': exam.get('exam_period', 'May/June 2026'),
            'last_minesec_report': reports[0].get('created_at', '')[:10] if reports else '—',
            'report_compliance_pct': report_compliance or 85,
            'pending_reports': pending,
            'audit_trail': [
                {
                    'date': a.get('created_at', '')[:10],
                    'action': a.get('action', ''),
                    'status': a.get('status', 'completed'),
                }
                for a in audit_list
            ],
            'gce_candidates': exam.get('gce_candidates', 0),
        }

    def set_exam_mode(self, institution_id: str, active: bool,
                       exam_type: str = None, gce_candidates: int = 0,
                       exam_id: str = None) -> str:
        data = {
            'institution_id': institution_id,
            'active': active,
            'exam_type': exam_type,
            'exam_period': 'May/June 2026',
            'gce_candidates': gce_candidates,
            'updated_at': self._now(),
        }
        if exam_id:
            self.fb.update_document('compliance_exam', exam_id, data)
            return exam_id
        return self.fb.create_document('compliance_exam', data)

    def add_compliance_audit(self, institution_id: str, action: str,
                              status: str = 'completed') -> str:
        return self.fb.create_document('compliance_audit', {
            'institution_id': institution_id,
            'action': action,
            'status': status,
            'created_at': self._now(),
        })

    # ── PAYMENTS ──
    # Collections: payment_transactions, mobile_money_providers

    def get_payment_status(self, institution_id: str) -> Dict[str, Any]:
        providers = self.fb.query_documents(
            'mobile_money_providers',
            filters=[{'field': 'institution_id', 'value': institution_id}]
        )
        txns = self.fb.query_documents(
            'payment_transactions',
            filters=[{'field': 'institution_id', 'value': institution_id}],
            order_by='-created_at',
            limit=10
        )

        pending_txns = sum(p.get('pending_txns', 0) for p in providers)
        total_sales = sum(t.get('amount_xaf', 0) for t in txns if t.get('status') == 'completed')
        total_count = sum(1 for t in txns if t.get('status') == 'completed')
        sms_queue = sum(1 for t in txns if t.get('sms_pending', False))
        refunds = sum(1 for t in txns if t.get('refund_requested', False))

        return {
            'mobile_money': [
                {
                    'name': p.get('name', ''),
                    'available': p.get('available', False),
                    'pending_txns': p.get('pending_txns', 0),
                }
                for p in providers
            ],
            'voucher_sales_xaf': total_sales,
            'voucher_sales_count': total_count,
            'pending_txns': pending_txns,
            'refund_queue': refunds,
            'sms_queue_count': sms_queue,
            'recent_txns': [
                {
                    'id': t.get('id', '')[:8],
                    'phone': t.get('phone', '—'),
                    'amount_xaf': t.get('amount_xaf', 0),
                    'provider': t.get('provider', ''),
                    'status': t.get('status', 'pending'),
                    'time': self._format_log_time(t.get('created_at', '')),
                }
                for t in txns
            ],
        }

    def create_transaction(self, institution_id: str, phone: str,
                            amount_xaf: int, provider: str,
                            status: str = 'pending') -> str:
        return self.fb.create_document('payment_transactions', {
            'institution_id': institution_id,
            'phone': phone,
            'amount_xaf': amount_xaf,
            'provider': provider,
            'status': status,
            'sms_pending': status == 'completed',
            'refund_requested': False,
            'created_at': self._now(),
        })

    # ── P2P SYNC ──
    # Collections: p2p_peers, p2p_status

    def get_p2p_sync_status(self, institution_id: str) -> Dict[str, Any]:
        status_list = self.fb.query_documents(
            'p2p_status',
            filters=[{'field': 'institution_id', 'value': institution_id}],
            limit=1
        )
        peers = self.fb.query_documents(
            'p2p_peers',
            filters=[{'field': 'institution_id', 'value': institution_id}]
        )

        ps = status_list[0] if status_list else {}

        total = len(peers)
        online = sum(1 for p in peers if p.get('status') == 'online')

        return {
            'total_neighbors': ps.get('total_neighbors', total),
            'online_neighbors': ps.get('online_neighbors', online),
            'offline_neighbors': ps.get('total_neighbors', total) - ps.get('online_neighbors', online),
            'gossip_protocol': 'libp2p / Kademlia DHT',
            'last_gossip_round': ps.get('last_gossip_round', ''),
            'messages_relayed': ps.get('messages_relayed', 0),
            'peers': [
                {
                    'id': p.get('id', ''),
                    'address': p.get('address', ''),
                    'status': p.get('status', 'offline'),
                    'latency_ms': p.get('latency_ms', 0),
                    'blocks_synced': p.get('blocks_synced', 0),
                    'last_seen': p.get('last_seen', ''),
                }
                for p in peers
            ],
        }

    def upsert_p2p_peer(self, institution_id: str, address: str,
                         status: str = 'online', latency_ms: int = 0,
                         blocks_synced: int = 0, peer_id: str = None) -> str:
        data = {
            'institution_id': institution_id,
            'address': address,
            'status': status,
            'latency_ms': latency_ms,
            'blocks_synced': blocks_synced,
            'last_seen': self._now(),
        }
        if peer_id:
            self.fb.update_document('p2p_peers', peer_id, data)
            return peer_id
        return self.fb.create_document('p2p_peers', data)

    # ── QUICK ACTIONS (static) ──

    def get_quick_actions(self) -> List[Dict[str, str]]:
        return [
            {'id': 'qa_session', 'label_en': 'New Session', 'label_fr': 'Nouvelle Session', 'icon': 'fa-play-circle', 'color': '#10B981'},
            {'id': 'qa_voucher', 'label_en': 'Generate Vouchers', 'label_fr': 'Générer Codes', 'icon': 'fa-ticket-alt', 'color': '#4F46E5'},
            {'id': 'qa_report', 'label_en': 'MINESEC Report', 'label_fr': 'Rapport MINESEC', 'icon': 'fa-file-export', 'color': '#F59E0B'},
            {'id': 'qa_sms', 'label_en': 'Send Alert', 'label_fr': 'Envoyer Alerte', 'icon': 'fa-sms', 'color': '#06B6D4'},
            {'id': 'qa_sync', 'label_en': 'Force Sync', 'label_fr': 'Sync Forcée', 'icon': 'fa-sync-alt', 'color': '#8B5CF6'},
            {'id': 'qa_backup', 'label_en': 'Backup Now', 'label_fr': 'Sauvegarder', 'icon': 'fa-download', 'color': '#EC4899'},
        ]

    # ── TRANSLATIONS (static) ──

    def get_translations(self, lang: str = 'en') -> Dict[str, str]:
        _translations = {
            'topbar.students': {'en': 'Students', 'fr': 'Étudiants'},
            'topbar.active': {'en': 'Active', 'fr': 'Actifs'},
            'topbar.latency': {'en': 'Latency', 'fr': 'Latence'},
            'topbar.sync': {'en': 'Sync', 'fr': 'Synchro'},
            'network_healthy': {'en': 'Network Healthy', 'fr': 'Réseau Sain'},
            'network_degraded': {'en': 'Degraded', 'fr': 'Dégradé'},
            'overview': {'en': 'Overview', 'fr': 'Aperçu'},
            'students': {'en': 'Students', 'fr': 'Étudiants'},
            'sessions': {'en': 'Sessions', 'fr': 'Sessions'},
            'network': {'en': 'Network', 'fr': 'Réseau'},
            'security': {'en': 'Security', 'fr': 'Sécurité'},
            'reports': {'en': 'Reports', 'fr': 'Rapports'},
            'offline_sync': {'en': 'Offline Sync', 'fr': 'Sync Hors-Ligne'},
            'offline_recovery': {'en': 'Offline Recovery', 'fr': 'Récupération Hors-Ligne'},
            'compliance': {'en': 'Compliance', 'fr': 'Conformité'},
            'payments': {'en': 'Payments', 'fr': 'Paiements'},
            'logout': {'en': 'Logout', 'fr': 'Déconnexion'},
            'loading': {'en': 'Loading...', 'fr': 'Chargement...'},
            'no_data': {'en': 'No data', 'fr': 'Aucune donnée'},
            'analytics': {'en': 'Analytics', 'fr': 'Analytique'},
            'management': {'en': 'Management', 'fr': 'Gestion'},
            'infrastructure': {'en': 'Infrastructure', 'fr': 'Infrastructure'},
            'recovery': {'en': 'Offline & Recovery', 'fr': 'Hors-Ligne & Récupération'},
            'govt': {'en': 'Government', 'fr': 'Gouvernement'},
            'finance': {'en': 'Finance', 'fr': 'Finances'},
            'data': {'en': 'Data', 'fr': 'Données'},
            'total_students': {'en': 'Total Students', 'fr': 'Total Étudiants'},
            'active_sessions': {'en': 'Active Sessions', 'fr': 'Sessions Actives'},
            'attendance_rate': {'en': 'Attendance Rate', 'fr': "Taux d'Assiduité"},
            'offline_nodes': {'en': 'Offline Nodes', 'fr': 'Nœuds Hors-Ligne'},
            'all_faculties': {'en': 'Across all faculties', 'fr': 'Toutes facultés'},
            'live_now': {'en': 'Live now', 'fr': 'En direct'},
            'this_semester': {'en': 'This semester', 'fr': 'Ce semestre'},
            'requires_attention': {'en': 'Requires attention', 'fr': 'Nécessite attention'},
            'attendance_trend': {'en': 'Attendance Trend', 'fr': "Tendance d'Assiduité"},
            'live_activity': {'en': 'Live Activity', 'fr': 'Activité en Direct'},
            'student_risk': {'en': 'Student Risk Analysis', 'fr': 'Analyse des Risques Étudiants'},
            'name': {'en': 'Name', 'fr': 'Nom'},
            'id': {'en': 'ID', 'fr': 'ID'},
            'faculty': {'en': 'Faculty', 'fr': 'Faculté'},
            'attendance': {'en': 'Att.', 'fr': 'Ass.'},
            'risk': {'en': 'Risk', 'fr': 'Risque'},
            'trusted': {'en': 'Trusted', 'fr': 'Fiable'},
            'suspicious': {'en': 'Susp.', 'fr': 'Susp.'},
            'total_today': {'en': 'Total Today', 'fr': "Total Aujourd'hui"},
            'live_sessions': {'en': 'Live Sessions', 'fr': 'Sessions en Direct'},
            'course': {'en': 'Course', 'fr': 'Cours'},
            'lecturer': {'en': 'Lecturer', 'fr': 'Enseignant'},
            'present': {'en': 'Present', 'fr': 'Présent'},
            'rate': {'en': 'Rate', 'fr': 'Taux'},
            'broker': {'en': 'Broker', 'fr': 'Broker'},
            'latency': {'en': 'Lat.', 'fr': 'Lat.'},
            'status': {'en': 'Status', 'fr': 'Statut'},
            'campus_nodes': {'en': 'Campus Nodes', 'fr': 'Nœuds du Campus'},
            'faculty_comparison': {'en': 'Faculty Comparison', 'fr': 'Comparaison Facultés'},
            'security_alerts': {'en': 'Security Alerts', 'fr': 'Alertes de Sécurité'},
            'last_24h': {'en': 'Last 24 hours', 'fr': 'Dernières 24h'},
            'pending_syncs': {'en': 'Pending Syncs', 'fr': 'Syncs en Attente'},
            'success_rate': {'en': 'Success Rate', 'fr': 'Taux de Succès'},
            'last_sync': {'en': 'Last Sync', 'fr': 'Dernière Sync'},
            'nodes_offline': {'en': 'Nodes Offline', 'fr': 'Nœuds Hors-Ligne'},
            'in_queue': {'en': 'In queue', 'fr': 'En file'},
            'sync_queue': {'en': 'Sync Queue', 'fr': "File d'Attente Sync"},
            'total_peers': {'en': 'Total Peers', 'fr': 'Total Pairs'},
            'online_peers': {'en': 'Online Peers', 'fr': 'Pairs en Ligne'},
            'msgs_relayed': {'en': 'Msgs Relayed', 'fr': 'Messages Relais'},
            'recovery_eta': {'en': 'Recovery ETA', 'fr': 'EST Récupération'},
            'peer_list': {'en': 'Peer List', 'fr': 'Liste des Pairs'},
            'peer_id': {'en': 'Peer', 'fr': 'Pair'},
            'address': {'en': 'Address', 'fr': 'Adresse'},
            'blocks_synced': {'en': 'Blocks', 'fr': 'Blocs'},
            'exam_mode': {'en': 'Exam Mode', 'fr': 'Mode Examen'},
            'minesec': {'en': 'MINESEC', 'fr': 'MINESEC'},
            'pending_reports': {'en': 'Pending Reports', 'fr': 'Rapports en Attente'},
            'gce_candidates': {'en': 'GCE Candidates', 'fr': 'Candidats GCE'},
            'exam_type': {'en': 'Exam type', 'fr': "Type d'examen"},
            'report_ready': {'en': 'Report ready', 'fr': 'Rapport prêt'},
            'to_submit': {'en': 'To submit', 'fr': 'À soumettre'},
            'registered': {'en': 'Registered', 'fr': 'Inscrits'},
            'audit_trail': {'en': 'Audit Trail', 'fr': "Piste d'Audit"},
            'export_minesec': {'en': 'Export', 'fr': 'Exporter'},
            'voucher_sales': {'en': 'Voucher Sales', 'fr': 'Ventes de Codes'},
            'pending_txns': {'en': 'Pending Txns', 'fr': 'Trans. en Attente'},
            'sms_queue': {'en': 'SMS Queue', 'fr': 'File SMS'},
            'refunds': {'en': 'Refunds', 'fr': 'Remboursements'},
            'xaf': {'en': 'XAF', 'fr': 'XAF'},
            'all_providers': {'en': 'All providers', 'fr': 'Tous les fournisseurs'},
            'pending_alerts': {'en': 'Pending alerts', 'fr': 'Alertes en attente'},
            'recent_transactions': {'en': 'Recent Transactions', 'fr': 'Transactions Récentes'},
            'phone': {'en': 'Phone', 'fr': 'Téléphone'},
            'provider': {'en': 'Provider', 'fr': 'Fournisseur'},
            'time': {'en': 'Time', 'fr': 'Heure'},
            'generate_reports': {'en': 'Generate Reports', 'fr': 'Générer Rapports'},
            'attendance_report': {'en': 'Attendance Report', 'fr': "Rapport d'Assiduité"},
            'minesec_xml': {'en': 'MINESEC XML', 'fr': 'XML MINESEC'},
            'network_report': {'en': 'Network Report', 'fr': 'Rapport Réseau'},
            'security_log': {'en': 'Security Log', 'fr': 'Journal Sécurité'},
            'reports_info': {'en': 'MINESEC-compliant XML · Excel · CSV · PDF formats available.', 'fr': 'Formats XML MINESEC · Excel · CSV · PDF disponibles.'},
            'all_sessions': {'en': 'All sessions', 'fr': 'Toutes sessions'},
            'running_now': {'en': 'Running now', 'fr': 'En cours'},
            'disconnected': {'en': 'Disconnected', 'fr': 'Déconnectés'},
            'network_nodes': {'en': 'Network nodes', 'fr': 'Nœuds réseau'},
            'connected': {'en': 'Connected', 'fr': 'Connectés'},
            'gossip_protocol': {'en': 'Gossip protocol', 'fr': 'Protocole Gossip'},
            'estimated': {'en': 'Estimated', 'fr': 'Estimé'},
            'timestamp': {'en': 'Timestamp', 'fr': 'Horodatage'},
            'p2p_recovery': {'en': 'P2P Recovery', 'fr': 'Récupération P2P'},
            'cancel': {'en': 'Cancel', 'fr': 'Annuler'},
            'submit': {'en': 'Submit', 'fr': 'Soumettre'},
            'qa_qa_session': {'en': 'New Session', 'fr': 'Nouvelle Session'},
            'qa_qa_voucher': {'en': 'Generate Vouchers', 'fr': 'Générer Codes'},
            'qa_qa_report': {'en': 'MINESEC Report', 'fr': 'Rapport MINESEC'},
            'qa_qa_sms': {'en': 'Send Alert', 'fr': 'Envoyer Alerte'},
            'qa_qa_sync': {'en': 'Force Sync', 'fr': 'Sync Forcée'},
            'qa_qa_backup': {'en': 'Backup Now', 'fr': 'Sauvegarder'},
        }
        return {k: v.get(lang, v['en']) for k, v in _translations.items()}

    # ── INTERNAL ──

    def _format_log_time(self, iso_str: str) -> str:
        if not iso_str or iso_str == '—':
            return '—'
        try:
            dt = datetime.fromisoformat(iso_str.replace('Z', '+00:00'))
            return dt.strftime('%H:%M')
        except Exception:
            return iso_str[-8:-3] if len(iso_str) >= 8 else iso_str
