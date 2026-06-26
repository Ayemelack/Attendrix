"""Smart Attendance Reputation System.

Attendance reliability scores, trust scoring, academic consistency analytics,
lecturer punctuality intelligence, and departmental discipline rankings.
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from collections import defaultdict
from statistics import mean

from .models import ReputationScore, RiskLevel
from .registry import registry, InnovationEvent

logger = logging.getLogger(__name__)


class ReputationSystem:
    """Multi-dimensional reputation scoring for attendance ecosystem.

    Scores computed for:
    - Students: attendance reliability, consistency, trust
    - Lecturers: punctuality, session management, engagement
    - Departments: overall discipline, ranking
    """

    def __init__(self):
        self._firebase = None
        self._repos = None
        self._scores: Dict[str, ReputationScore] = {}
        self._config = {
            "reliability_window_days": 30,
            "consistency_weight": 0.4,
            "reliability_weight": 0.35,
            "trust_weight": 0.25,
            "score_decay_days": 60,
            "top_performer_threshold": 0.9,
        }

    def initialize(self, firebase_service=None, repositories: dict = None) -> None:
        self._firebase = firebase_service
        self._repos = repositories or {}
        registry.subscribe(InnovationEvent.ATTENDANCE_MARKED, self._on_attendance)
        logger.info("ReputationSystem initialized")

    def _on_attendance(self, data: dict) -> None:
        student_id = data.get("student_id")
        if student_id and student_id in self._scores:
            del self._scores[student_id]

    # ── Student Reputation ──

    def compute_student_reputation(self, student_id: str,
                                    institution_id: str,
                                    attendance_history: List[Dict]) -> ReputationScore:
        """Compute comprehensive reputation score for a student."""
        cache_key = f"student:{student_id}"
        if cache_key in self._scores:
            return self._scores[cache_key]

        if not attendance_history:
            score = ReputationScore(
                entity_id=student_id,
                entity_type="student",
                institution_id=institution_id,
                reliability_score=0.5,
                consistency_score=0.5,
                trust_score=0.5,
                ranking=None,
            )
            self._scores[cache_key] = score
            return score

        reliability = self._compute_reliability(attendance_history)
        consistency = self._compute_consistency(attendance_history)
        trust = self._compute_trust(attendance_history)

        reputation = ReputationScore(
            entity_id=student_id,
            entity_type="student",
            institution_id=institution_id,
            reliability_score=round(reliability, 4),
            consistency_score=round(consistency, 4),
            trust_score=round(trust, 4),
            last_updated=datetime.utcnow(),
        )
        self._scores[cache_key] = reputation
        return reputation

    def _compute_reliability(self, history: List[Dict]) -> float:
        """Reliability: attendance rate weighted by recency."""
        if not history:
            return 0.5
        sorted_recs = sorted(
            history,
            key=lambda r: self._parse_dt(r.get("timestamp", "")),
            reverse=True
        )
        weighted_sum = 0.0
        total_weight = 0.0
        now = datetime.utcnow()

        for i, rec in enumerate(sorted_recs[:100]):
            ts = self._parse_dt(rec.get("timestamp", ""))
            days_ago = max(0, (now - ts).days)
            weight = max(0.1, 1.0 - days_ago / self._config["reliability_window_days"])
            present = 1.0 if rec.get("present", False) else 0.0
            weighted_sum += present * weight
            total_weight += weight

        return weighted_sum / total_weight if total_weight > 0 else 0.5

    def _compute_consistency(self, history: List[Dict]) -> float:
        """Consistency: low variance in attendance pattern."""
        if len(history) < 5:
            return 0.5
        sorted_recs = sorted(
            history,
            key=lambda r: self._parse_dt(r.get("timestamp", ""))
        )
        attendance_vector = [
            1.0 if r.get("present", False) else 0.0 for r in sorted_recs
        ]
        from statistics import stdev
        try:
            std = stdev(attendance_vector)
            return max(0.0, 1.0 - std)
        except (ValueError, ZeroDivisionError):
            return 0.5

    def _compute_trust(self, history: List[Dict]) -> float:
        """Trust: device consistency + location consistency + punctuality."""
        if not history:
            return 0.5
        devices = len(set(
            r.get("device_id") or r.get("device", "") for r in history
        ))
        device_trust = max(0.0, 1.0 - (devices - 1) * 0.15)

        locations = len(set(
            r.get("location") or r.get("classroom", "") for r in history
        ))

        anomalies = sum(
            1 for r in history
            if r.get("anomaly_flag", False) or r.get("flagged", False)
        )
        anomaly_penalty = min(0.5, anomalies * 0.1)

        return max(0.0, min(1.0, device_trust - anomaly_penalty))

    # ── Lecturer Punctuality ──

    def compute_lecturer_reputation(self, lecturer_id: str,
                                     institution_id: str,
                                     session_history: List[Dict]) -> ReputationScore:
        """Compute reputation score for a lecturer based on punctuality & session quality."""
        cache_key = f"lecturer:{lecturer_id}"
        if cache_key in self._scores:
            return self._scores[cache_key]

        if not session_history:
            score = ReputationScore(
                entity_id=lecturer_id,
                entity_type="lecturer",
                institution_id=institution_id,
                reliability_score=0.5,
                consistency_score=0.5,
                trust_score=0.5,
            )
            self._scores[cache_key] = score
            return score

        # Punctuality: session started on time
        punctuality_scores = []
        for session in session_history:
            scheduled = self._parse_dt(session.get("scheduled_start", ""))
            actual = self._parse_dt(session.get("actual_start", ""))
            if scheduled and actual:
                delay = (actual - scheduled).total_seconds() / 60
                punctuality_scores.append(max(0.0, 1.0 - delay / 15.0))

        reliability = mean(punctuality_scores) if punctuality_scores else 0.5

        # Consistency: regular session scheduling
        start_times = [
            self._parse_dt(s.get("scheduled_start", "")).hour
            for s in session_history
            if s.get("scheduled_start")
        ]
        if len(start_times) >= 3:
            var = len(set(start_times))
            consistency = max(0.0, 1.0 - (var - 1) * 0.1)
        else:
            consistency = 0.5

        # Trust: session completion rate
        completed = sum(
            1 for s in session_history
            if s.get("status") in ("completed", "active")
        )
        trust = completed / len(session_history) if session_history else 0.5

        score = ReputationScore(
            entity_id=lecturer_id,
            entity_type="lecturer",
            institution_id=institution_id,
            reliability_score=round(reliability, 4),
            consistency_score=round(consistency, 4),
            trust_score=round(trust, 4),
            last_updated=datetime.utcnow(),
        )
        self._scores[cache_key] = score
        return score

    # ── Department Ranking ──

    def rank_departments(self, institution_id: str,
                          student_scores: List[ReputationScore]) -> List[Dict]:
        """Rank departments by overall attendance discipline."""
        by_dept = defaultdict(list)
        for score in student_scores:
            dept = score.entity_id.split("_")[1] if "_" in score.entity_id else "unknown"
            by_dept[dept].append(score)

        rankings = []
        for dept, scores in by_dept.items():
            avg_reliability = mean(s.reliability_score for s in scores)
            rankings.append({
                "department": dept,
                "average_reliability": round(avg_reliability, 4),
                "student_count": len(scores),
                "composite_score": round(avg_reliability, 4),
            })

        rankings.sort(key=lambda r: r["composite_score"], reverse=True)
        for i, rank in enumerate(rankings, 1):
            rank["rank"] = i
            rank["tier"] = "top" if i <= max(1, len(rankings) // 3) else (
                "middle" if i <= max(1, len(rankings) * 2 // 3) else "bottom"
            )

        return rankings

    # ── Bulk Operations ──

    def get_reputation_summary(self, institution_id: str,
                                scores: List[ReputationScore]) -> Dict[str, Any]:
        """Get summary statistics for reputation scores."""
        if not scores:
            return {"institution_id": institution_id, "status": "no_data"}

        reliabilities = [s.reliability_score for s in scores]
        consistencies = [s.consistency_score for s in scores]
        trusts = [s.trust_score for s in scores]

        return {
            "institution_id": institution_id,
            "entity_count": len(scores),
            "average_reliability": round(mean(reliabilities), 4),
            "average_consistency": round(mean(consistencies), 4),
            "average_trust": round(mean(trusts), 4),
            "composite_reputation": round(
                (mean(reliabilities) * self._config["reliability_weight"] +
                 mean(consistencies) * self._config["consistency_weight"] +
                 mean(trusts) * self._config["trust_weight"]), 4
            ),
            "top_performers": sum(
                1 for s in scores
                if s.reliability_score > self._config["top_performer_threshold"]
            ),
            "needs_improvement": sum(
                1 for s in scores
                if s.reliability_score < 0.5
            ),
            "distribution": {
                "excellent": round(
                    sum(1 for s in scores if s.reliability_score >= 0.9) / len(scores), 4
                ),
                "good": round(
                    sum(1 for s in scores if 0.75 <= s.reliability_score < 0.9) / len(scores), 4
                ),
                "fair": round(
                    sum(1 for s in scores if 0.5 <= s.reliability_score < 0.75) / len(scores), 4
                ),
                "poor": round(
                    sum(1 for s in scores if s.reliability_score < 0.5) / len(scores), 4
                ),
            }
        }

    @staticmethod
    def _parse_dt(ts) -> datetime:
        if isinstance(ts, datetime):
            return ts
        if isinstance(ts, str):
            try:
                return datetime.fromisoformat(ts)
            except (ValueError, TypeError):
                pass
        return datetime.min

    def cleanup(self) -> None:
        self._scores.clear()
        logger.info("ReputationSystem cleaned up")
