import random
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, List

FACULTIES = ["Faculty of Science", "Faculty of Engineering", "Faculty of Arts", "HTTTC", "Faculty of Education", "Faculty of Law"]
DEPARTMENTS = ["Computer Science", "Electrical Eng.", "Civil Eng.", "Mathematics", "Physics", "Chemistry", "English", "History"]
LECTURERS = ["Dr. Ewane", "Mr. Kelvin", "Prof. Asongu", "Dr. Nkwi", "Mrs. Atem", "Dr. Mbah", "Prof. Tazanu", "Mr. Neba"]
STUDENT_NAMES = [
    "Ayemelack Fotsa", "Nkwenti Julius", "Tata Prisca", "Mbah Bryan", "Asaah Derick",
    "Kum Christian", "Ndifor Claris", "Lum Roland", "Njini Emmanuel", "Fon Felicity",
    "Atanga Divine", "Che Denis", "Nde Melvis", "Suh Cynthia", "Akeh Bertrand"
]
COURSES = ["CSC301", "CSC401", "CSE204", "CSE305", "MAT201", "PHY101", "CHM202", "ENG101"]

NETWORK_NODES = [
    {"id": "node_sci", "name": "Science Block", "type": "building"},
    {"id": "node_eng", "name": "Engineering Block", "type": "building"},
    {"id": "node_httc", "name": "HTTTC Annex", "type": "building"},
    {"id": "node_lib", "name": "Central Library", "type": "building"},
    {"id": "node_admin", "name": "Admin Block", "type": "building"},
    {"id": "node_core", "name": "Core Broker", "type": "broker"},
]

SECURITY_EVENT_TYPES = [
    ("duplicate_qr", "Duplicate QR scan detected", "high"),
    ("proxy_attempt", "Proxy attendance attempt blocked", "critical"),
    ("vpn_detected", "VPN usage detected during session", "medium"),
    ("device_mismatch", "Device fingerprint mismatch", "high"),
    ("geo_anomaly", "Impossible geolocation detected", "critical"),
    ("rapid_replay", "Rapid QR replay attempt blocked", "high"),
    ("unauthorized_device", "Unauthorized device attempted access", "medium"),
]

ACTIVITY_TYPES = [
    ("session_started", "attendance session started"),
    ("session_ended", "attendance session ended"),
    ("node_synced", "node synchronized"),
    ("broker_latency", "MQTT Broker latency changed"),
    ("sync_completed", "offline sync completed"),
    ("alert_generated", "security alert generated"),
    ("student_enrolled", "student enrolled in course"),
]


def _rand_time(days_back: int = 7) -> str:
    return (datetime.utcnow() - timedelta(
        hours=random.randint(0, days_back * 24),
        minutes=random.randint(0, 59)
    )).strftime("%H:%M")


def get_activity_feed(limit: int = 15) -> List[Dict[str, Any]]:
    events = []
    for _ in range(limit):
        t = random.choice(ACTIVITY_TYPES)
        faculty = random.choice(FACULTIES)
        time_str = _rand_time(1)
        msg = t[1]
        if t[0] == "session_started":
            msg = f"{random.choice(COURSES)} {t[1]}"
        elif t[0] == "node_synced":
            msg = f"{faculty} {t[1]}"
        elif t[0] == "broker_latency":
            msg = f"MQTT Broker latency increased to {random.randint(15, 85)}ms"
        elif t[0] == "sync_completed":
            msg = f"Offline sync completed — {random.randint(50, 500)} records synced"
        elif t[0] == "student_enrolled":
            msg = f"{random.choice(STUDENT_NAMES)} {t[1]}"
        events.append({
            "id": str(uuid.uuid4())[:8],
            "time": time_str,
            "type": t[0],
            "message": msg,
            "faculty": faculty,
        })
    events.sort(key=lambda e: e["time"], reverse=True)
    return events


def get_security_alerts(limit: int = 8) -> List[Dict[str, Any]]:
    alerts = []
    for _ in range(limit):
        t = random.choice(SECURITY_EVENT_TYPES)
        student = random.choice(STUDENT_NAMES)
        alerts.append({
            "id": str(uuid.uuid4())[:8],
            "time": _rand_time(2),
            "type": t[0],
            "severity": t[2],
            "message": f"{t[1]} — {student}",
            "resolved": random.random() < 0.3,
        })
    alerts.sort(key=lambda a: a["time"], reverse=True)
    return alerts


