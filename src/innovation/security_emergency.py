"""Campus Security & Emergency Intelligence.

Emergency evacuation attendance reconciliation, missing student detection,
restricted-area intelligence, and real-time campus presence mapping.
"""

import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
from collections import defaultdict

from .models import EmergencyReport
from .registry import registry, InnovationEvent

logger = logging.getLogger(__name__)


class SecurityEmergency:
    """Campus security and emergency response intelligence.

    Features:
    - Emergency evacuation attendance reconciliation
    - Missing student detection during drills/incidents
    - Restricted-area intelligence
    - Emergency accountability tracking
    - Real-time campus presence mapping for emergencies
    """

    def __init__(self):
        self._firebase = None
        self._repos = None
        self._active_emergencies: Dict[str, EmergencyReport] = {}
        self._config = {
            "accountability_timeout_minutes": 30,
            "restricted_zone_alert_threshold": 1,
            "auto_declare_missing_after_minutes": 15,
        }

    def initialize(self, firebase_service=None, repositories: dict = None) -> None:
        self._firebase = firebase_service
        self._repos = repositories or {}
        logger.info("SecurityEmergency initialized")

    # ── Emergency Management ──

    def activate_emergency(self, institution_id: str,
                           emergency_type: str,
                           triggered_by: str = "system") -> EmergencyReport:
        """Activate an emergency event for the institution."""
        report = EmergencyReport(
            emergency_id=f"EMG-{institution_id}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
            institution_id=institution_id,
            type=emergency_type,
            triggered_at=datetime.utcnow(),
            status="active",
        )
        self._active_emergencies[report.emergency_id] = report

        registry.emit(InnovationEvent.EMERGENCY_ACTIVATED, {
            "emergency_id": report.emergency_id,
            "institution_id": institution_id,
            "type": emergency_type,
        })

        logger.info(f"Emergency activated: {report.emergency_id} ({emergency_type})")
        return report

    def resolve_emergency(self, emergency_id: str) -> bool:
        """Resolve an active emergency."""
        report = self._active_emergencies.get(emergency_id)
        if not report:
            return False
        report.status = "resolved"
        report.resolved_at = datetime.utcnow()

        registry.emit(InnovationEvent.EMERGENCY_RESOLVED, {
            "emergency_id": emergency_id,
            "institution_id": report.institution_id,
            "duration_minutes": (
                (report.resolved_at - report.triggered_at).total_seconds() / 60
            ) if report.resolved_at else 0,
        })
        logger.info(f"Emergency resolved: {emergency_id}")
        return True

    # ── Evacuation Reconciliation ──

    def reconcile_evacuation(self, emergency_id: str,
                              expected_present: Dict[str, List[str]],
                              safe_zone_checkins: Dict[str, List[str]]) -> Dict[str, Any]:
        """Reconcile who is accounted for vs missing during evacuation."""
        report = self._active_emergencies.get(emergency_id)
        if not report:
            return {"error": "Emergency not found"}

        all_expected = set()
        for zone, persons in expected_present.items():
            all_expected.update(persons)

        all_accounted = set()
        safe_zones = {}
        for zone, persons in safe_zone_checkins.items():
            safe_zones[zone] = persons
            all_accounted.update(persons)

        missing = all_expected - all_accounted
        report.total_accounted = len(all_accounted)
        report.missing_count = len(missing)
        report.missing_students = list(missing)
        report.safe_zones = safe_zones

        return {
            "emergency_id": emergency_id,
            "institution_id": report.institution_id,
            "type": report.type,
            "total_expected": len(all_expected),
            "total_accounted": len(all_accounted),
            "missing_count": len(missing),
            "missing_persons": sorted(missing)[:20],     # Top 20 for UI
            "safe_zones": {
                zone: len(persons) for zone, persons in safe_zones.items()
            },
            "accountability_rate": round(
                len(all_accounted) / len(all_expected), 4
            ) if all_expected else 1.0,
            "status": "deficit" if missing else "all_accounted"
        }

    # ── Missing Student Detection ──

    def detect_missing_students(self, institution_id: str,
                                 session_attendance: Dict[str, List[str]],
                                 last_known_presence: Dict[str, datetime]) -> List[Dict]:
        """Detect students unaccounted for during emergencies."""
        missing = []
        now = datetime.utcnow()

        for location, student_ids in session_attendance.items():
            for student_id in student_ids:
                last_seen = last_known_presence.get(student_id)
                if last_seen:
                    elapsed = (now - last_seen).total_seconds() / 60
                    if elapsed > self._config["auto_declare_missing_after_minutes"]:
                        missing.append({
                            "student_id": student_id,
                            "last_seen_location": location,
                            "last_seen_at": last_seen.isoformat(),
                            "minutes_unaccounted": round(elapsed, 1),
                            "severity": "critical" if elapsed > 60 else (
                                "high" if elapsed > 30 else "moderate"
                            )
                        })

        # Check active emergencies for cross-reference
        for emergency in self._active_emergencies.values():
            if emergency.institution_id == institution_id:
                missing.extend([
                    {"student_id": sid, "source": "emergency_reconciliation",
                     "severity": "critical"}
                    for sid in emergency.missing_students
                    if sid not in {m["student_id"] for m in missing}
                ])

        return sorted(missing, key=lambda x: x.get("minutes_unaccounted", 0), reverse=True)

    # ── Restricted Area Intelligence ──

    def monitor_restricted_zones(self, institution_id: str,
                                  zone_access_log: List[Dict],
                                  authorized_personnel: Dict[str, List[str]]) -> List[Dict]:
        """Detect unauthorized presence in restricted areas."""
        alerts = []
        for entry in zone_access_log:
            zone = entry.get("zone", "")
            user_id = entry.get("user_id", "")
            authorized = authorized_personnel.get(zone, [])

            if user_id not in authorized:
                alerts.append({
                    "zone": zone,
                    "user_id": user_id,
                    "timestamp": entry.get("timestamp", ""),
                    "severity": "critical" if zone in (
                        "server_room", "admin_office", "exam_storage"
                    ) else "warning",
                    "action": "log_and_notify_security"
                })

        return alerts

    # ── Campus Presence Mapping ──

    def campus_presence_map(self, institution_id: str,
                             active_sessions: List[Dict]) -> Dict[str, Any]:
        """Generate real-time campus presence map for emergency response."""
        by_building = defaultdict(list)
        for session in active_sessions:
            building = session.get("building",
                        session.get("location", "unknown"))
            by_building[building].append(session)

        buildings = {}
        total_present = 0
        for building, sessions in by_building.items():
            present = sum(s.get("present_count", 0) for s in sessions)
            capacity = sum(s.get("capacity", 0) for s in sessions)
            total_present += present
            buildings[building] = {
                "present": present,
                "capacity": capacity,
                "active_sessions": len(sessions),
                "utilization": round(present / capacity, 4) if capacity > 0 else 0,
            }

        return {
            "institution_id": institution_id,
            "timestamp": datetime.utcnow().isoformat(),
            "total_present_campus": total_present,
            "buildings": buildings,
            "active_emergencies": [
                {
                    "id": eid,
                    "type": e.type,
                    "triggered_at": e.triggered_at.isoformat(),
                    "missing_count": e.missing_count,
                }
                for eid, e in self._active_emergencies.items()
                if e.institution_id == institution_id and e.status == "active"
            ]
        }

    def get_active_emergencies(self, institution_id: str = None) -> List[Dict]:
        """Get all active emergencies, optionally filtered by institution."""
        emergencies = self._active_emergencies.values()
        if institution_id:
            emergencies = [
                e for e in emergencies if e.institution_id == institution_id
            ]
        return [
            {
                "id": e.emergency_id,
                "type": e.type,
                "institution_id": e.institution_id,
                "triggered_at": e.triggered_at.isoformat(),
                "status": e.status,
                "total_accounted": e.total_accounted,
                "missing_count": e.missing_count,
                "missing_students": e.missing_students[:10],
            }
            for e in emergencies
            if e.status == "active"
        ]

    def cleanup(self) -> None:
        self._active_emergencies.clear()
        logger.info("SecurityEmergency cleaned up")
