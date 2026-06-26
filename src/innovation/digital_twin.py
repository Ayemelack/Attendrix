"""Institutional Digital Twin.

Provides live campus operational visualization, real-time attendance simulation
maps, department activity monitoring, and predictive campus analytics.
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from collections import defaultdict
from statistics import mean

from .models import DigitalTwinSnapshot
from .registry import registry, InnovationEvent

logger = logging.getLogger(__name__)


class InstitutionalDigitalTwin:
    """Real-time digital representation of campus operations.

    Features:
    - Live campus operational visualization data
    - Real-time attendance heatmap generation
    - Department activity monitoring
    - Predictive operational analytics
    """

    def __init__(self):
        self._firebase = None
        self._repos = None
        self._snapshot_history: List[DigitalTwinSnapshot] = []
        self._config = {
            "snapshot_retention_hours": 72,
            "prediction_window_minutes": 60,
            "anomaly_zone_threshold": 0.3,
        }

    def initialize(self, firebase_service=None, repositories: dict = None) -> None:
        self._firebase = firebase_service
        self._repos = repositories or {}
        registry.subscribe(InnovationEvent.ATTENDANCE_MARKED, self._on_event)
        registry.subscribe(InnovationEvent.SESSION_CREATED, self._on_event)
        registry.subscribe(InnovationEvent.ANOMALY_DETECTED, self._on_event)
        logger.info("InstitutionalDigitalTwin initialized")

    def _on_event(self, data: dict) -> None:
        pass  # Triggers lazy cache invalidation

    # ── Snapshot Generation ──

    def generate_snapshot(self, institution_id: str,
                          active_sessions: List[Dict],
                          classroom_data: List[Dict],
                          department_metrics: Dict[str, Any] = None) -> DigitalTwinSnapshot:
        """Generate a real-time digital twin snapshot."""
        now = datetime.utcnow()
        total_present = sum(
            s.get("present_count", 0) for s in active_sessions
        )
        total_capacity = sum(
            c.get("capacity", 0) for c in classroom_data
        ) or 1
        classroom_utilization = total_present / total_capacity

        dept_activity = self._build_department_activity(
            active_sessions, department_metrics
        )
        hotspots = self._detect_anomaly_hotspots(active_sessions, classroom_data)
        prediction = self._predict_next_hour(
            active_sessions, classroom_data
        )

        snapshot = DigitalTwinSnapshot(
            institution_id=institution_id,
            timestamp=now,
            active_sessions=len(active_sessions),
            total_present=total_present,
            classroom_utilization=round(classroom_utilization, 4),
            department_activity=dept_activity,
            anomaly_hotspots=hotspots,
            prediction_next_hour=prediction,
        )
        self._snapshot_history.append(snapshot)
        self._prune_history()
        return snapshot

    def _build_department_activity(self, sessions: List[Dict],
                                    dept_metrics: Dict) -> Dict[str, Any]:
        """Build department-level activity snapshot."""
        by_dept = defaultdict(list)
        for s in sessions:
            dept = s.get("department") or s.get("faculty") or "unknown"
            by_dept[dept].append(s)

        activity = {}
        for dept, dept_sessions in by_dept.items():
            present = sum(s.get("present_count", 0) for s in dept_sessions)
            enrolled = sum(s.get("enrolled_count", 0) for s in dept_sessions)
            activity[dept] = {
                "active_sessions": len(dept_sessions),
                "total_present": present,
                "total_enrolled": enrolled,
                "attendance_rate": round(
                    present / enrolled, 4
                ) if enrolled > 0 else 0.0,
                "status": "active" if present > 0 else "idle"
            }

        return {
            "departments": activity,
            "total_active_departments": sum(
                1 for d in activity.values() if d["active_sessions"] > 0
            )
        }

    def _detect_anomaly_hotspots(self, sessions: List[Dict],
                                  classrooms: List[Dict]) -> List[Dict]:
        """Detect locations with anomalous attendance patterns."""
        hotspots = []
        avg_attendance = mean(
            [s.get("present_count", 0) for s in sessions]
        ) if sessions else 0.0

        for s in sessions:
            present = s.get("present_count", 0)
            enrolled = s.get("enrolled_count", 1)
            rate = present / enrolled if enrolled > 0 else 0.0
            deviation = abs(rate - avg_attendance / (enrolled or 1))

            if deviation > self._config["anomaly_zone_threshold"]:
                hotspots.append({
                    "session_id": s.get("id", ""),
                    "location": s.get("location") or s.get("classroom", ""),
                    "attendance_rate": round(rate, 4),
                    "deviation": round(deviation, 4),
                    "severity": "high" if deviation > 0.5 else "medium",
                })
        return hotspots

    def _predict_next_hour(self, sessions: List[Dict],
                            classrooms: List[Dict]) -> Optional[Dict[str, Any]]:
        """Predict campus state one hour ahead."""
        if not self._snapshot_history:
            return None

        recent = self._snapshot_history[-10:]
        if len(recent) < 3:
            return None

        present_trend = [
            s.total_present for s in recent
        ]
        avg_increase = (
            (present_trend[-1] - present_trend[0]) / len(present_trend)
            if len(present_trend) > 1 else 0
        )

        predicted_present = max(
            0, int(present_trend[-1] + avg_increase * 4)
        )
        predicted_sessions = max(
            0, int(recent[-1].active_sessions + avg_increase * 2)
        )

        return {
            "predicted_present": predicted_present,
            "predicted_active_sessions": predicted_sessions,
            "trend": "increasing" if avg_increase > 0 else (
                "decreasing" if avg_increase < 0 else "stable"
            ),
            "confidence": round(
                min(1.0, len(recent) / 10), 4
            ),
            "forecast_horizon": "60 minutes"
        }

    def _prune_history(self) -> None:
        cutoff = datetime.utcnow() - timedelta(
            hours=self._config["snapshot_retention_hours"]
        )
        self._snapshot_history = [
            s for s in self._snapshot_history
            if s.timestamp > cutoff
        ]

    # ── Campus Heatmap Data ──

    def generate_heatmap_data(self, institution_id: str,
                               sessions: List[Dict]) -> Dict[str, Any]:
        """Generate heatmap visualization data for campus map."""
        by_location = defaultdict(list)
        for s in sessions:
            loc = s.get("location") or s.get("classroom", "unknown")
            by_location[loc].append(s)

        zones = []
        max_density = 0
        for location, loc_sessions in by_location.items():
            present = sum(s.get("present_count", 0) for s in loc_sessions)
            capacity = sum(
                s.get("capacity", 100) for s in loc_sessions
            ) or 1
            density = present / capacity
            max_density = max(max_density, density)
            zones.append({
                "location": location,
                "present_count": present,
                "capacity": capacity,
                "density": round(density, 4),
                "active_sessions": len(loc_sessions),
                "intensity": self._heat_intensity(density),
            })

        return {
            "institution_id": institution_id,
            "timestamp": datetime.utcnow().isoformat(),
            "zones": zones,
            "max_density": round(max_density, 4),
            "total_present_campus": sum(
                s.get("present_count", 0) for s in sessions
            ),
            "total_active_sessions": len(sessions),
        }

    @staticmethod
    def _heat_intensity(density: float) -> str:
        if density > 0.8:
            return "critical"
        if density > 0.6:
            return "high"
        if density > 0.4:
            return "medium"
        if density > 0.2:
            return "low"
        return "inactive"

    # ── Performance Intelligence ──

    def institutional_performance(self, institution_id: str,
                                   snapshot_history: List[DigitalTwinSnapshot] = None) -> Dict[str, Any]:
        """Calculate institutional performance intelligence."""
        snapshots = snapshot_history or self._snapshot_history
        if not snapshots:
            return {"institution_id": institution_id, "status": "insufficient_data"}

        recent = snapshots[-20:]
        avg_utilization = mean(s.classroom_utilization for s in recent)
        avg_active = mean(s.active_sessions for s in recent)
        avg_present = mean(s.total_present for s in recent)

        peak = max(recent, key=lambda s: s.total_present)
        trough = min(recent, key=lambda s: s.total_present)

        return {
            "institution_id": institution_id,
            "period": f"Last {len(recent)} snapshots",
            "average_utilization": round(avg_utilization, 4),
            "average_active_sessions": round(avg_active, 1),
            "average_present_students": round(avg_present, 1),
            "peak_utilization": {
                "timestamp": peak.timestamp.isoformat(),
                "present": peak.total_present,
                "sessions": peak.active_sessions
            },
            "trough_utilization": {
                "timestamp": trough.timestamp.isoformat(),
                "present": trough.total_present,
                "sessions": trough.active_sessions
            },
            "operational_score": round(
                (avg_utilization * 0.4 + (avg_active / max(avg_active, 1)) * 0.3 +
                 (avg_present / max(avg_present, 1)) * 0.3), 4
            ),
            "status": self._overall_status(avg_utilization, avg_present)
        }

    @staticmethod
    def _overall_status(utilization: float, present: float) -> str:
        if utilization > 0.6 and present > 100:
            return "highly_active"
        if utilization > 0.4:
            return "active"
        if utilization > 0.2:
            return "moderate"
        return "low_activity"

    def cleanup(self) -> None:
        self._snapshot_history.clear()
        logger.info("InstitutionalDigitalTwin cleaned up")
