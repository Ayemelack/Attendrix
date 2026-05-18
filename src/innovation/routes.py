"""Innovation Expansion API Routes — Flask Blueprint.

All routes are additive — they do not modify existing routes or services.
Register this blueprint in the Flask app factory without touching existing code.

Usage in app.py:
    from src.innovation.routes import innovation_bp
    app.register_blueprint(innovation_bp)
"""

from flask import Blueprint, jsonify, request
from datetime import datetime
from typing import Dict, Any

from .services import InnovationEngine
from .models import RiskLevel, InterventionTier

innovation_bp = Blueprint('innovation', __name__, url_prefix='/api/innovation')

# Will be set on initialization
_engine: InnovationEngine = None


def init_innovation_routes(engine: InnovationEngine) -> None:
    """Initialize the blueprint with the innovation engine instance."""
    global _engine
    _engine = engine


# ── Status ──

@innovation_bp.route('/status', methods=['GET'])
def innovation_status():
    """Get innovation module status."""
    if not _engine:
        return jsonify({"status": "not_initialized"}), 503
    return jsonify({
        "status": "operational",
        "version": "1.0.0",
        "modules": _engine.get_registry_status()
    })


# ── Academic Risk Intelligence ──

@innovation_bp.route('/risk/predict', methods=['POST'])
def predict_risk():
    """Predict dropout/academic risk for a student."""
    if not _engine or not _engine.risk_engine:
        return jsonify({"error": "Risk engine not available"}), 503
    data = request.get_json() or {}
    profile = _engine.risk_engine.predict_dropout_risk(
        student_id=data.get("student_id", ""),
        institution_id=data.get("institution_id", ""),
        attendance_history=data.get("attendance_history", [])
    )
    return jsonify({
        "student_id": profile.student_id,
        "dropout_probability": profile.dropout_probability,
        "disengagement_score": profile.disengagement_score,
        "absenteeism_trend": profile.absenteeism_trend,
        "risk_level": profile.risk_level.value,
        "intervention_recommendation": profile.intervention_recommendation,
        "risk_factors": profile.risk_factors
    })


@innovation_bp.route('/risk/heatmap', methods=['POST'])
def risk_heatmap():
    """Generate department/faculty risk heatmap."""
    if not _engine or not _engine.risk_engine:
        return jsonify({"error": "Risk engine not available"}), 503
    data = request.get_json() or {}
    from src.innovation.models import RiskProfile
    profiles = [RiskProfile(**p) if isinstance(p, dict) else p
                for p in data.get("profiles", [])]
    result = _engine.risk_engine.generate_risk_heatmap(
        institution_id=data.get("institution_id", ""),
        student_profiles=profiles
    )
    return jsonify(result)


@innovation_bp.route('/risk/exam-eligibility', methods=['POST'])
def exam_eligibility():
    """Predict exam eligibility from attendance trajectory."""
    if not _engine or not _engine.risk_engine:
        return jsonify({"error": "Risk engine not available"}), 503
    data = request.get_json() or {}
    result = _engine.risk_engine.predict_exam_eligibility(
        student_id=data.get("student_id", ""),
        attendance_records=data.get("attendance_records", []),
        course_id=data.get("course_id", "")
    )
    return jsonify(result)


@innovation_bp.route('/risk/burnout', methods=['POST'])
def detect_burnout():
    """Detect burnout patterns from attendance records."""
    if not _engine or not _engine.risk_engine:
        return jsonify({"error": "Risk engine not available"}), 503
    data = request.get_json() or {}
    result = _engine.risk_engine.detect_burnout_patterns(
        student_id=data.get("student_id", ""),
        attendance_records=data.get("attendance_records", [])
    )
    return jsonify(result)


# ── Participation & Engagement ──

@innovation_bp.route('/participation/classify', methods=['POST'])
def classify_engagement():
    """Classify engagement level for a student session."""
    if not _engine or not _engine.participation:
        return jsonify({"error": "Participation engine not available"}), 503
    data = request.get_json() or {}
    score = _engine.participation.classify_engagement(
        student_id=data.get("student_id", ""),
        session_id=data.get("session_id", ""),
        attendance_records=data.get("attendance_records", [])
    )
    return jsonify({
        "student_id": score.student_id,
        "session_id": score.session_id,
        "engagement_type": score.engagement_type.value,
        "participation_score": score.participation_score,
        "attendance_density": score.attendance_density,
        "interaction_frequency": score.interaction_frequency,
    })


