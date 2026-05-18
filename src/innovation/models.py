"""Shared data models for Attendrix Innovation Expansion modules."""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from datetime import datetime, date
from enum import Enum


class RiskLevel(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NORMAL = "normal"


class EngagementType(str, Enum):
    ACTIVE = "active"
    PASSIVE = "passive"
    DISENGAGED = "disengaged"
    ABSENT = "absent"


class InterventionTier(str, Enum):
    TIER_1_AUTOMATED = "tier_1_automated"        # Auto-generated warning
    TIER_2_COUNSELOR = "tier_2_counselor"        # Counselor assigned
    TIER_3_DEAN = "tier_3_dean"                  # Dean escalation
    TIER_4_EMERGENCY = "tier_4_emergency"        # Emergency intervention


class TrustAnchor(str, Enum):
    ATTENDANCE_CHAIN = "attendance_chain"
    BLUETOOTH_MESH = "bluetooth_mesh"
    BEHAVIORAL_FINGERPRINT = "behavioral_fingerprint"
    MULTI_FACTOR_CONTEXT = "multi_factor_context"


@dataclass
class RiskProfile:
    student_id: str
    institution_id: str
    dropout_probability: float
    disengagement_score: float
    absenteeism_trend: str          # worsening | stable | improving
    risk_level: RiskLevel
    intervention_recommendation: str
    risk_factors: List[str] = field(default_factory=list)
    last_updated: Optional[datetime] = None


@dataclass
class EngagementScore:
    student_id: str
    session_id: str
    engagement_type: EngagementType
    participation_score: float       # 0.0 - 1.0
    attendance_density: float        # temporal density within session
    interaction_frequency: float     # normalized interaction count
    period: str                      # daily | weekly | monthly
    timestamp: Optional[datetime] = None


@dataclass
class ClassroomIntelligence:
    classroom_id: str
    institution_id: str
    current_occupancy: int
    max_capacity: int
    utilization_rate: float
    peak_hours: List[str] = field(default_factory=list)
    underutilized: bool = False
    overcrowding_risk: str = "normal"   # normal | warning | critical
    seating_density_map: Optional[Dict[str, float]] = None


@dataclass
class BehavioralPattern:
    student_id: str
    institution_id: str
    habitual_checkin_time: Optional[str] = None
    preferred_seating_zone: Optional[str] = None
    typical_duration: Optional[float] = None
    device_consistency: float = 0.0
    location_consistency: float = 0.0
    peer_proximity_score: float = 0.0
    anomaly_score: float = 0.0
    trust_level: RiskLevel = RiskLevel.NORMAL
    pattern_history: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class AuditChainEntry:
    chain_id: str
    previous_hash: str
    merkle_root: str
    attendance_hash: str
    timestamp: datetime
    institution_id: str
    session_id: str
    block_height: int
    verified: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class InterventionRecord:
    student_id: str
    institution_id: str
    tier: InterventionTier
    trigger_reason: str
    assigned_to: Optional[str] = None       # counselor_id or dean_id
    status: str = "pending"                 # pending | active | resolved | escalated
    auto_generated: bool = True
    created_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    notes: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class ReputationScore:
    entity_id: str
    entity_type: str            # student | lecturer | department
    institution_id: str
    reliability_score: float    # 0.0 - 1.0
    consistency_score: float    # 0.0 - 1.0
    trust_score: float          # 0.0 - 1.0
    ranking: Optional[int] = None
    trend: str = "stable"       # improving | stable | declining
    last_updated: Optional[datetime] = None


@dataclass
class DigitalTwinSnapshot:
    institution_id: str
    timestamp: datetime
    active_sessions: int
    total_present: int
    classroom_utilization: float
    department_activity: Dict[str, Any] = field(default_factory=dict)
    anomaly_hotspots: List[Dict[str, Any]] = field(default_factory=list)
    prediction_next_hour: Optional[Dict[str, Any]] = None


@dataclass
class EmergencyReport:
    emergency_id: str
    institution_id: str
    type: str                    # evacuation | lockdown | drill
    triggered_at: datetime
    resolved_at: Optional[datetime] = None
    total_accounted: int = 0
    missing_count: int = 0
    missing_students: List[str] = field(default_factory=list)
    safe_zones: Dict[str, List[str]] = field(default_factory=dict)
    status: str = "active"
