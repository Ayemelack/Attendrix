"""Participation & Engagement Intelligence.

Classifies passive vs. active participation, generates engagement scores,
and provides lecturer effectiveness analytics from attendance data.
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from collections import defaultdict
from statistics import mean

from .models import EngagementScore, EngagementType
from .registry import registry, InnovationEvent

logger = logging.getLogger(__name__)


class ParticipationIntelligence:
    """Analyzes engagement levels from attendance patterns.

    Distinguishes between:
    - Active participation (consistent full-duration attendance)
    - Passive attendance (present but minimal engagement)
    - Disengaged (present but erratic/nominal)
    - Absent
    """

    def __init__(self):
        self._firebase = None
        self._repos = None
        self._session_cache: Dict[str, Dict] = {}
        self._config = {
            "active_threshold_minutes": 30,
            "passive_threshold_minutes": 10,
            "engagement_window": 7,          # days
            "interaction_density_window": 5,  # minutes
        }

    def initialize(self, firebase_service=None, repositories: dict = None) -> None:
        self._firebase = firebase_service
        self._repos = repositories or {}
        registry.subscribe(InnovationEvent.ATTENDANCE_MARKED, self._on_attendance)
        registry.subscribe(InnovationEvent.SESSION_ENDED, self._on_session_end)
        logger.info("ParticipationIntelligence initialized")

    def _on_attendance(self, data: dict) -> None:
        session_id = data.get("session_id")
        if session_id:
            self._session_cache.pop(session_id, None)

    def _on_session_end(self, data: dict) -> None:
        session_id = data.get("session_id")
        if session_id:
            self._session_cache.pop(session_id, None)

    # ── Engagement Classification ──

    def classify_engagement(self, student_id: str, session_id: str,
                            attendance_records: List[Dict]) -> EngagementScore:
        """Classify a student's engagement level for a session."""
        if not attendance_records:
            return EngagementScore(
                student_id=student_id,
                session_id=session_id,
                engagement_type=EngagementType.ABSENT,
                participation_score=0.0,
                attendance_density=0.0,
                interaction_frequency=0.0,
                period="session"
            )

        sorted_recs = sorted(
            attendance_records,
            key=lambda r: self._parse_dt(r.get("timestamp", ""))
        )
        duration = self._calculate_duration(sorted_recs)
        density = self._calculate_density(sorted_recs)
        interaction_freq = self._calculate_interaction_frequency(sorted_recs)
        participation_score = self._compute_participation_score(
            duration, density, interaction_freq
        )
        engagement_type = self._classify(participation_score, density)

        return EngagementScore(
            student_id=student_id,
            session_id=session_id,
            engagement_type=engagement_type,
            participation_score=round(participation_score, 4),
            attendance_density=round(density, 4),
            interaction_frequency=round(interaction_freq, 4),
            period="session",
            timestamp=datetime.utcnow()
        )

    def _calculate_duration(self, records: List[Dict]) -> float:
        if len(records) < 2:
            return 0.0
        first = self._parse_dt(records[0].get("timestamp", ""))
        last = self._parse_dt(records[-1].get("timestamp", ""))
        return (last - first).total_seconds() / 60.0

    def _calculate_density(self, records: List[Dict]) -> float:
        """Temporal density: how evenly distributed attendance is within session."""
        if len(records) < 3:
            return 0.0
        timestamps = [
            self._parse_dt(r.get("timestamp", "")).timestamp()
            for r in records
        ]
        if len(timestamps) < 2:
            return 0.0
        intervals = [
            timestamps[i + 1] - timestamps[i]
            for i in range(len(timestamps) - 1)
        ]
        if not intervals:
            return 0.0
        cv = stdev(intervals) / mean(intervals) if mean(intervals) > 0 else 0.0
        return max(0.0, 1.0 - min(cv, 1.0))

    def _calculate_interaction_frequency(self, records: List[Dict]) -> float:
        """Normalized interaction frequency within the session."""
        if len(records) < 2:
            return 0.0
        duration_min = self._calculate_duration(records)
        if duration_min <= 0:
            return 0.0
        raw_freq = len(records) / duration_min
        return min(1.0, raw_freq / self._config["interaction_density_window"])

    def _compute_participation_score(self, duration: float,
                                     density: float,
                                     interaction: float) -> float:
        return (duration * 0.3 + density * 0.35 + interaction * 0.35) / 100.0

    def _classify(self, score: float, density: float) -> EngagementType:
        if score > 0.7 and density > 0.6:
            return EngagementType.ACTIVE
        if score > 0.3:
            return EngagementType.PASSIVE
        if score > 0.1:
            return EngagementType.DISENGAGED
        return EngagementType.ABSENT

    # ── Lecturer Effectiveness ──

    def lecturer_effectiveness_report(self, lecturer_id: str,
                                      session_records: List[Dict]) -> Dict[str, Any]:
        """Aggregate engagement metrics into lecturer effectiveness report."""
        if not session_records:
            return {"lecturer_id": lecturer_id, "sessions_analyzed": 0}

        engagement_scores = []
        for session in session_records:
            students = session.get("attendance_records", [])
            if students:
                avg = mean(
                    self._compute_participation_score(
                        self._calculate_duration(students),
                        self._calculate_density(students),
                        self._calculate_interaction_frequency(students)
                    ) for _ in [1]
                )
                engagement_scores.append(avg)

        avg_engagement = mean(engagement_scores) if engagement_scores else 0.0
        active_ratio = sum(1 for s in engagement_scores if s > 0.7) / len(engagement_scores) \
            if engagement_scores else 0.0

        return {
            "lecturer_id": lecturer_id,
            "sessions_analyzed": len(session_records),
            "average_engagement_score": round(avg_engagement, 4),
            "active_participation_ratio": round(active_ratio, 4),
            "effectiveness_rating": self._rating_label(avg_engagement),
            "recommendations": self._generate_effectiveness_tips(avg_engagement)
        }

    @staticmethod
    def _rating_label(score: float) -> str:
        if score > 0.7:
            return "highly_effective"
        if score > 0.5:
            return "effective"
        if score > 0.3:
            return "moderate"
        return "needs_improvement"

    @staticmethod
    def _generate_effectiveness_tips(score: float) -> List[str]:
        if score > 0.7:
            return ["Maintain current engagement strategies"]
        if score > 0.5:
            return ["Consider more interactive elements",
                    "Increase real-time polling or Q&A sessions"]
        if score > 0.3:
            return ["Introduce group activities",
                    "Use attendance data to identify disengaged students",
                    "Consider shorter lecture segments with breaks"]
        return ["Schedule mid-session engagement checks",
                "Implement active learning techniques",
                "Use technology-enhanced interaction tools"]

    # ── Participation Heatmap ──

    def generate_heatmap(self, institution_id: str,
                         attendance_data: List[Dict],
                         group_by: str = "department") -> Dict[str, Any]:
        """Generate participation heatmap grouped by department/time/location."""
        groups = defaultdict(list)
        for record in attendance_data:
            key = record.get(group_by, "unknown")
            groups[key].append(record)

        heatmap = {}
        for group, records in groups.items():
            scores = []
            for r in records:
                student_records = r.get("attendance_records", [])
                if student_records:
                    score = self._compute_participation_score(
                        self._calculate_duration(student_records),
                        self._calculate_density(student_records),
                        self._calculate_interaction_frequency(student_records)
                    )
                    scores.append(score)
            if scores:
                heatmap[group] = {
                    "average_engagement": round(mean(scores), 4),
                    "student_count": len(scores),
                    "active_count": sum(1 for s in scores if s > 0.7),
                    "disengaged_count": sum(1 for s in scores if s < 0.3),
                }

        return {
            "institution_id": institution_id,
            "group_by": group_by,
            "heatmap": heatmap,
            "generated_at": datetime.utcnow().isoformat()
        }

    # ── Silent Student Detection ──

    def detect_silent_students(self, institution_id: str,
                               all_engagement_scores: List[EngagementScore],
                               threshold: float = 0.2) -> List[Dict[str, Any]]:
        """Identify students with persistently low engagement."""
        by_student = defaultdict(list)
        for score in all_engagement_scores:
            by_student[score.student_id].append(score)

        silent_students = []
        for student_id, scores in by_student.items():
            avg = mean(s.participation_score for s in scores)
            if avg < threshold:
                silent_students.append({
                    "student_id": student_id,
                    "average_engagement": round(avg, 4),
                    "sessions_attended": len(scores),
                    "classification": "silent_disengaged"
                })

        return sorted(silent_students, key=lambda s: s["average_engagement"])

    @staticmethod
    def _parse_dt(ts) -> datetime:
        if isinstance(ts, datetime):
            return ts
        try:
            return datetime.fromisoformat(ts) if isinstance(ts, str) else datetime.min
        except (ValueError, TypeError):
            return datetime.min

    def cleanup(self) -> None:
        self._session_cache.clear()
        logger.info("ParticipationIntelligence cleaned up")


# Local stdev import for density calculation
def stdev(values):
    from statistics import stdev as _stdev
    return _stdev(values) if len(values) > 1 else 0.0
