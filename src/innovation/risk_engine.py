"""Academic Risk Intelligence Engine.

Predicts dropout risk, detects academic disengagement, identifies chronic
absenteeism trends, and generates AI-based intervention recommendations.
All analysis is additive — it reads from existing attendance records without
modifying core attendance workflows.
"""

import logging
from datetime import datetime, timedelta, date
from typing import List, Dict, Any, Optional, Tuple
from collections import defaultdict
from statistics import mean, stdev

from .models import RiskProfile, RiskLevel, InterventionRecord, InterventionTier
from .registry import registry, InnovationEvent

logger = logging.getLogger(__name__)


class AcademicRiskEngine:
    """AI-powered academic risk intelligence engine.

    Analyzes attendance patterns over configurable time windows to detect:
    - Dropout probability (sustained absence + disengagement)
    - Academic disengagement (sudden attendance drop)
    - Chronic absenteeism (cumulative absence patterns)
    - Exam eligibility risk (trajectory-based prediction)
    - Burnout patterns (erratic attendance + declining participation)
    """

    def __init__(self):
        self._firebase = None
        self._repos = None
        self._risk_cache: Dict[str, RiskProfile] = {}
        self._config = {
            "disengagement_window_days": 14,
            "chronic_absence_threshold": 0.3,
            "dropout_lookback_days": 60,
            "risk_refresh_hours": 4,
            "exam_eligibility_min_attendance": 0.75,
            "burnout_attendance_variance_threshold": 0.4,
        }

    def initialize(self, firebase_service=None, repositories: dict = None) -> None:
        self._firebase = firebase_service
        self._repos = repositories or {}
        registry.subscribe(InnovationEvent.ATTENDANCE_MARKED, self._on_attendance_marked)
        logger.info("AcademicRiskEngine initialized")

    def _on_attendance_marked(self, data: dict) -> None:
        student_id = data.get("student_id")
        if student_id and student_id in self._risk_cache:
            del self._risk_cache[student_id]

    # ── Dropout Risk Prediction ──

    def predict_dropout_risk(self, student_id: str, institution_id: str,
                             attendance_history: List[Dict[str, Any]]) -> RiskProfile:
        """Predict dropout probability from attendance trajectory."""
        if not attendance_history:
            return RiskProfile(
                student_id=student_id,
                institution_id=institution_id,
                dropout_probability=0.0,
                disengagement_score=0.0,
                absenteeism_trend="stable",
                risk_level=RiskLevel.NORMAL,
                intervention_recommendation="Insufficient data",
                risk_factors=["no_attendance_history"]
            )

        recent = self._filter_recent(attendance_history,
                                     self._config["dropout_lookback_days"])
        if not recent:
            return self._default_normal(student_id, institution_id)

        absence_rate = self._calculate_absence_rate(recent)
        attendance_trajectory = self._calculate_trajectory(recent)
        disengagement_score = self._calculate_disengagement(recent)
        absenteeism_trend = self._classify_trend(attendance_trajectory)

        dropout_prob = self._compute_dropout_probability(
            absence_rate, attendance_trajectory, disengagement_score
        )
        risk_level = self._classify_risk_level(dropout_prob, disengagement_score)
        interventions = self._generate_recommendations(risk_level, absence_rate)

        risk_factors = self._identify_risk_factors(
            absence_rate, attendance_trajectory, disengagement_score
        )

        profile = RiskProfile(
            student_id=student_id,
            institution_id=institution_id,
            dropout_probability=round(dropout_prob, 4),
            disengagement_score=round(disengagement_score, 4),
            absenteeism_trend=absenteeism_trend,
            risk_level=risk_level,
            intervention_recommendation=interventions,
            risk_factors=risk_factors,
            last_updated=datetime.utcnow()
        )
        self._risk_cache[student_id] = profile
        return profile

    def _filter_recent(self, history: List[Dict], days: int) -> List[Dict]:
        cutoff = datetime.utcnow() - timedelta(days=days)
        return [r for r in history if self._parse_dt(r.get("timestamp", "")) > cutoff]

    def _parse_dt(self, ts) -> datetime:
        if isinstance(ts, datetime):
            return ts
        try:
            return datetime.fromisoformat(ts) if isinstance(ts, str) else datetime.min
        except (ValueError, TypeError):
            return datetime.min

    def _calculate_absence_rate(self, records: List[Dict]) -> float:
        if not records:
            return 0.0
        absences = sum(1 for r in records if not r.get("present", False))
        return absences / len(records)

    def _calculate_trajectory(self, records: List[Dict]) -> List[float]:
        sorted_recs = sorted(records, key=lambda r: self._parse_dt(r.get("timestamp", "")))
        window_size = max(len(sorted_recs) // 5, 3)
        trajectory = []
        for i in range(0, len(sorted_recs), window_size):
            chunk = sorted_recs[i:i + window_size]
            if chunk:
                present = sum(1 for r in chunk if r.get("present", False))
                trajectory.append(present / len(chunk))
        return trajectory

    def _calculate_disengagement(self, records: List[Dict]) -> float:
        if len(records) < 4:
            return 0.0
        sorted_recs = sorted(records, key=lambda r: self._parse_dt(r.get("timestamp", "")))
        mid = len(sorted_recs) // 2
        first_half = sorted_recs[:mid]
        second_half = sorted_recs[mid:]
        if not first_half or not second_half:
            return 0.0
        early_rate = sum(1 for r in first_half if r.get("present", False)) / len(first_half)
        late_rate = sum(1 for r in second_half if r.get("present", False)) / len(second_half)
        return max(0.0, early_rate - late_rate)

    def _classify_trend(self, trajectory: List[float]) -> str:
        if len(trajectory) < 3:
            return "stable"
        recent = trajectory[-3:]
        if all(recent[i] <= recent[i + 1] for i in range(len(recent) - 1)):
            return "improving"
        if all(recent[i] >= recent[i + 1] for i in range(len(recent) - 1)):
            return "worsening"
        return "stable"

    def _compute_dropout_probability(self, absence_rate: float,
                                     trajectory: List[float],
                                     disengagement: float) -> float:
        base = absence_rate * 0.5
        trajectory_factor = 0.0
        if len(trajectory) >= 2 and trajectory[-1] < trajectory[0]:
            trajectory_factor = (trajectory[0] - trajectory[-1]) * 0.3
        disengagement_factor = disengagement * 0.4
        raw = min(1.0, base + trajectory_factor + disengagement_factor)
        return max(0.0, raw - 0.1)  # floor to avoid false positives

    def _classify_risk_level(self, dropout_prob: float,
                             disengagement: float) -> RiskLevel:
        if dropout_prob > 0.7 or disengagement > 0.6:
            return RiskLevel.CRITICAL
        if dropout_prob > 0.5 or disengagement > 0.4:
            return RiskLevel.HIGH
        if dropout_prob > 0.3 or disengagement > 0.25:
            return RiskLevel.MEDIUM
        if dropout_prob > 0.15:
            return RiskLevel.LOW
        return RiskLevel.NORMAL

    def _generate_recommendations(self, risk_level: RiskLevel,
                                  absence_rate: float) -> str:
        recommendations = {
            RiskLevel.CRITICAL: "Immediate intervention required. Assign counselor "
                                "and notify dean. Schedule mandatory meeting within 48 hours.",
            RiskLevel.HIGH: "Proactive intervention recommended. Contact student, "
                            "schedule academic advising session, monitor weekly attendance.",
            RiskLevel.MEDIUM: "Monitor closely. Send automated check-in, review "
                              "attendance weekly, consider peer mentoring program.",
            RiskLevel.LOW: "Routine monitoring. Send periodic engagement reminders.",
            RiskLevel.NORMAL: "No intervention needed at this time.",
        }
        return recommendations.get(risk_level, "No recommendation")

    def _identify_risk_factors(self, absence_rate: float,
                               trajectory: List[float],
                               disengagement: float) -> List[str]:
        factors = []
        if absence_rate > 0.4:
            factors.append("high_absence_rate")
        if disengagement > 0.3:
            factors.append("declining_engagement")
        if len(trajectory) >= 2 and trajectory[-1] < 0.5:
            factors.append("recent_attendance_collapse")
        if absence_rate > 0.6:
            factors.append("chronic_absenteeism")
        return factors or ["within_normal_range"]

    def _default_normal(self, student_id: str, institution_id: str) -> RiskProfile:
        return RiskProfile(
            student_id=student_id,
            institution_id=institution_id,
            dropout_probability=0.0,
            disengagement_score=0.0,
            absenteeism_trend="stable",
            risk_level=RiskLevel.NORMAL,
            intervention_recommendation="Insufficient attendance data",
            risk_factors=["insufficient_data"]
        )

    # ── Cohort Risk Heatmap ──

    def generate_risk_heatmap(self, institution_id: str,
                              student_profiles: List[RiskProfile]) -> Dict[str, Any]:
        """Generate faculty/department risk heatmap from student profiles."""
        if not student_profiles:
            return {"departments": {}, "overall_risk": "normal"}

        by_dept = defaultdict(list)
        for p in student_profiles:
            dept = self._extract_dept(p.student_id)
            by_dept[dept].append(p)

        dept_heatmap = {}
        for dept, profiles in by_dept.items():
            avg_risk = mean(
                [self._risk_level_score(p.risk_level) for p in profiles]
            )
            critical_count = sum(
                1 for p in profiles if p.risk_level == RiskLevel.CRITICAL
            )
            high_count = sum(
                1 for p in profiles if p.risk_level == RiskLevel.HIGH
            )
            dept_heatmap[dept] = {
                "average_risk_score": round(avg_risk, 2),
                "critical_students": critical_count,
                "high_risk_students": high_count,
                "total_students": len(profiles),
                "risk_level": self._score_to_level(avg_risk).value
            }

        overall = mean([h["average_risk_score"] for h in dept_heatmap.values()]) \
            if dept_heatmap else 0.0

        return {
            "departments": dept_heatmap,
            "overall_risk_score": round(overall, 2),
            "overall_risk_level": self._score_to_level(overall).value,
            "generated_at": datetime.utcnow().isoformat()
        }

    @staticmethod
    def _risk_level_score(level: RiskLevel) -> float:
        mapping = {
            RiskLevel.CRITICAL: 1.0,
            RiskLevel.HIGH: 0.75,
            RiskLevel.MEDIUM: 0.5,
            RiskLevel.LOW: 0.25,
            RiskLevel.NORMAL: 0.0,
        }
        return mapping.get(level, 0.0)

    @staticmethod
    def _score_to_level(score: float) -> RiskLevel:
        if score > 0.7:
            return RiskLevel.CRITICAL
        if score > 0.5:
            return RiskLevel.HIGH
        if score > 0.3:
            return RiskLevel.MEDIUM
        if score > 0.1:
            return RiskLevel.LOW
        return RiskLevel.NORMAL

    @staticmethod
    def _extract_dept(student_id: str) -> str:
        parts = student_id.split("_")
        return parts[1] if len(parts) > 1 else "unknown"

    # ── Exam Eligibility Prediction ──

    def predict_exam_eligibility(self, student_id: str,
                                 attendance_records: List[Dict[str, Any]],
                                 course_id: str) -> Dict[str, Any]:
        """Predict whether a student will be exam-eligible based on attendance trajectory."""
        profile = self.predict_dropout_risk(student_id, "all", attendance_records)
        projected = self._project_future_attendance(attendance_records)
        eligible = projected >= self._config["exam_eligibility_min_attendance"]
        return {
            "student_id": student_id,
            "course_id": course_id,
            "current_attendance_rate": round(
                1.0 - self._calculate_absence_rate(attendance_records), 4
            ),
            "projected_attendance_rate": round(projected, 4),
            "exam_eligible": eligible,
            "risk_level": profile.risk_level.value,
            "recommendation": "Eligible" if eligible else (
                "At risk of ineligibility. Recommend intervention."
            )
        }

    def _project_future_attendance(self, records: List[Dict]) -> float:
        if len(records) < 5:
            return 1.0 - self._calculate_absence_rate(records)
        trajectory = self._calculate_trajectory(records)
        if len(trajectory) < 2:
            return 1.0 - self._calculate_absence_rate(records)
        recent_trend = trajectory[-1] - trajectory[-2]
        projected = trajectory[-1] + recent_trend
        return max(0.0, min(1.0, projected))

    # ── Burnout Detection ──

    def detect_burnout_patterns(self, student_id: str,
                                attendance_records: List[Dict]) -> Dict[str, Any]:
        """Detect burnout patterns from erratic attendance and declining duration."""
        if len(attendance_records) < 10:
            return {"burnout_detected": False, "confidence": 0.0}

        sorted_recs = sorted(attendance_records,
                             key=lambda r: self._parse_dt(r.get("timestamp", "")))
        attendance_vector = [
            1.0 if r.get("present", False) else 0.0 for r in sorted_recs
        ]
        variance = stdev(attendance_vector) if len(attendance_vector) > 1 else 0.0
        recent_avg = mean(attendance_vector[-5:]) if len(attendance_vector) >= 5 else 0.0
        early_avg = mean(attendance_vector[:5]) if len(attendance_vector) >= 5 else 1.0
        decline = early_avg - recent_avg

        burnout_prob = min(1.0, (variance * 0.4 + decline * 0.6))
        if "duration" in sorted_recs[-1]:
            durations = [
                r.get("duration", 0) or 0 for r in sorted_recs[-10:]
            ]
            if durations and mean(durations) < 10:
                burnout_prob = min(1.0, burnout_prob + 0.15)

        return {
            "burnout_detected": burnout_prob > 0.5,
            "confidence": round(burnout_prob, 4),
            "attendance_variance": round(variance, 4),
            "attendance_decline": round(decline, 4),
            "risk_level": RiskLevel.CRITICAL.value if burnout_prob > 0.7
            else RiskLevel.HIGH.value if burnout_prob > 0.5
            else RiskLevel.NORMAL.value
        }

    @property
    def config(self) -> Dict:
        return dict(self._config)

    def update_config(self, overrides: Dict) -> None:
        self._config.update(overrides)
        self._risk_cache.clear()
        logger.info(f"AcademicRiskEngine config updated: {overrides}")

    def cleanup(self) -> None:
        self._risk_cache.clear()
        logger.info("AcademicRiskEngine cleaned up")