def get_network_status() -> Dict[str, Any]:
    nodes = []
    all_healthy = True
    for node in NETWORK_NODES:
        healthy = random.random() < 0.85
        if not healthy:
            all_healthy = False
        latency = random.randint(5, 60) if healthy else random.randint(100, 500)
        nodes.append({
            **node,
            "status": "healthy" if healthy else "degraded" if random.random() < 0.5 else "offline",
            "latency_ms": latency,
            "packet_loss": round(random.uniform(0, 2.5), 1) if healthy else round(random.uniform(5, 25), 1),
            "last_seen": (datetime.utcnow() - timedelta(seconds=random.randint(0, 120))).isoformat(),
        })

    return {
        "overall_status": "healthy" if all_healthy else "degraded",
        "nodes": nodes,
        "broker": {
            "messages_per_sec": round(random.uniform(120, 450), 1),
            "connected_nodes": sum(1 for n in nodes if n["status"] != "offline"),
            "total_nodes": len(nodes),
            "dropped_messages": random.randint(0, 8),
            "bandwidth_mbps": round(random.uniform(45, 240), 1),
            "uptime": f"{random.randint(5, 72)}h {random.randint(0, 59)}m",
            "qos_levels": {str(i): random.randint(100, 2000) for i in range(3)},
        },
        "offline_sync": {
            "pending_syncs": random.randint(0, 500),
            "estimated_recovery_mins": random.randint(1, 5),
            "queue_healthy": random.random() < 0.9,
        },
    }


def get_session_health() -> Dict[str, Any]:
    sessions = []
    for i in range(random.randint(3, 6)):
        course = random.choice(COURSES)
        lecturer = random.choice(LECTURERS)
        students = random.randint(30, 250)
        present = int(students * random.uniform(0.7, 0.98))
        healthy = random.random() < 0.85
        sessions.append({
            "id": f"sess_{course.lower()}_{i}",
            "course": course,
            "lecturer": lecturer,
            "total_students": students,
            "present": present,
            "absent": students - present,
            "attendance_rate": round(present / students * 100, 1),
            "status": random.choice(["active", "active", "active", "syncing", "completed"]),
            "health": {
                "broker": "healthy" if healthy else "degraded",
                "latency_ms": random.randint(5, 35) if healthy else random.randint(50, 200),
                "sync_success_pct": round(random.uniform(95, 100), 1) if healthy else round(random.uniform(70, 90), 1),
                "network": "stable" if healthy else "unstable",
            },
        })
    return {
        "active_sessions": len([s for s in sessions if s["status"] == "active"]),
        "total_sessions": len(sessions),
        "sessions": sessions,
    }


def get_attendance_trends(days: int = 14) -> Dict[str, Any]:
    dates = []
    rates = []
    for i in range(days):
        d = (datetime.utcnow() - timedelta(days=days - 1 - i)).strftime("%Y-%m-%d")
        rate = round(random.uniform(75, 98), 1)
        dates.append(d)
        rates.append(rate)
    return {
        "daily_rates": rates,
        "dates": dates,
        "average": round(sum(rates) / len(rates), 1),
        "faculty_comparison": [
            {"faculty": f, "rate": round(random.uniform(70, 98), 1)} for f in FACULTIES
        ],
    }


def get_students_with_risk(limit: int = 12) -> List[Dict[str, Any]]:
    students = []
    for name in STUDENT_NAMES[:limit]:
        risk = random.choice(["low", "low", "low", "medium", "medium", "high"])
        attendance = round(random.uniform(60, 100), 1) if risk != "high" else round(random.uniform(40, 70), 1)
        students.append({
            "name": name,
            "student_id": f"STU{random.randint(10000, 99999)}",
            "faculty": random.choice(FACULTIES),
            "attendance_pct": attendance,
            "risk_level": risk,
            "trusted_device": random.random() < 0.7,
            "vpn_detected": random.random() < 0.1,
            "suspicious_attempts": random.randint(0, 3) if risk == "high" else random.randint(0, 1),
            "last_active": (datetime.utcnow() - timedelta(hours=random.randint(0, 72))).isoformat(),
        })
    return students