@innovation_bp.route('/participation/lecturer-report', methods=['POST'])
def lecturer_report():
    """Generate lecturer effectiveness report."""
    if not _engine or not _engine.participation:
        return jsonify({"error": "Participation engine not available"}), 503
    data = request.get_json() or {}
    result = _engine.participation.lecturer_effectiveness_report(
        lecturer_id=data.get("lecturer_id", ""),
        session_records=data.get("session_records", [])
    )
    return jsonify(result)


@innovation_bp.route('/participation/heatmap', methods=['POST'])
def participation_heatmap():
    """Generate participation heatmap."""
    if not _engine or not _engine.participation:
        return jsonify({"error": "Participation engine not available"}), 503
    data = request.get_json() or {}
    result = _engine.participation.generate_heatmap(
        institution_id=data.get("institution_id", ""),
        attendance_data=data.get("attendance_data", []),
        group_by=data.get("group_by", "department")
    )
    return jsonify(result)


@innovation_bp.route('/participation/silent-students', methods=['POST'])
def silent_students():
    """Detect silently disengaged students."""
    if not _engine or not _engine.participation:
        return jsonify({"error": "Participation engine not available"}), 503
    data = request.get_json() or {}
    from src.innovation.models import EngagementScore
    scores = [EngagementScore(**s) if isinstance(s, dict) else s
              for s in data.get("scores", [])]
    result = _engine.participation.detect_silent_students(
        institution_id=data.get("institution_id", ""),
        all_engagement_scores=scores,
        threshold=data.get("threshold", 0.2)
    )
    return jsonify({"silent_students": result})


# ── Classroom Intelligence ──

@innovation_bp.route('/classroom/intelligence', methods=['POST'])
def classroom_intelligence():
    """Get classroom intelligence metrics."""
    if not _engine or not _engine.classroom:
        return jsonify({"error": "Classroom engine not available"}), 503
    data = request.get_json() or {}
    ci = _engine.classroom.get_classroom_intelligence(
        classroom_id=data.get("classroom_id", ""),
        capacity=data.get("capacity", 0),
        current_attendees=data.get("current_attendees", 0),
        schedule=data.get("schedule", [])
    )
    return jsonify({
        "classroom_id": ci.classroom_id,
        "current_occupancy": ci.current_occupancy,
        "max_capacity": ci.max_capacity,
        "utilization_rate": ci.utilization_rate,
        "peak_hours": ci.peak_hours,
        "underutilized": ci.underutilized,
        "overcrowding_risk": ci.overcrowding_risk,
        "seating_density": ci.seating_density_map,
    })


@innovation_bp.route('/classroom/underutilized', methods=['POST'])
def underutilized_halls():
    """Find underutilized classrooms."""
    if not _engine or not _engine.classroom:
        return jsonify({"error": "Classroom engine not available"}), 503
    data = request.get_json() or {}
    from src.innovation.models import ClassroomIntelligence
    metrics = [ClassroomIntelligence(**m) if isinstance(m, dict) else m
               for m in data.get("metrics", [])]
    result = _engine.classroom.find_underutilized_halls(
        institution_id=data.get("institution_id", ""),
        classroom_metrics=metrics,
        threshold=data.get("threshold")
    )
    return jsonify({"underutilized_halls": result})


@innovation_bp.route('/classroom/overcrowding-prediction', methods=['POST'])
def predict_overcrowding():
    """Predict classroom overcrowding."""
    if not _engine or not _engine.classroom:
        return jsonify({"error": "Classroom engine not available"}), 503
    data = request.get_json() or {}
    result = _engine.classroom.predict_overcrowding(
        institution_id=data.get("institution_id", ""),
        classrooms=data.get("classrooms", [])
    )
    return jsonify({"predictions": result})


# ── Invisible Validation ──

