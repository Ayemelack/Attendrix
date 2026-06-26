"""AI Administrative Automation.

Automates report generation, accreditation documentation, compliance auditing,
anomaly explanations, and dispute resolution — all driven by existing
attendance data without modifying core workflows.
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from collections import defaultdict
from statistics import mean

from .models import RiskLevel, ReputationScore
from .registry import registry, InnovationEvent

logger = logging.getLogger(__name__)


class AdminAutomation:
    """AI-powered administrative automation suite.

    Capabilities:
    - Automatic report generation (PDF/CSV structured data)
    - Accreditation document preparation
    - AI-generated institutional summaries
    - Attendance anomaly explanations (plain English)
    - Automated compliance auditing
    - Smart attendance dispute resolution
    """

    def __init__(self):
        self._firebase = None
        self._repos = None
        self._report_cache: Dict[str, Dict] = {}
        self._config = {
            "report_retention_days": 90,
            "compliance_threshold": 0.75,
            "max_dispute_auto_resolve_days": 7,
        }

    def initialize(self, firebase_service=None, repositories: dict = None) -> None:
        self._firebase = firebase_service
        self._repos = repositories or {}
        logger.info("AdminAutomation initialized")

    # ── Report Generation ──

    def generate_attendance_report(self, institution_id: str,
                                    period_start: str,
                                    period_end: str,
                                    data: List[Dict]) -> Dict[str, Any]:
        """Generate a comprehensive attendance report."""
        if not data:
            return {
                "institution_id": institution_id,
                "period": f"{period_start} to {period_end}",
                "status": "no_data"
            }

        total_sessions = len(set(
            r.get("session_id", "") for r in data
        ))
        unique_students = len(set(
            r.get("student_id", "") for r in data
        ))
        attendance_rates = [
            1.0 if r.get("present", False) else 0.0 for r in data
        ]
        avg_rate = mean(attendance_rates) if attendance_rates else 0.0

        by_department = defaultdict(list)
        for r in data:
            dept = r.get("department", "unknown")
            by_department[dept].append(r)

        dept_summary = {}
        for dept, records in by_department.items():
            dept_rates = [1.0 if r.get("present", False) else 0.0 for r in records]
            dept_summary[dept] = {
                "total_records": len(records),
                "attendance_rate": round(mean(dept_rates), 4) if dept_rates else 0.0,
                "unique_students": len(set(r.get("student_id", "") for r in records)),
            }

        return {
            "institution_id": institution_id,
            "period": f"{period_start} to {period_end}",
            "generated_at": datetime.utcnow().isoformat(),
            "summary": {
                "total_sessions": total_sessions,
                "unique_students": unique_students,
                "total_records": len(data),
                "overall_attendance_rate": round(avg_rate, 4),
                "status": self._report_status(avg_rate),
            },
            "by_department": dept_summary,
            "top_performers": self._top_performers(data, 5),
            "requires_attention": self._needs_attention(data, 5),
            "export_formats": ["json", "csv"]
        }

    @staticmethod
    def _report_status(rate: float) -> str:
        if rate >= 0.9:
            return "excellent"
        if rate >= 0.75:
            return "good"
        if rate >= 0.6:
            return "fair"
        return "needs_improvement"

    @staticmethod
    def _top_performers(data: List[Dict], n: int) -> List[Dict]:
        by_student = defaultdict(list)
        for r in data:
            by_student[r.get("student_id", "")].append(r)
        scores = []
        for sid, records in by_student.items():
            rate = mean(1.0 if r.get("present", False) else 0.0 for r in records)
            scores.append({"student_id": sid, "attendance_rate": round(rate, 4)})
        return sorted(scores, key=lambda x: x["attendance_rate"], reverse=True)[:n]

    @staticmethod
    def _needs_attention(data: List[Dict], n: int) -> List[Dict]:
        by_student = defaultdict(list)
        for r in data:
            by_student[r.get("student_id", "")].append(r)
        scores = []
        for sid, records in by_student.items():
            rate = mean(1.0 if r.get("present", False) else 0.0 for r in records)
            scores.append({"student_id": sid, "attendance_rate": round(rate, 4)})
        return sorted(scores, key=lambda x: x["attendance_rate"])[:n]

    # ── Institutional Summaries ──

    def generate_institutional_summary(self, institution_id: str,
                                        departments: List[Dict],
                                        recent_trends: List[float]) -> Dict[str, Any]:
        """Generate an AI-crafted institutional performance summary."""
        if not departments:
            return {"institution_id": institution_id, "summary": "Insufficient data"}

        dept_count = len(departments)
        total_students = sum(d.get("student_count", 0) for d in departments)
        avg_rate = mean(d.get("attendance_rate", 0) for d in departments) if departments else 0.0

        trend = "improving" if len(recent_trends) > 1 and recent_trends[-1] > recent_trends[0] \
            else "declining" if len(recent_trends) > 1 and recent_trends[-1] < recent_trends[0] \
            else "stable"

        narratives = []
        if avg_rate >= 0.85:
            narratives.append("Overall attendance is strong across the institution.")
        elif avg_rate >= 0.7:
            narratives.append("Attendance is satisfactory with room for improvement.")
        else:
            narratives.append("Attendance requires institutional attention.")

        top_dept = max(departments, key=lambda d: d.get("attendance_rate", 0))
        narratives.append(
            f"Leading department: {top_dept.get('name', 'N/A')} "
            f"({round(top_dept.get('attendance_rate', 0) * 100, 1)}%)."
        )

        return {
            "institution_id": institution_id,
            "generated_at": datetime.utcnow().isoformat(),
            "summary": " ".join(narratives),
            "metrics": {
                "departments": dept_count,
                "total_students": total_students,
                "average_attendance": round(avg_rate, 4),
                "trend": trend,
            },
            "narrative_components": narratives,
            "recommendations": self._generate_summary_recommendations(avg_rate, trend)
        }

    @staticmethod
    def _generate_summary_recommendations(rate: float, trend: str) -> List[str]:
        recs = []
        if rate < 0.7:
            recs.append("Implement institution-wide attendance awareness campaign")
        if trend == "declining":
            recs.append("Investigate recent attendance decline patterns")
        if rate < 0.8:
            recs.append("Identify departments needing targeted intervention")
        if not recs:
            recs.append("Maintain current attendance policies and monitoring")
        return recs

    # ── Anomaly Explanations ──

    def explain_anomaly(self, student_id: str,
                         anomaly_data: Dict) -> Dict[str, Any]:
        """Generate plain-English explanation for attendance anomalies."""
        anomaly_type = anomaly_data.get("type", "unknown")
        severity = anomaly_data.get("severity", "low")
        context = anomaly_data.get("context", {})

        explanations = {
            "sudden_drop": (
                f"Student {student_id} shows a sudden decline in attendance. "
                f"Attendance dropped from {context.get('previous_rate', 'N/A')}% "
                f"to {context.get('current_rate', 'N/A')}% over "
                f"{context.get('window_days', 'recent')} days."
            ),
            "erratic_pattern": (
                f"Student {student_id} exhibits erratic attendance with "
                f"high variability ({context.get('variance', 'N/A')} variance). "
                f"This may indicate scheduling conflicts or disengagement."
            ),
            "device_change": (
                f"Student {student_id} attended from a new device "
                f"({context.get('new_device', 'unknown')}) which differs from "
                f"their habitual device ({context.get('habitual_device', 'unknown')})."
            ),
            "location_mismatch": (
                f"Student {student_id} checked in from an unusual location "
                f"({context.get('location', 'unknown')}) outside their "
                f"typical attendance zone."
            ),
        }

        explanation = explanations.get(
            anomaly_type,
            f"Attendance anomaly detected for {student_id} ({severity} severity)."
        )

        return {
            "student_id": student_id,
            "anomaly_type": anomaly_type,
            "severity": severity,
            "explanation": explanation,
            "confidence": context.get("confidence", 0.8),
            "recommended_action": self._anomaly_action(anomaly_type, severity),
            "generated_at": datetime.utcnow().isoformat()
        }

    @staticmethod
    def _anomaly_action(anomaly_type: str, severity: str) -> str:
        actions = {
            "sudden_drop": "Check with student or review recent circumstances",
            "erratic_pattern": "Review schedule conflicts and provide support",
            "device_change": "Verify new device with student (possible credential sharing)",
            "location_mismatch": "Investigate location discrepancy (possible proxy attendance)",
        }
        return actions.get(anomaly_type, "Monitor and document")

    # ── Compliance Auditing ──

    def audit_compliance(self, institution_id: str,
                          policies: List[Dict],
                          attendance_data: List[Dict]) -> Dict[str, Any]:
        """Automated compliance auditing against institutional policies."""
        results = []
        for policy in policies:
            policy_type = policy.get("type", "")
            threshold = policy.get("threshold", self._config["compliance_threshold"])
            if policy_type == "minimum_attendance":
                compliant = self._check_minimum_attendance(
                    attendance_data, threshold
                )
            elif policy_type == "session_capacity":
                compliant = self._check_session_capacity(
                    attendance_data, policy.get("max_capacity", 0)
                )
            else:
                compliant = {"compliant": True, "note": "Policy type not checked"}

            results.append({
                "policy": policy.get("name", "Unknown"),
                "type": policy_type,
                "compliant": compliant.get("compliant", False),
                "details": compliant.get("details", ""),
                "violations": compliant.get("violations", 0),
            })

        return {
            "institution_id": institution_id,
            "audit_timestamp": datetime.utcnow().isoformat(),
            "total_policies": len(policies),
            "compliant_count": sum(1 for r in results if r["compliant"]),
            "violation_count": sum(1 for r in results if not r["compliant"]),
            "results": results,
            "overall_compliance": round(
                sum(1 for r in results if r["compliant"]) / len(results), 4
            ) if results else 0.0,
        }

    @staticmethod
    def _check_minimum_attendance(data: List[Dict],
                                   threshold: float) -> Dict:
        if not data:
            return {"compliant": True, "details": "No data to audit"}
        by_student = defaultdict(list)
        for r in data:
            by_student[r.get("student_id", "")].append(r)
        violations = 0
        for sid, records in by_student.items():
            rate = mean(1.0 if r.get("present", False) else 0.0 for r in records)
            if rate < threshold:
                violations += 1
        return {
            "compliant": violations == 0,
            "details": f"Students below threshold: {violations}",
            "violations": violations
        }

    @staticmethod
    def _check_session_capacity(data: List[Dict],
                                 max_capacity: int) -> Dict:
        if not data or max_capacity <= 0:
            return {"compliant": True, "details": "Capacity not checked"}
        by_session = defaultdict(list)
        for r in data:
            by_session[r.get("session_id", "")].append(r)
        violations = sum(
            1 for s, recs in by_session.items()
            if len(recs) > max_capacity
        )
        return {
            "compliant": violations == 0,
            "details": f"Over-capacity sessions: {violations}",
            "violations": violations
        }

    # ── Dispute Resolution ──

    def resolve_dispute(self, dispute_data: Dict,
                         attendance_records: List[Dict]) -> Dict[str, Any]:
        """Smart attendance dispute resolution using available evidence."""
        student_id = dispute_data.get("student_id", "")
        session_id = dispute_data.get("session_id", "")
        claim = dispute_data.get("claim", "")
        recorded_status = dispute_data.get("recorded_status", "absent")

        evidence = [
            r for r in attendance_records
            if r.get("student_id") == student_id
            and r.get("session_id") == session_id
        ]

        if not evidence:
            return {
                "dispute_id": f"DSP-{student_id}-{session_id}",
                "resolution": "insufficient_evidence",
                "explanation": "No attendance records found for this session.",
                "auto_resolvable": False,
                "requires_human": True,
                "confidence": 0.0
            }

        # Analyze evidence
        checkin_count = len(evidence)
        has_biometric = any(
            r.get("method") in ("biometric", "face", "fingerprint") for r in evidence
        )
        has_peer_context = any(
            r.get("peer_count", 0) > 0 for r in evidence
        )

        # Determine resolution
        auto_resolvable = checkin_count >= 2 or has_biometric
        confidence = min(1.0, (checkin_count * 0.3 + (0.3 if has_biometric else 0) +
                               (0.2 if has_peer_context else 0)))

        if auto_resolvable and confidence > 0.6:
            resolution = "resolved_in_favor"
            explanation = (
                f"Multiple attendance markers found ({checkin_count} check-ins). "
                + ("Biometric verification present. " if has_biometric else "")
                + "Dispute resolved in favor of student."
            )
        else:
            resolution = "requires_review"
            explanation = (
                f"Limited evidence ({checkin_count} check-in(s)). "
                "Dispute requires human review."
            )

        return {
            "dispute_id": f"DSP-{student_id}-{session_id}",
            "resolution": resolution,
            "explanation": explanation,
            "auto_resolvable": auto_resolvable,
            "requires_human": not auto_resolvable,
            "confidence": round(confidence, 4),
            "evidence_summary": {
                "checkin_count": checkin_count,
                "biometric_present": has_biometric,
                "peer_context": has_peer_context,
            }
        }

    def cleanup(self) -> None:
        self._report_cache.clear()
        logger.info("AdminAutomation cleaned up")