def get_session_history(course: str = None, limit: int = 10) -> List[Dict[str, Any]]:
    sessions = []
    for i in range(limit):
        c = course or random.choice(COURSES)
        sessions.append({
            "course": c,
            "lecturer": random.choice(LECTURERS),
            "date": (datetime.utcnow() - timedelta(days=random.randint(0, 30))).strftime("%Y-%m-%d"),
            "start": f"{random.randint(8, 16):02d}:00",
            "end": f"{random.randint(9, 17):02d}:00",
            "students": random.randint(40, 250),
            "attendance_pct": round(random.uniform(65, 99), 1),
            "network_health": random.choice(["stable", "stable", "stable", "degraded", "offline"]),
        })
    return sessions


def get_offline_log() -> Dict[str, Any]:
    return {
        "total_offline_sessions": random.randint(5, 30),
        "pending_syncs": random.randint(0, 500),
        "last_sync": (datetime.utcnow() - timedelta(minutes=random.randint(1, 30))).isoformat(),
        "sync_success_rate": round(random.uniform(92, 100), 1),
        "nodes_offline": random.randint(0, 2),
        "queue": [
            {
                "id": str(uuid.uuid4())[:8],
                "node": random.choice(NETWORK_NODES)["name"],
                "records": random.randint(10, 200),
                "since": (datetime.utcnow() - timedelta(hours=random.randint(1, 8))).strftime("%H:%M"),
                "status": random.choice(["pending", "pending", "syncing", "failed"]),
            }
            for _ in range(random.randint(2, 6))
        ],
    }


def get_infrastructure_status() -> Dict[str, Any]:
    isp_providers = [
        {"name": "MTN", "status": random.choice(["up", "up", "up", "degraded"]), "latency_ms": random.randint(20, 120), "bandwidth_mbps": round(random.uniform(10, 100), 1)},
        {"name": "Orange", "status": random.choice(["up", "up", "degraded", "down"]), "latency_ms": random.randint(25, 150), "bandwidth_mbps": round(random.uniform(8, 80), 1)},
        {"name": "Camtel", "status": random.choice(["up", "degraded", "down"]), "latency_ms": random.randint(30, 200), "bandwidth_mbps": round(random.uniform(5, 50), 1)},
    ]
    active_isp = [p for p in isp_providers if p["status"] == "up"]
    return {
        "ups": {
            "charge_pct": random.randint(60, 100),
            "runtime_minutes": random.randint(30, 180),
            "status": random.choice(["online", "online", "online", "on_battery", "on_battery"]),
            "load_pct": random.randint(15, 60),
        },
        "isp": isp_providers,
        "active_isp_count": len(active_isp),
        "power_status": random.choice(["mains", "mains", "mains", "generator", "battery"]),
        "generator": {
            "running": random.random() < 0.2,
            "fuel_pct": random.randint(20, 100) if random.random() < 0.2 else None,
        },
    }


def get_compliance_status() -> Dict[str, Any]:
    exam_active = random.random() < 0.4
    return {
        "exam_mode": exam_active,
        "exam_type": random.choice(["GCE", "Baccalaureate", "BEPC", "Probatoire", "CAP"]) if exam_active else None,
        "exam_period": "May/June 2026",
        "last_minesec_report": (datetime.utcnow() - timedelta(days=random.randint(1, 14))).strftime("%Y-%m-%d"),
        "report_compliance_pct": round(random.uniform(85, 100), 1),
        "pending_reports": random.randint(0, 3),
        "audit_trail": [
            {
                "date": (datetime.utcnow() - timedelta(days=i)).strftime("%Y-%m-%d"),
                "action": random.choice(["attendance_exported", "report_generated", "exam_session_logged", "sync_verified"]),
                "status": random.choice(["completed", "completed", "completed", "pending"]),
            }
            for i in range(random.randint(3, 7))
        ],
        "gce_candidates": random.randint(200, 2000) if exam_active else 0,
    }