@innovation_bp.route('/validation/pattern', methods=['POST'])
def build_pattern():
    """Build behavioral pattern for a student."""
    if not _engine or not _engine.validation:
        return jsonify({"error": "Validation engine not available"}), 503
    data = request.get_json() or {}
    pattern = _engine.validation.build_pattern(
        student_id=data.get("student_id", ""),
        attendance_history=data.get("attendance_history", [])
    )
    return jsonify({
        "student_id": pattern.student_id,
        "habitual_checkin_time": pattern.habitual_checkin_time,
        "device_consistency": pattern.device_consistency,
        "location_consistency": pattern.location_consistency,
        "peer_proximity_score": pattern.peer_proximity_score,
        "anomaly_score": pattern.anomaly_score,
        "trust_level": pattern.trust_level.value,
    })


@innovation_bp.route('/validation/verify', methods=['POST'])
def validate_attendance():
    """Multi-factor contextual attendance validation."""
    if not _engine or not _engine.validation:
        return jsonify({"error": "Validation engine not available"}), 503
    data = request.get_json() or {}
    result = _engine.validation.validate_attendance(
        student_id=data.get("student_id", ""),
        current_checkin=data.get("checkin", {}),
        historical_pattern=None  # Will be looked up from cache
    )
    return jsonify(result)


@innovation_bp.route('/validation/continuous-presence', methods=['POST'])
def continuous_presence():
    """Verify continuous presence throughout a session."""
    if not _engine or not _engine.validation:
        return jsonify({"error": "Validation engine not available"}), 503
    data = request.get_json() or {}
    result = _engine.validation.verify_continuous_presence(
        student_id=data.get("student_id", ""),
        session_records=data.get("session_records", [])
    )
    return jsonify(result)


# ── Digital Twin ──

@innovation_bp.route('/digital-twin/snapshot', methods=['POST'])
def twin_snapshot():
    """Generate digital twin snapshot."""
    if not _engine or not _engine.digital_twin:
        return jsonify({"error": "Digital twin not available"}), 503
    data = request.get_json() or {}
    snapshot = _engine.digital_twin.generate_snapshot(
        institution_id=data.get("institution_id", ""),
        active_sessions=data.get("active_sessions", []),
        classroom_data=data.get("classroom_data", []),
        department_metrics=data.get("department_metrics")
    )
    return jsonify({
        "institution_id": snapshot.institution_id,
        "timestamp": snapshot.timestamp.isoformat(),
        "active_sessions": snapshot.active_sessions,
        "total_present": snapshot.total_present,
        "classroom_utilization": snapshot.classroom_utilization,
        "department_activity": snapshot.department_activity,
        "anomaly_hotspots": snapshot.anomaly_hotspots,
        "prediction_next_hour": snapshot.prediction_next_hour,
    })


@innovation_bp.route('/digital-twin/heatmap', methods=['POST'])
def twin_heatmap():
    """Generate campus heatmap data."""
    if not _engine or not _engine.digital_twin:
        return jsonify({"error": "Digital twin not available"}), 503
    data = request.get_json() or {}
    result = _engine.digital_twin.generate_heatmap_data(
        institution_id=data.get("institution_id", ""),
        sessions=data.get("sessions", [])
    )
    return jsonify(result)


@innovation_bp.route('/digital-twin/performance', methods=['POST'])
def twin_performance():
    """Calculate institutional performance intelligence."""
    if not _engine or not _engine.digital_twin:
        return jsonify({"error": "Digital twin not available"}), 503
    data = request.get_json() or {}
    result = _engine.digital_twin.institutional_performance(
        institution_id=data.get("institution_id", "")
    )
    return jsonify(result)


# ── Trust Chain ──

@innovation_bp.route('/trust/verify/<chain_id>/<int:block_height>', methods=['GET'])
def verify_chain_entry(chain_id: str, block_height: int):
    """Verify a specific chain entry."""
    if not _engine or not _engine.trust_chain:
        return jsonify({"error": "Trust chain not available"}), 503
    result = _engine.trust_chain.verify_entry(chain_id, block_height)
    return jsonify(result)


@innovation_bp.route('/trust/verify-chain/<chain_id>', methods=['GET'])
def verify_full_chain(chain_id: str):
    """Verify full chain integrity."""
    if not _engine or not _engine.trust_chain:
        return jsonify({"error": "Trust chain not available"}), 503
    result = _engine.trust_chain.verify_chain(chain_id)
    return jsonify(result)


