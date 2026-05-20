from sqlalchemy import Column, String, Text, DateTime, Boolean, JSON, Integer, Float, ForeignKey, Enum, Index
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid, enum
from .sqlalchemy_db import Base, get_db_session

def _utc_now():
    return datetime.utcnow()

class FeedbackCategory(str, enum.Enum):
    ATTENDANCE_ISSUE = "attendance_issue"
    BUG_REPORT = "bug_report"
    FEATURE_REQUEST = "feature_request"
    LECTURER_COMPLAINT = "lecturer_complaint"
    NETWORK_FAILURE = "network_failure"
    SECURITY_CONCERN = "security_concern"
    UI_UX_PROBLEM = "ui_ux_problem"
    MOBILE_APP_PROBLEM = "mobile_app_problem"
    SYNC_FAILURE = "sync_failure"
    SUGGESTION = "suggestion"
    GENERAL = "general"

class FeedbackSeverity(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class FeedbackStatus(str, enum.Enum):
    OPEN = "open"
    IN_REVIEW = "in_review"
    RESOLVED = "resolved"
    ARCHIVED = "archived"
    HIDDEN = "hidden"

class Feedback(Base):
    __tablename__ = 'feedback'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), nullable=False, index=True)
    user_role = Column(String(30), nullable=False, default='student')
    institution = Column(String(150), nullable=True, index=True)
    category = Column(String(40), nullable=False, index=True)
    severity = Column(String(20), nullable=False, default='medium')
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=False)
    experience_rating = Column(Integer, nullable=True)
    screenshot_path = Column(String(500), nullable=True)
    is_anonymous = Column(Boolean, nullable=False, default=True)
    allow_contact = Column(Boolean, nullable=False, default=False)
    community_visible = Column(Boolean, nullable=False, default=True)
    status = Column(String(20), nullable=False, default='open', index=True)
    upvotes = Column(Integer, nullable=False, default=0)
    reply_count = Column(Integer, nullable=False, default=0)
    is_resolved = Column(Boolean, nullable=False, default=False)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    resolved_by = Column(String(36), nullable=True)
    admin_viewed = Column(Boolean, nullable=False, default=False)
    admin_viewed_at = Column(DateTime(timezone=True), nullable=True)
    admin_notes = Column(Text, nullable=True)
    is_flagged = Column(Boolean, nullable=False, default=False)
    is_hidden = Column(Boolean, nullable=False, default=False)
    flag_reason = Column(String(200), nullable=True)
    moderation_action = Column(String(100), nullable=True)
    moderation_by = Column(String(36), nullable=True)
    moderation_at = Column(DateTime(timezone=True), nullable=True)
    escalation_level = Column(String(20), nullable=False, default='none')
    escalation_count = Column(Integer, nullable=False, default=0)
    device_info = Column(JSON, nullable=True)
    network_diagnostics = Column(JSON, nullable=True)
    browser_info = Column(JSON, nullable=True)
    sync_logs = Column(JSON, nullable=True)
    sentiment_score = Column(Float, nullable=True)
    sentiment_label = Column(String(20), nullable=True)
    keywords = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utc_now, nullable=False, index=True)
    updated_at = Column(DateTime(timezone=True), default=_utc_now, onupdate=_utc_now, nullable=False)

    replies = relationship('FeedbackReply', back_populates='feedback', cascade='all, delete-orphan')
    reactions = relationship('FeedbackReaction', back_populates='feedback', cascade='all, delete-orphan')

    __table_args__ = (
        Index('idx_feedback_category_status', 'category', 'status'),
        Index('idx_feedback_institution_category', 'institution', 'category'),
        Index('idx_feedback_severity_status', 'severity', 'status'),
    )

class FeedbackReply(Base):
    __tablename__ = 'feedback_replies'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    feedback_id = Column(String(36), ForeignKey('feedback.id', ondelete='CASCADE'), nullable=False, index=True)
    user_id = Column(String(36), nullable=False)
    user_role = Column(String(30), nullable=False)
    is_anonymous = Column(Boolean, nullable=False, default=True)
    body = Column(Text, nullable=False)
    is_admin = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), default=_utc_now, nullable=False)

    feedback = relationship('Feedback', back_populates='replies')

class FeedbackReaction(Base):
    __tablename__ = 'feedback_reactions'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    feedback_id = Column(String(36), ForeignKey('feedback.id', ondelete='CASCADE'), nullable=False, index=True)
    user_id = Column(String(36), nullable=False)
    reaction_type = Column(String(20), nullable=False, default='upvote')
    created_at = Column(DateTime(timezone=True), default=_utc_now, nullable=False)

    feedback = relationship('Feedback', back_populates='reactions')

    __table_args__ = (
        Index('idx_reaction_feedback_user', 'feedback_id', 'user_id', unique=True),
    )

class ModerationLog(Base):
    __tablename__ = 'moderation_logs'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    feedback_id = Column(String(36), ForeignKey('feedback.id', ondelete='CASCADE'), nullable=True, index=True)
    admin_id = Column(String(36), nullable=False)
    action = Column(String(50), nullable=False)
    reason = Column(String(500), nullable=True)
    details = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utc_now, nullable=False)

class FeedbackDiagnostics(Base):
    __tablename__ = 'feedback_diagnostics'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    feedback_id = Column(String(36), ForeignKey('feedback.id', ondelete='CASCADE'), nullable=False, index=True)
    network_latency_ms = Column(Float, nullable=True)
    vpn_active = Column(Boolean, nullable=False, default=False)
    offline_mode = Column(Boolean, nullable=False, default=False)
    mqtt_sync_status = Column(String(30), nullable=True)
    mqtt_sync_logs = Column(JSON, nullable=True)
    packet_loss_pct = Column(Float, nullable=True)
    sync_duration_ms = Column(Float, nullable=True)
    browser_version = Column(String(100), nullable=True)
    os_platform = Column(String(100), nullable=True)
    device_type = Column(String(50), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utc_now, nullable=False)

    __table_args__ = (
        Index('idx_diag_feedback', 'feedback_id'),
    )

class EscalationHistory(Base):
    __tablename__ = 'escalation_history'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    feedback_id = Column(String(36), ForeignKey('feedback.id', ondelete='CASCADE'), nullable=False, index=True)
    from_level = Column(String(20), nullable=False)
    to_level = Column(String(20), nullable=False)
    reason = Column(String(500), nullable=True)
    triggered_by = Column(String(36), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utc_now, nullable=False)

def init_feedback_tables():
    from .sqlalchemy_db import Base, engine
    Base.metadata.create_all(engine)
