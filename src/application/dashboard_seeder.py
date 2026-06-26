from datetime import datetime, timedelta
import uuid
import random
import logging

logger = logging.getLogger(__name__)


def seed_comprehensive_demo_data(firebase_service, institution_id='inst_001'):
    """Seed comprehensive demo data for the institutional dashboard.
    
    Creates realistic sample data in the persisted database so the dashboard
    has something to display. Safe to call multiple times (skips if data exists).
    """
    result = {'collections_created': {}, 'errors': []}

    # Check if seed already exists
    existing = firebase_service.query_documents(
        'network_nodes',
        filters=[{'field': 'institution_id', 'value': institution_id}],
        limit=1
    )
    if existing:
        return {'message': 'Demo data already seeded', 'skipped': True}

    now = datetime.utcnow()

    # ── NETWORK NODES ──
    nodes_data = [
        {'name': 'Science Block', 'type': 'building', 'status': 'healthy', 'latency_ms': 8, 'packet_loss': 0.2},
        {'name': 'Engineering Block', 'type': 'building', 'status': 'healthy', 'latency_ms': 12, 'packet_loss': 0.5},
        {'name': 'HTTTC Annex', 'type': 'building', 'status': 'degraded', 'latency_ms': 45, 'packet_loss': 3.1},
        {'name': 'Central Library', 'type': 'building', 'status': 'healthy', 'latency_ms': 6, 'packet_loss': 0.1},
        {'name': 'Admin Block', 'type': 'building', 'status': 'healthy', 'latency_ms': 10, 'packet_loss': 0.3},
        {'name': 'Core Broker', 'type': 'broker', 'status': 'healthy', 'latency_ms': 3, 'packet_loss': 0.0},
    ]
    node_ids = []
    for n in nodes_data:
        nid = firebase_service.create_document('network_nodes', {
            'institution_id': institution_id,
            'name': n['name'],
            'type': n['type'],
            'status': n['status'],
            'latency_ms': n['latency_ms'],
            'packet_loss': n['packet_loss'],
            'last_seen': now.isoformat(),
        })
        node_ids.append(nid)
    result['collections_created']['network_nodes'] = len(nodes_data)

    # ── BROKER STATUS ──
    firebase_service.create_document('broker_status', {
        'institution_id': institution_id,
        'messages_per_sec': 287.3,
        'connected_nodes': 5,
        'total_nodes': 6,
        'dropped_messages': 2,
        'bandwidth_mbps': 156.8,
        'uptime': '72h 34m',
        'qos_levels': {'0': 1500, '1': 800, '2': 320},
    })
    result['collections_created']['broker_status'] = 1

    # ── ISP PROVIDERS ──
    isps = [
        {'name': 'MTN', 'status': 'up', 'latency_ms': 32, 'bandwidth_mbps': 85.5},
        {'name': 'Orange', 'status': 'up', 'latency_ms': 45, 'bandwidth_mbps': 62.3},
        {'name': 'Camtel', 'status': 'degraded', 'latency_ms': 120, 'bandwidth_mbps': 18.7},
    ]
    for isp in isps:
        firebase_service.create_document('isp_status', {
            'institution_id': institution_id,
            **isp,
        })
    result['collections_created']['isp_status'] = len(isps)

    # ── UPS ──
    firebase_service.create_document('ups_status', {
        'institution_id': institution_id,
        'charge_pct': 87,
        'runtime_minutes': 145,
        'status': 'online',
        'load_pct': 34,
        'power_status': 'mains',
    })
    result['collections_created']['ups_status'] = 1

    # ── GENERATOR ──
    firebase_service.create_document('generator_status', {
        'institution_id': institution_id,
        'running': False,
        'fuel_pct': 92,
    })
    result['collections_created']['generator_status'] = 1

    # ── COMPLIANCE EXAM ──
    firebase_service.create_document('compliance_exam', {
        'institution_id': institution_id,
        'active': True,
        'exam_type': 'GCE',
        'exam_period': 'May/June 2026',
        'gce_candidates': 845,
    })
    result['collections_created']['compliance_exam'] = 1

    # ── COMPLIANCE AUDIT ──
    audit_entries = [
        ('attendance_exported', 'completed'),
        ('report_generated', 'completed'),
        ('exam_session_logged', 'completed'),
        ('sync_verified', 'completed'),
        ('backup_created', 'completed'),
    ]
    for action, status in audit_entries:
        firebase_service.create_document('compliance_audit', {
            'institution_id': institution_id,
            'action': action,
            'status': status,
            'created_at': (now - timedelta(hours=random.randint(1, 168))).isoformat(),
        })
    result['collections_created']['compliance_audit'] = len(audit_entries)

    # ── MOBILE MONEY PROVIDERS ──
    for provider in ['MTN MoMo', 'Orange Money']:
        firebase_service.create_document('mobile_money_providers', {
            'institution_id': institution_id,
            'name': provider,
            'available': True,
            'pending_txns': random.randint(0, 12),
        })
    result['collections_created']['mobile_money_providers'] = 2

    # ── PAYMENT TRANSACTIONS ──
    phones = ['670123456', '699876543', '677234567', '690345678', '671456789']
    providers = ['MTN', 'Orange']
    statuses = ['completed', 'completed', 'completed', 'pending', 'failed']
    amounts = [5000, 10000, 2500, 15000, 8000, 2000, 12000]
    for i in range(8):
        firebase_service.create_document('payment_transactions', {
            'institution_id': institution_id,
            'phone': random.choice(phones),
            'amount_xaf': random.choice(amounts),
            'provider': random.choice(providers),
            'status': random.choice(statuses),
            'sms_pending': False,
            'refund_requested': False,
            'created_at': (now - timedelta(hours=i * 3)).isoformat(),
        })
    result['collections_created']['payment_transactions'] = 8

    # ── P2P PEERS ──
    peers = [
        {'address': '192.168.1.10', 'status': 'online', 'latency_ms': 4, 'blocks_synced': 4200},
        {'address': '192.168.1.25', 'status': 'online', 'latency_ms': 7, 'blocks_synced': 3800},
        {'address': '192.168.2.5', 'status': 'online', 'latency_ms': 12, 'blocks_synced': 4100},
        {'address': '192.168.2.18', 'status': 'online', 'latency_ms': 9, 'blocks_synced': 3950},
        {'address': '192.168.3.3', 'status': 'offline', 'latency_ms': 0, 'blocks_synced': 2800},
        {'address': '192.168.4.12', 'status': 'online', 'latency_ms': 15, 'blocks_synced': 3500},
    ]
    peer_ids = []
    for p in peers:
        pid = firebase_service.create_document('p2p_peers', {
            'institution_id': institution_id,
            'address': p['address'],
            'status': p['status'],
            'latency_ms': p['latency_ms'],
            'blocks_synced': p['blocks_synced'],
            'last_seen': (now - timedelta(seconds=random.randint(0, 120))).isoformat(),
        })
        peer_ids.append(pid)
    result['collections_created']['p2p_peers'] = len(peers)

    # ── P2P STATUS ──
    firebase_service.create_document('p2p_status', {
        'institution_id': institution_id,
        'total_neighbors': len(peers),
        'online_neighbors': sum(1 for p in peers if p['status'] == 'online'),
        'messages_relayed': 3847,
        'last_gossip_round': now.isoformat(),
    })
    result['collections_created']['p2p_status'] = 1

    # ── OFFLINE SYNC QUEUE ──
    queue_items = [
        {'node_name': 'HTTTC Annex', 'records': 156, 'status': 'pending'},
        {'node_name': 'Science Block', 'records': 42, 'status': 'syncing'},
        {'node_name': 'Admin Block', 'records': 89, 'status': 'pending'},
        {'node_name': 'Engineering Block', 'records': 0, 'status': 'synced'},
    ]
    for q in queue_items:
        firebase_service.create_document('offline_sync_queue', {
            'institution_id': institution_id,
            'node_name': q['node_name'],
            'records': q['records'],
            'status': q['status'],
            'created_at': (now - timedelta(hours=random.randint(1, 8))).isoformat(),
        })
    result['collections_created']['offline_sync_queue'] = len(queue_items)

    # ── ACTIVITY LOGS ──
    activities = [
        ('session_started', 'CSC301 attendance session started', 'Faculty of Science'),
        ('node_synced', 'Central Library node synchronized', 'Library'),
        ('broker_latency', 'MQTT Broker latency increased to 45ms', 'Infrastructure'),
        ('sync_completed', 'Offline sync completed - 156 records synced', 'Infrastructure'),
        ('alert_generated', 'Security alert generated for proxy attempt', 'Security'),
        ('student_enrolled', 'New student enrolled in CSC401', 'Faculty of Science'),
        ('session_ended', 'CSE204 attendance session ended', 'Faculty of Engineering'),
    ]
    for act_type, msg, fac in activities:
        firebase_service.create_document('activity_logs', {
            'institution_id': institution_id,
            'type': act_type,
            'message': msg,
            'faculty': fac,
            'user_id': 'system',
            'created_at': (now - timedelta(minutes=random.randint(5, 180))).isoformat(),
        })
    result['collections_created']['activity_logs'] = len(activities)

    # ── SECURITY LOGS ──
    security_events = [
        ('duplicate_qr', 'Duplicate QR scan detected', 'high'),
        ('proxy_attempt', 'Proxy attendance attempt blocked', 'critical'),
        ('vpn_detected', 'VPN usage detected during session', 'medium'),
        ('geo_anomaly', 'Impossible geolocation detected', 'critical'),
        ('rapid_replay', 'Rapid QR replay attempt blocked', 'high'),
    ]
    for ev_type, desc, sev in security_events:
        firebase_service.create_document('security_logs', {
            'institution_id': institution_id,
            'event_type': ev_type,
            'description': desc,
            'severity': sev,
            'user_id': '',
            'is_resolved': False,
            'risk_score': {'critical': 90, 'high': 70, 'medium': 40}.get(sev, 50),
            'created_at': (now - timedelta(hours=random.randint(1, 48))).isoformat(),
        })
    result['collections_created']['security_logs'] = len(security_events)

    # ── DEPARTMENTS ──
    dept_data = [
        {'code': 'CSC', 'name': 'Computer Science', 'head': 'Dr. Ewane'},
        {'code': 'CSE', 'name': 'Computer Engineering', 'head': 'Prof. Asongu'},
        {'code': 'MAT', 'name': 'Mathematics', 'head': 'Dr. Mbah'},
        {'code': 'PHY', 'name': 'Physics', 'head': 'Dr. Nkwi'},
        {'code': 'BIO', 'name': 'Biology', 'head': 'Dr. Ndifor'},
    ]
    dept_ids = {}
    for dept in dept_data:
        did = firebase_service.create_document('departments', {
            'institution_id': institution_id,
            'name': dept['name'],
            'code': dept['code'],
            'head_id': '',
            'is_active': True,
            'created_at': (now - timedelta(days=random.randint(30, 90))).isoformat(),
        })
        dept_ids[dept['code']] = did
    result['collections_created']['departments'] = len(dept_data)

    # ── COURSES ──
    course_data = [
        {'code': 'CSC301', 'name': 'Data Structures', 'dept': 'CSC', 'lecturer': 'Dr. Ewane', 'credits': 4},
        {'code': 'CSC401', 'name': 'Algorithms', 'dept': 'CSC', 'lecturer': 'Prof. Asongu', 'credits': 4},
        {'code': 'CSE204', 'name': 'Digital Electronics', 'dept': 'CSE', 'lecturer': 'Dr. Nkwi', 'credits': 3},
        {'code': 'CSE305', 'name': 'Computer Networks', 'dept': 'CSE', 'lecturer': 'Mr. Kelvin', 'credits': 3},
        {'code': 'MAT201', 'name': 'Calculus II', 'dept': 'MAT', 'lecturer': 'Dr. Mbah', 'credits': 4},
        {'code': 'MAT301', 'name': 'Linear Algebra', 'dept': 'MAT', 'lecturer': 'Dr. Mbah', 'credits': 3},
        {'code': 'PHY201', 'name': 'Waves & Optics', 'dept': 'PHY', 'lecturer': 'Dr. Nkwi', 'credits': 3},
    ]
    course_ids = {}
    for c in course_data:
        cid = firebase_service.create_document('courses', {
            'institution_id': institution_id,
            'department_id': dept_ids.get(c['dept'], ''),
            'code': c['code'],
            'name': c['name'],
            'lecturer_id': '',
            'credits': c['credits'],
            'description': f'{c["name"]} course',
            'is_active': True,
            'created_at': (now - timedelta(days=random.randint(30, 90))).isoformat(),
        })
        course_ids[c['code']] = cid
    result['collections_created']['courses'] = len(course_data)

    # ── ATTENDANCE SESSIONS (linked to courses) ──
    session_tpls = [
        ('CSC301', 'Data Structures', 'Dr. Ewane', 65),
        ('CSC401', 'Algorithms', 'Prof. Asongu', 48),
        ('CSE204', 'Digital Electronics', 'Dr. Nkwi', 52),
        ('CSE305', 'Computer Networks', 'Mr. Kelvin', 74),
        ('MAT201', 'Calculus II', 'Dr. Mbah', 88),
    ]
    session_ids = []
    for code, name, lecturer, total in session_tpls:
        sid = firebase_service.create_document('attendance_sessions', {
            'institution_id': institution_id,
            'course_id': code,
            'course_name': name,
            'lecturer_name': lecturer,
            'session_code': str(uuid.uuid4())[:8].upper(),
            'status': 'completed',
            'is_active': False,
            'total_students': total,
            'broker_health': random.choice(['healthy', 'healthy', 'healthy', 'degraded']),
            'broker_latency_ms': random.randint(5, 45),
            'sync_success_pct': round(random.uniform(95, 100), 1),
            'network_status': random.choice(['stable', 'stable', 'stable', 'unstable']),
            'created_at': (now - timedelta(days=random.randint(0, 7), hours=random.randint(0, 12))).isoformat(),
        })
        session_ids.append(sid)
    result['collections_created']['attendance_sessions'] = len(session_tpls)

    # ── MAKE ONE SESSION ACTIVE ──
    if session_ids:
        active_sid = session_ids[0]
        firebase_service.update_document('attendance_sessions', active_sid, {
            'status': 'active',
            'is_active': True,
        })

    # ── ATTENDANCE RECORDS ──
    # Get all student users
    students = firebase_service.query_documents(
        'users',
        filters=[{'field': 'institution_id', 'value': institution_id},
                 {'field': 'role', 'value': 'student'}]
    )
    record_count = 0
    for sid in session_ids:
        for student in students[:10]:  # First 10 students per session
            is_present = random.random() < 0.85
            firebase_service.create_document('attendance_records', {
                'attendance_session_id': sid,
                'student_id': student['id'],
                'status': 'present' if is_present else 'absent',
                'marked_at': (now - timedelta(days=random.randint(0, 7))).isoformat(),
                'is_suspicious': False,
                'suspicion_reason': None,
            })
            record_count += 1
    result['collections_created']['attendance_records'] = record_count

    # ── COURSE ENROLLMENTS ──
    enrollment_count = 0
    for student in students:
        num_courses = random.randint(3, 5)
        enrolled_courses = random.sample(list(course_ids.values()), min(num_courses, len(course_ids)))
        for cid in enrolled_courses:
            existing = firebase_service.query_documents(
                'course_enrollments',
                filters=[{'field': 'course_id', 'value': cid},
                         {'field': 'student_id', 'value': student['id']}]
            )
            if not existing:
                firebase_service.create_document('course_enrollments', {
                    'course_id': cid,
                    'student_id': student['id'],
                    'institution_id': institution_id,
                    'enrollment_date': (now - timedelta(days=random.randint(30, 60))).isoformat(),
                    'is_active': True,
                    'created_at': (now - timedelta(days=random.randint(30, 60))).isoformat(),
                })
                enrollment_count += 1
    result['collections_created']['course_enrollments'] = enrollment_count

    # ── USER PROFILES ──
    for student in students:
        existing_profiles = firebase_service.query_documents(
            'user_profiles',
            filters=[{'field': 'user_id', 'value': student['id']}]
        )
        if not existing_profiles:
            firebase_service.create_document('user_profiles', {
                'user_id': student['id'],
                'institution_id': institution_id,
                'department_id': random.choice(list(dept_ids.values())) if dept_ids else '',
                'employee_id': '',
                'student_id': f"STU{random.randint(10000, 99999)}",
                'join_date': (now - timedelta(days=random.randint(90, 365))).isoformat(),
            })

    # ── EXISTING STUDENT USERS GET FACULTY ASSIGNMENTS ──
    faculties = ['Faculty of Science', 'Faculty of Engineering', 'Faculty of Arts', 'HTTTC']
    for student in students:
        firebase_service.update_document('users', student['id'], {
            'faculty': random.choice(faculties),
            'student_id': f"STU{random.randint(10000, 99999)}",
            'trusted_device': random.random() < 0.7,
            'vpn_detected': random.random() < 0.1,
        })

    result['message'] = 'Comprehensive demo data seeded successfully'
    total = sum(result['collections_created'].values())
    result['total_documents_created'] = total
    logger.info(f"Seeded {total} demo documents for institution {institution_id}")
    return result
