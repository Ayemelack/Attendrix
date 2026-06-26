"""Smart Classroom Infrastructure Intelligence.

Provides real-time classroom occupancy intelligence, utilization analytics,
overcrowding prediction, seating analysis, and timetable optimization.
"""

import logging
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from collections import defaultdict
from statistics import mean

from .models import ClassroomIntelligence
from .registry import registry, InnovationEvent

logger = logging.getLogger(__name__)


class SmartClassroomIntelligence:
    """Classroom infrastructure intelligence module.

    Capabilities:
    - Real-time occupancy tracking
    - Underutilized hall detection
    - Overcrowding prediction from enrollment + attendance patterns
    - Seating analytics and zone density
    - Timetable optimization recommendations
    """

    def __init__(self):
        self._firebase = None
        self._repos = None
        self._classroom_cache: Dict[str, ClassroomIntelligence] = {}
        self._config = {
            "utilization_warning_threshold": 0.3,
            "overcrowding_threshold": 0.9,
            "optimization_lookback_days": 30,
        }

    def initialize(self, firebase_service=None, repositories: dict = None) -> None:
        self._firebase = firebase_service
        self._repos = repositories or {}
        registry.subscribe(InnovationEvent.ATTENDANCE_MARKED, self._on_attendance)
        logger.info("SmartClassroomIntelligence initialized")

    def _on_attendance(self, data: dict) -> None:
        classroom_id = data.get("classroom_id") or data.get("location")
        if classroom_id and classroom_id in self._classroom_cache:
            del self._classroom_cache[classroom_id]

    # ── Occupancy Intelligence ──

    def get_classroom_intelligence(self, classroom_id: str,
                                   capacity: int,
                                   current_attendees: int,
                                   schedule: List[Dict] = None) -> ClassroomIntelligence:
        """Calculate real-time classroom intelligence metrics."""
        if classroom_id in self._classroom_cache:
            return self._classroom_cache[classroom_id]

        utilization = current_attendees / capacity if capacity > 0 else 0.0
        peak_hours = self._analyze_peak_hours(schedule or [])
        underutilized = utilization < self._config["utilization_warning_threshold"]
        overcrowding_risk = self._evaluate_overcrowding(
            current_attendees, capacity, schedule or []
        )
        seating_density = self._compute_seating_density(
            capacity, current_attendees
        ) if current_attendees > 0 else None

        intelligence = ClassroomIntelligence(
            classroom_id=classroom_id,
            institution_id="",
            current_occupancy=current_attendees,
            max_capacity=capacity,
            utilization_rate=round(utilization, 4),
            peak_hours=peak_hours,
            underutilized=underutilized,
            overcrowding_risk=overcrowding_risk,
            seating_density_map=seating_density,
        )
        self._classroom_cache[classroom_id] = intelligence
        return intelligence

    def _analyze_peak_hours(self, schedule: List[Dict]) -> List[str]:
        """Identify peak usage hours from schedule history."""
        if not schedule:
            return []
        hour_counts = defaultdict(int)
        for entry in schedule:
            start = entry.get("start_time", "")
            if isinstance(start, str) and ":" in start:
                hour = start.split(":")[0]
                hour_counts[hour] += 1
        if not hour_counts:
            return []
        max_count = max(hour_counts.values())
        return sorted(
            h for h, c in hour_counts.items()
            if c >= max_count * 0.7
        )[:5]

    def _evaluate_overcrowding(self, current: int, capacity: int,
                                schedule: List[Dict]) -> str:
        """Predict overcrowding risk from current + scheduled attendance."""
        ratio = current / capacity if capacity > 0 else 0.0
        if ratio >= self._config["overcrowding_threshold"]:
            return "critical"
        if ratio >= self._config["overcrowding_threshold"] - 0.15:
            return "warning"
        if schedule:
            upcoming_enrollment = max(
                (e.get("enrolled", 0) for e in schedule if e.get("enrolled")),
                default=0
            )
            future_ratio = upcoming_enrollment / capacity if capacity > 0 else 0.0
            if future_ratio >= self._config["overcrowding_threshold"]:
                return "warning"
        return "normal"

    def _compute_seating_density(self, capacity: int,
                                 attendees: int) -> Optional[Dict[str, float]]:
        """Compute theoretical seating zone densities."""
        if capacity <= 0 or attendees <= 0:
            return None
        density = attendees / capacity
        return {
            "overall_density": round(density, 4),
            "estimated_front_zone": round(min(1.0, density * 1.2), 4),
            "estimated_middle_zone": round(density, 4),
            "estimated_rear_zone": round(max(0.0, density * 0.7), 4),
        }

    # ── Underutilized Hall Detection ──

    def find_underutilized_halls(self, institution_id: str,
                                 classroom_metrics: List[ClassroomIntelligence],
                                 threshold: float = None) -> List[Dict]:
        """Identify consistently underutilized classrooms."""
        threshold = threshold or self._config["utilization_warning_threshold"]
        underutilized = []
        for cm in classroom_metrics:
            if cm.utilization_rate < threshold:
                underutilized.append({
                    "classroom_id": cm.classroom_id,
                    "utilization_rate": cm.utilization_rate,
                    "capacity": cm.max_capacity,
                    "current_occupancy": cm.current_occupancy,
                    "recommendation": self._utilization_recommendation(
                        cm.utilization_rate
                    )
                })
        return sorted(underutilized, key=lambda x: x["utilization_rate"])

    @staticmethod
    def _utilization_recommendation(rate: float) -> str:
        if rate < 0.1:
            return "Consider repurposing or consolidating sessions"
        if rate < 0.2:
            return "Review scheduling allocation for this room"
        if rate < 0.3:
            return "Optimize timetable to consolidate underfilled sessions"
        return "Monitor utilization trends"

    # ── Overcrowding Prediction ──

    def predict_overcrowding(self, institution_id: str,
                             classrooms: List[Dict]) -> List[Dict]:
        """Predict which classrooms will face overcrowding."""
        predictions = []
        for room in classrooms:
            capacity = room.get("capacity", 0)
            enrolled = room.get("enrolled_students", 0)
            avg_attendance_rate = room.get("avg_attendance_rate", 0.8)
            expected = enrolled * avg_attendance_rate
            ratio = expected / capacity if capacity > 0 else 0.0

            if ratio >= self._config["overcrowding_threshold"]:
                predictions.append({
                    "classroom_id": room.get("id", ""),
                    "name": room.get("name", ""),
                    "capacity": capacity,
                    "enrolled": enrolled,
                    "expected_attendance": round(expected),
                    "projected_ratio": round(ratio, 4),
                    "risk": "critical" if ratio >= 1.0 else "high",
                    "recommendation": "Reschedule to larger hall" if ratio >= 1.0
                    else "Consider splitting into parallel sessions"
                })
        return sorted(predictions, key=lambda x: x["projected_ratio"], reverse=True)

    # ── Timetable Optimization ──

    def optimize_timetable(self, institution_id: str,
                           current_schedule: List[Dict],
                           classroom_pool: List[Dict]) -> Dict[str, Any]:
        """Generate timetable optimization recommendations."""
        conflicts = self._detect_scheduling_conflicts(current_schedule)
        consolidation_ops = self._find_consolidation_opportunities(
            current_schedule, classroom_pool
        )
        return {
            "institution_id": institution_id,
            "conflicts_detected": len(conflicts),
            "consolidation_opportunities": len(consolidation_ops),
            "conflicts": conflicts[:10],
            "consolidation_recommendations": consolidation_ops[:10],
            "generated_at": datetime.utcnow().isoformat()
        }

    @staticmethod
    def _detect_scheduling_conflicts(schedule: List[Dict]) -> List[Dict]:
        """Detect overlapping session assignments for same room."""
        conflicts = []
        for i, a in enumerate(schedule):
            for b in schedule[i + 1:]:
                if a.get("classroom_id") == b.get("classroom_id"):
                    if _times_overlap(a.get("start_time"), a.get("end_time"),
                                      b.get("start_time"), b.get("end_time")):
                        conflicts.append({
                            "classroom_id": a["classroom_id"],
                            "session_a": a.get("name", ""),
                            "session_b": b.get("name", ""),
                            "time_conflict": f"{a.get('start_time')} vs {b.get('start_time')}"
                        })
        return conflicts

    @staticmethod
    def _find_consolidation_opportunities(schedule: List[Dict],
                                          classrooms: List[Dict]) -> List[Dict]:
        """Find sessions that could be consolidated into fewer rooms."""
        by_time = defaultdict(list)
        for s in schedule:
            time_key = f"{s.get('start_time')}-{s.get('end_time')}"
            by_time[time_key].append(s)

        opportunities = []
        for time_key, sessions in by_time.items():
            if len(sessions) > 1:
                total_expected = sum(
                    s.get("expected_attendance", 0) for s in sessions
                )
                suitable = [
                    c for c in classrooms
                    if c.get("capacity", 0) >= total_expected
                ]
                if suitable:
                    best = min(suitable, key=lambda c: c["capacity"])
                    opportunities.append({
                        "time_slot": time_key,
                        "sessions_count": len(sessions),
                        "total_expected_attendance": total_expected,
                        "recommended_classroom": best.get("name", ""),
                        "capacity": best.get("capacity", 0),
                        "potential_savings": f"Consolidate {len(sessions)} sessions"
                    })
        return opportunities

    def cleanup(self) -> None:
        self._classroom_cache.clear()
        logger.info("SmartClassroomIntelligence cleaned up")


def _times_overlap(start_a, end_a, start_b, end_b) -> bool:
    if not all([start_a, end_a, start_b, end_b]):
        return False
    return start_a < end_b and start_b < end_a