@innovation_bp.route('/trust/attest', methods=['POST'])
def attest_record():
    """Create cryptographically attested record."""
    if not _engine or not _engine.trust_chain:
        return jsonify({"error": "Trust chain not available"}), 503
    data = request.get_json() or {}
    result = _engine.trust_chain.attest_record(
        student_id=data.get("student_id", ""),
        institution_id=data.get("institution_id", ""),
        session_id=data.get("session_id", ""),
        attendance_data=data.get("attendance_data", {})
    )
    return jsonify(result)


# ── Intervention ──

@innovation_bp.route('/intervention/create', methods=['POST'])
def create_intervention():
    """Create an intervention (manual or auto)."""
    if not _engine or not _engine.intervention:
        return jsonify({"error": "Intervention not available"}), 503
    data = request.get_json() or {}
    if data.get("auto", True):
        level = RiskLevel(data.get("risk_level", "medium"))
        record = _engine.intervention._evaluate_intervention(
            student_id=data.get("student_id", ""),
            institution_id=data.get("institution_id", ""),
            risk_level=level
        )
    else:
        tier = InterventionTier(data.get("tier", "tier_1_automated"))
        record = _engine.intervention.create_intervention(
            student_id=data.get("student_id", ""),
            institution_id=data.get("institution_id", ""),
            tier=tier,
            reason=data.get("reason", "Manual intervention"),
            assigned_to=data.get("assigned_to")
        )
    if not record:
        return jsonify({"error": "Could not create intervention"}), 400
    return jsonify({
        "student_id": record.student_id,
        "tier": record.tier.value,
        "status": record.status,
        "auto_generated": record.auto_generated,
        "assigned_to": record.assigned_to,
    })


@innovation_bp.route('/intervention/resolve', methods=['POST'])
def resolve_intervention():
    """Resolve an intervention."""
    if not _engine or not _engine.intervention:
        return jsonify({"error": "Intervention not available"}), 503
    data = request.get_json() or {}
    success = _engine.intervention.resolve_intervention(
        student_id=data.get("student_id", ""),
        intervention_idx=data.get("intervention_idx", -1),
        resolution_note=data.get("note", "")
    )
    return jsonify({"resolved": success})


@innovation_bp.route('/intervention/pending', methods=['GET'])
def pending_interventions():
    """Get all pending interventions."""
    if not _engine or not _engine.intervention:
        return jsonify({"error": "Intervention not available"}), 503
    institution_id = request.args.get("institution_id", "")
    result = _engine.intervention.get_pending_interventions(institution_id)
    return jsonify({"pending_interventions": result})


# ── Reputation ──

@innovation_bp.route('/reputation/student', methods=['POST'])
def student_reputation():
    """Compute student reputation score."""
    if not _engine or not _engine.reputation:
        return jsonify({"error": "Reputation not available"}), 503
    data = request.get_json() or {}
    score = _engine.reputation.compute_student_reputation(
        student_id=data.get("student_id", ""),
        institution_id=data.get("institution_id", ""),
        attendance_history=data.get("attendance_history", [])
    )
    return jsonify({
        "entity_id": score.entity_id,
        "reliability_score": score.reliability_score,
        "consistency_score": score.consistency_score,
        "trust_score": score.trust_score,
        "ranking": score.ranking,
    })


@innovation_bp.route('/reputation/lecturer', methods=['POST'])
def lecturer_reputation():
    """Compute lecturer reputation score."""
    if not _engine or not _engine.reputation:
        return jsonify({"error": "Reputation not available"}), 503
    data = request.get_json() or {}
    score = _engine.reputation.compute_lecturer_reputation(
        lecturer_id=data.get("lecturer_id", ""),
        institution_id=data.get("institution_id", ""),
        session_history=data.get("session_history", [])
    )
    return jsonify({
        "entity_id": score.entity_id,
        "reliability_score": score.reliability_score,
        "consistency_score": score.consistency_score,
        "trust_score": score.trust_score,
    })


@innovation_bp.route('/reputation/department-rankings', methods=['POST'])
def department_rankings():
    """Rank departments by attendance discipline."""
    if not _engine or not _engine.reputation:
        return jsonify({"error": "Reputation not available"}), 503
    data = request.get_json() or {}
    from src.innovation.models import ReputationScore
    scores = [ReputationScore(**s) if isinstance(s, dict) else s
              for s in data.get("scores", [])]
    result = _engine.reputation.rank_departments(
        institution_id=data.get("institution_id", ""),
        student_scores=scores
    )
    return jsonify({"rankings": result})


