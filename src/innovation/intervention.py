"""Smart Academic Intervention System.

Automates intervention workflows: tiered warning generation, dean escalation,
counselor assignment, and adaptive recommendations — all driven by risk
intelligence from the Academic Risk Engine.
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from collections import defaultdict

from .models import InterventionRecord, InterventionTier, RiskLevel
from .registry import registry, InnovationEvent

logger = logging.getLogger(__name__)


class SmartIntervention:
    """Automated academic intervention system.

    Tiered intervention model:
    - Tier 1: Automated warning (no human required)
    - Tier 2: Counselor assigned (moderate risk)
    - Tier 3: Dean escalation (high risk)
    - Tier 4: Emergency intervention (critical risk)

    Trigger sources:
    - Risk profile changes from AcademicRiskEngine
    - Attendance threshold breaches
    - Engagement collapse detection
    - Manual trigger by authorized staff
    """

    def __init__(self):
        self._firebase = None
        self._repos = None
        self._interventions: Dict[str, List[InterventionRecord]] = defaultdict(list)
        self._config = {
            "auto_warn_on_absence_streak": 5,
            "counselor_assign_threshold": RiskLevel.HIGH,
            "dean_escalate_threshold": RiskLevel.CRITICAL,
            "max_active_interventions": 3,
            "cooldown_days": 14,
            "parental_notification": False,
        }

    def initialize(self, firebase_service=None, repositories: dict = None) -> None:
        self._firebase = firebase_service
        self._repos = repositories or {}
        registry.subscribe(InnovationEvent.RISK_THRESHOLD_CROSSED, self._on_risk_event)
        logger.info("SmartIntervention initialized")

    def _on_risk_event(self, data: dict) -> None:
        risk_level = data.get("risk_level")
        student_id = data.get("student_id")
        if risk_level and student_id:
            level = RiskLevel(risk_level) if isinstance(risk_level, str) else risk_level
            self._evaluate_intervention(student_id, data.get("institution_id", ""), level)

    # ── Intervention Evaluation ──

    def _evaluate_intervention(self, student_id: str,
                                institution_id: str,
                                risk_level: RiskLevel) -> Optional[InterventionRecord]:
        """Evaluate and generate intervention based on risk level."""
        if self._has_active(student_id):
            logger.info(f"Active intervention exists for {student_id}, skipping")
            return None

        if self._in_cooldown(student_id, institution_id):
            logger.info(f"{student_id} in intervention cooldown, skipping")
            return None

        tier = self._determine_tier(risk_level)
        if tier is None:
            return None

        intervention = InterventionRecord(
            student_id=student_id,
            institution_id=institution_id,
            tier=tier,
            trigger_reason=f"Risk level escalated to {risk_level.value}",
            status="pending",
            auto_generated=True,
            created_at=datetime.utcnow(),
        )

        self._assign_intervention(tier, intervention)
        self._interventions[student_id].append(intervention)

        intervention_data = {
            "student_id": student_id,
            "tier": tier.value,
            "status": intervention.status,
            "intervention_id": f"INT-{student_id}-{len(self._interventions[student_id])}"
        }
        registry.emit(InnovationEvent.INTERVENTION_TRIGGERED, intervention_data)
        logger.info(f"Intervention triggered for {student_id}: tier={tier.value}")
        return intervention

    def _determine_tier(self, risk_level: RiskLevel) -> Optional[InterventionTier]:
        mapping = {
            RiskLevel.CRITICAL: InterventionTier.TIER_4_EMERGENCY,
            RiskLevel.HIGH: InterventionTier.TIER_3_DEAN,
            RiskLevel.MEDIUM: InterventionTier.TIER_2_COUNSELOR,
            RiskLevel.LOW: InterventionTier.TIER_1_AUTOMATED,
            RiskLevel.NORMAL: None,
        }
        return mapping.get(risk_level)

    def _has_active(self, student_id: str) -> bool:
        records = self._interventions.get(student_id, [])
        return any(r.status in ("pending", "active") for r in records)

    def _in_cooldown(self, student_id: str, institution_id: str) -> bool:
        records = self._interventions.get(student_id, [])
        if not records:
            return False
        latest = max(
            (r for r in records if r.created_at),
            key=lambda r: r.created_at,
            default=None
        )
        if not latest or not latest.created_at:
            return False
        return (datetime.utcnow() - latest.created_at) < timedelta(
            days=self._config["cooldown_days"]
        )

    @staticmethod
    def _assign_intervention(tier: InterventionTier,
                              record: InterventionRecord) -> None:
        """Assign appropriate handler based on tier."""
        if tier == InterventionTier.TIER_1_AUTOMATED:
            record.status = "active"  # Auto-send warning, no human needed
            record.assigned_to = "system"
        elif tier == InterventionTier.TIER_2_COUNSELOR:
            record.status = "pending"    # Awaiting counselor assignment
            record.assigned_to = "counselor_pool"
            record.trigger_reason += ". Counselor intervention recommended."
        elif tier == InterventionTier.TIER_3_DEAN:
            record.status = "pending"
            record.assigned_to = "dean_office"
            record.trigger_reason += ". Dean escalation required."
        elif tier == InterventionTier.TIER_4_EMERGENCY:
            record.status = "active"
            record.assigned_to = "emergency_response"
            record.trigger_reason += ". Emergency intervention initiated."

    # ── Manual Intervention ──

    def create_intervention(self, student_id: str, institution_id: str,
                            tier: InterventionTier, reason: str,
                            assigned_to: str = None) -> InterventionRecord:
        """Manually create an intervention (for authorized staff)."""
        record = InterventionRecord(
            student_id=student_id,
            institution_id=institution_id,
            tier=tier,
            trigger_reason=reason,
            assigned_to=assigned_to,
            status="active",
            auto_generated=False,
            created_at=datetime.utcnow(),
        )
        self._interventions[student_id].append(record)
        registry.emit(InnovationEvent.INTERVENTION_TRIGGERED, {
            "student_id": student_id,
            "tier": tier.value,
            "status": record.status,
            "manual": True
        })
        return record

    # ── Intervention Workflow ──

    def resolve_intervention(self, student_id: str,
                             intervention_idx: int = -1,
                             resolution_note: str = "") -> bool:
        """Mark an intervention as resolved."""
        records = self._interventions.get(student_id, [])
        if not records:
            return False
        record = records[intervention_idx]
        record.status = "resolved"
        record.resolved_at = datetime.utcnow()
        if resolution_note:
            record.notes.append({
                "timestamp": datetime.utcnow().isoformat(),
                "note": resolution_note,
                "type": "resolution"
            })
        return True

    def escalate_intervention(self, student_id: str,
                              intervention_idx: int = -1) -> bool:
        """Escalate an intervention to the next tier."""
        records = self._interventions.get(student_id, [])
        if not records:
            return False
        record = records[intervention_idx]
        tier_order = list(InterventionTier)
        current_idx = tier_order.index(record.tier)
        if current_idx < len(tier_order) - 1:
            record.tier = tier_order[current_idx + 1]
            record.status = "escalated"
            self._assign_intervention(record.tier, record)
            record.notes.append({
                "timestamp": datetime.utcnow().isoformat(),
                "note": f"Escalated to {record.tier.value}",
                "type": "escalation"
            })
            return True
        return False

    def add_intervention_note(self, student_id: str, note: str,
                              note_type: str = "general",
                              intervention_idx: int = -1) -> bool:
        """Add a note to an intervention record."""
        records = self._interventions.get(student_id, [])
        if not records:
            return False
        record = records[intervention_idx]
        record.notes.append({
            "timestamp": datetime.utcnow().isoformat(),
            "note": note,
            "type": note_type
        })
        return True

    # ── Parental Notification ──

    def generate_notification(self, student_id: str,
                               intervention: InterventionRecord) -> Dict[str, Any]:
        """Generate notification content for parent/guardian."""
        templates = {
            InterventionTier.TIER_1_AUTOMATED: (
                "Attendance notice for {student_id}: "
                "Your ward has missed {count} consecutive sessions. "
                "Please encourage regular attendance."
            ),
            InterventionTier.TIER_2_COUNSELOR: (
                "Academic concern for {student_id}: "
                "Your ward has been identified for academic counseling due to "
                "attendance patterns. A counselor will be in contact."
            ),
            InterventionTier.TIER_3_DEAN: (
                "Academic alert for {student_id}: "
                "This matter has been escalated to the Dean's office "
                "regarding attendance concerns requiring immediate attention."
            ),
            InterventionTier.TIER_4_EMERGENCY: (
                "URGENT: Academic emergency for {student_id}: "
                "Your ward's attendance has reached a critical threshold. "
                "Please contact the administration immediately."
            ),
        }
        msg = templates.get(
            intervention.tier,
            "Attendance notification for {student_id}"
        ).format(student_id=student_id, count=self._config["auto_warn_on_absence_streak"])

        return {
            "student_id": student_id,
            "tier": intervention.tier.value,
            "message": msg,
            "priority": "high" if intervention.tier in (
                InterventionTier.TIER_3_DEAN, InterventionTier.TIER_4_EMERGENCY
            ) else "normal",
            "channels": ["email", "sms"] if intervention.tier in (
                InterventionTier.TIER_3_DEAN, InterventionTier.TIER_4_EMERGENCY
            ) else ["email"],
            "generated_at": datetime.utcnow().isoformat()
        }

    def get_student_interventions(self, student_id: str) -> List[Dict]:
        """Get all interventions for a student."""
        records = self._interventions.get(student_id, [])
        return [
            {
                "tier": r.tier.value,
                "status": r.status,
                "trigger_reason": r.trigger_reason,
                "assigned_to": r.assigned_to,
                "auto_generated": r.auto_generated,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "resolved_at": r.resolved_at.isoformat() if r.resolved_at else None,
                "notes": r.notes[-3:] if r.notes else [],
            }
            for r in records
        ]

    def get_pending_interventions(self, institution_id: str) -> List[Dict]:
        """Get all pending interventions for an institution."""
        pending = []
        for student_id, records in self._interventions.items():
            for r in records:
                if r.institution_id == institution_id and r.status in ("pending", "active"):
                    pending.append({
                        "student_id": student_id,
                        "tier": r.tier.value,
                        "status": r.status,
                        "trigger_reason": r.trigger_reason,
                        "assigned_to": r.assigned_to,
                        "created_at": r.created_at.isoformat() if r.created_at else None,
                    })
        return sorted(pending, key=lambda x: x.get("created_at", ""), reverse=True)

    def cleanup(self) -> None:
        self._interventions.clear()
        logger.info("SmartIntervention cleaned up")