def get_payment_status() -> Dict[str, Any]:
    momo_providers = [
        {"name": "MTN MoMo", "available": True, "pending_txns": random.randint(0, 15)},
        {"name": "Orange Money", "available": True, "pending_txns": random.randint(0, 10)},
    ]
    total_sales = random.randint(50000, 500000)
    return {
        "mobile_money": momo_providers,
        "voucher_sales_xaf": total_sales,
        "voucher_sales_count": random.randint(10, 100),
        "pending_txns": sum(p["pending_txns"] for p in momo_providers),
        "refund_queue": random.randint(0, 5),
        "sms_queue_count": random.randint(0, 50),
        "recent_txns": [
            {
                "id": f"TXN{random.randint(1000,9999)}",
                "phone": f"6{random.randint(70,99)}{random.randint(100000,999999)}",
                "amount_xaf": random.randint(1000, 25000),
                "provider": random.choice(["MTN", "Orange"]),
                "status": random.choice(["completed", "completed", "pending", "failed"]),
                "time": _rand_time(1),
            }
            for _ in range(random.randint(3, 8))
        ],
    }


def get_p2p_sync_status() -> Dict[str, Any]:
    total_neighbors = random.randint(12, 22)
    online = total_neighbors - random.randint(0, 4)
    return {
        "total_neighbors": total_neighbors,
        "online_neighbors": online,
        "offline_neighbors": total_neighbors - online,
        "gossip_protocol": "libp2p / Kademlia DHT",
        "last_gossip_round": (datetime.utcnow() - timedelta(seconds=random.randint(1, 60))).isoformat(),
        "messages_relayed": random.randint(500, 5000),
        "peers": [
            {
                "id": f"peer_{random.choice(['sci','eng','lib','admin','httc','law'])}",
                "address": f"192.168.{random.randint(1,10)}.{random.randint(2,254)}",
                "status": random.choice(["online", "online", "online", "online", "offline"]),
                "latency_ms": random.randint(2, 50),
                "blocks_synced": random.randint(100, 5000),
                "last_seen": (datetime.utcnow() - timedelta(seconds=random.randint(0, 120))).isoformat(),
            }
            for _ in range(random.randint(4, 8))
        ],
    }


def get_quick_actions() -> List[Dict[str, str]]:
    return [
        {"id": "qa_session", "label_en": "New Session", "label_fr": "Nouvelle Session", "icon": "fa-play-circle", "color": "#10B981"},
        {"id": "qa_voucher", "label_en": "Generate Vouchers", "label_fr": "Générer Codes", "icon": "fa-ticket-alt", "color": "#4F46E5"},
        {"id": "qa_report", "label_en": "MINESEC Report", "label_fr": "Rapport MINESEC", "icon": "fa-file-export", "color": "#F59E0B"},
        {"id": "qa_sms", "label_en": "Send Alert", "label_fr": "Envoyer Alerte", "icon": "fa-sms", "color": "#06B6D4"},
        {"id": "qa_sync", "label_en": "Force Sync", "label_fr": "Sync Forcée", "icon": "fa-sync-alt", "color": "#8B5CF6"},
        {"id": "qa_backup", "label_en": "Backup Now", "label_fr": "Sauvegarder", "icon": "fa-download", "color": "#EC4899"},
    ]


TRANSLATIONS = {
    "topbar.students": {"en": "Students", "fr": "Étudiants"},
    "topbar.active": {"en": "Active", "fr": "Actifs"},
    "topbar.latency": {"en": "Latency", "fr": "Latence"},
    "topbar.sync": {"en": "Sync", "fr": "Synchro"},
    "network_healthy": {"en": "Network Healthy", "fr": "Réseau Sain"},
    "network_degraded": {"en": "Degraded", "fr": "Dégradé"},
    "overview": {"en": "Overview", "fr": "Aperçu"},
    "students": {"en": "Students", "fr": "Étudiants"},
    "sessions": {"en": "Sessions", "fr": "Sessions"},
    "network": {"en": "Network", "fr": "Réseau"},
    "security": {"en": "Security", "fr": "Sécurité"},
    "reports": {"en": "Reports", "fr": "Rapports"},
    "offline_sync": {"en": "Offline Sync", "fr": "Sync Hors-Ligne"},
    "offline_recovery": {"en": "Offline Recovery", "fr": "Récupération Hors-Ligne"},
    "compliance": {"en": "Compliance", "fr": "Conformité"},
    "payments": {"en": "Payments", "fr": "Paiements"},
    "logout": {"en": "Logout", "fr": "Déconnexion"},
    "loading": {"en": "Loading...", "fr": "Chargement..."},
    "no_data": {"en": "No data", "fr": "Aucune donnée"},
}


def get_translations(lang: str = "en") -> Dict[str, str]:
    result = {}
    for key, val in TRANSLATIONS.items():
        result[key] = val.get(lang, val["en"])
    return result