# ── Security & Emergency ──

@innovation_bp.route('/security/emergency/activate', methods=['POST'])
def activate_emergency():
    """Activate emergency protocol."""
    if not _engine or not _engine.security:
        return jsonify({"error": "Security not available"}), 503
    data = request.get_json() or {}
    report = _engine.security.activate_emergency(
        institution_id=data.get("institution_id", ""),
        emergency_type=data.get("type", "drill"),
        triggered_by=data.get("triggered_by", "system")
    )
    return jsonify({
        "emergency_id": report.emergency_id,
        "type": report.type,
        "status": report.status,
        "triggered_at": report.triggered_at.isoformat()
    })


@innovation_bp.route('/security/emergency/resolve', methods=['POST'])
def resolve_emergency():
    """Resolve active emergency."""
    if not _engine or not _engine.security:
        return jsonify({"error": "Security not available"}), 503
    data = request.get_json() or {}
    success = _engine.security.resolve_emergency(
        emergency_id=data.get("emergency_id", "")
    )
    return jsonify({"resolved": success})


@innovation_bp.route('/security/emergency/reconcile', methods=['POST'])
def reconcile_evacuation():
    """Reconcile evacuation attendance."""
    if not _engine or not _engine.security:
        return jsonify({"error": "Security not available"}), 503
    data = request.get_json() or {}
    result = _engine.security.reconcile_evacuation(
        emergency_id=data.get("emergency_id", ""),
        expected_present=data.get("expected_present", {}),
        safe_zone_checkins=data.get("safe_zone_checkins", {})
    )
    return jsonify(result)


@innovation_bp.route('/security/active', methods=['GET'])
def active_emergencies():
    """Get all active emergencies."""
    if not _engine or not _engine.security:
        return jsonify({"error": "Security not available"}), 503
    institution_id = request.args.get("institution_id", "")
    result = _engine.security.get_active_emergencies(institution_id)
    return jsonify({"active_emergencies": result})


# ── Infrastructure & Networking ──

@innovation_bp.route('/infrastructure/status', methods=['GET'])
def network_status():
    """Get network infrastructure status."""
    if not _engine or not _engine.infrastructure:
        return jsonify({"error": "Infrastructure not available"}), 503
    result = _engine.infrastructure.get_network_status()
    return jsonify(result)


@innovation_bp.route('/infrastructure/node/register', methods=['POST'])
def register_node():
    """Register an edge node."""
    if not _engine or not _engine.infrastructure:
        return jsonify({"error": "Infrastructure not available"}), 503
    data = request.get_json() or {}
    result = _engine.infrastructure.register_node(
        node_id=data.get("node_id", ""),
        node_type=data.get("node_type", "edge"),
        location=data.get("location", ""),
        capabilities=data.get("capabilities", [])
    )
    return jsonify(result)


@innovation_bp.route('/infrastructure/load-balance', methods=['GET'])
def load_balance():
    """Get load balance recommendations."""
    if not _engine or not _engine.infrastructure:
        return jsonify({"error": "Infrastructure not available"}), 503
    result = _engine.infrastructure.balance_load()
    return jsonify(result)


# ── Ecosystem Integration ──

@innovation_bp.route('/ecosystem/integrations', methods=['GET'])
def available_integrations():
    """List available system integrations."""
    if not _engine or not _engine.ecosystem:
        return jsonify({"error": "Ecosystem not available"}), 503
    result = _engine.ecosystem.get_available_integrations()
    return jsonify(result)


@innovation_bp.route('/ecosystem/campus-apis', methods=['GET'])
def campus_api_catalog():
    """Get smart campus API catalog."""
    if not _engine or not _engine.ecosystem:
        return jsonify({"error": "Ecosystem not available"}), 503
    result = _engine.ecosystem.get_campus_api_catalog()
    return jsonify(result)


@innovation_bp.route('/health', methods=['GET'])
def innovation_health():
    """Health check for innovation subsystem."""
    return jsonify({
        "service": "attendrix-innovation",
        "version": "1.0.0",
        "engine_ready": _engine is not None and _engine._initialized,
        "timestamp": datetime.utcnow().isoformat()
    })
