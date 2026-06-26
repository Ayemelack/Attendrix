import uuid, enum
from sqlalchemy import Column, String, Text, DateTime, Boolean, Integer, Enum, ForeignKey, Index, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
from .sqlalchemy_db import Base


def _utc_now():
    return datetime.utcnow()


class MailStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    SENT = "sent"
    FAILED = "failed"
    RETRYING = "retrying"
    CANCELLED = "cancelled"


class MailEventType(str, enum.Enum):
    QUEUED = "queued"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"
    RETRIED = "retried"
    CANCELLED = "cancelled"
    BOUNCED = "bounced"


class MailTemplateCategory(str, enum.Enum):
    VOUCHER_DELIVERY = "voucher_delivery"
    DEMO_CONFIRMATION = "demo_confirmation"
    PASSWORD_RESET = "password_reset"
    ACCOUNT_ACTIVATION = "account_activation"
    ATTENDANCE_NOTIFICATION = "attendance_notification"
    INSTITUTION_ANNOUNCEMENT = "institution_announcement"
    SYSTEM_ALERT = "system_alert"


class MailSmtpProfile(Base):
    __tablename__ = 'mail_smtp_profiles'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(100), nullable=False, unique=True)
    host = Column(String(255), nullable=False)
    port = Column(Integer, nullable=False, default=587)
    username = Column(String(255), nullable=False, default='')
    password = Column(String(255), nullable=False, default='')
    use_tls = Column(Boolean, nullable=False, default=True)
    from_email = Column(String(255), nullable=False)
    from_name = Column(String(255), nullable=False, default='Attendrix')
    provider_type = Column(String(50), nullable=False, default='smtp')
    rate_limit_per_sec = Column(Integer, nullable=False, default=10)
    daily_quota = Column(Integer, nullable=True)
    is_primary = Column(Boolean, nullable=False, default=False)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), default=_utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=_utc_now, onupdate=_utc_now, nullable=False)

    templates = relationship('MailTemplate', back_populates='smtp_profile', cascade='all, delete-orphan')


class MailTemplate(Base):
    __tablename__ = 'mail_templates'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    smtp_profile_id = Column(String(36), ForeignKey('mail_smtp_profiles.id', ondelete='SET NULL'), nullable=True)
    template_name = Column(String(100), nullable=False, unique=True)
    category = Column(String(40), nullable=False, index=True)
    subject_template = Column(String(500), nullable=False)
    body_template = Column(Text, nullable=False)
    variables_schema = Column(JSON, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), default=_utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=_utc_now, onupdate=_utc_now, nullable=False)

    smtp_profile = relationship('MailSmtpProfile', back_populates='templates')

    __table_args__ = (
        Index('idx_mail_template_category', 'category'),
    )


class MailQueue(Base):
    __tablename__ = 'mail_queue'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    template_id = Column(String(36), ForeignKey('mail_templates.id', ondelete='SET NULL'), nullable=True)
    smtp_profile_id = Column(String(36), ForeignKey('mail_smtp_profiles.id', ondelete='SET NULL'), nullable=True)
    recipient_email = Column(String(320), nullable=False, index=True)
    recipient_name = Column(String(255), nullable=True)
    subject = Column(String(500), nullable=False)
    body_html = Column(Text, nullable=False)
    body_text = Column(Text, nullable=True)
    status = Column(String(20), nullable=False, default='pending', index=True)
    priority = Column(Integer, nullable=False, default=0)
    retry_count = Column(Integer, nullable=False, default=0)
    max_retries = Column(Integer, nullable=False, default=3)
    next_retry_at = Column(DateTime(timezone=True), nullable=True)
    error_message = Column(Text, nullable=True)
    smtp_response = Column(Text, nullable=True)
    tracking_id = Column(String(36), nullable=False, default=lambda: str(uuid.uuid4()), unique=True)
    batch_id = Column(String(36), nullable=True, index=True)
    template_type = Column(String(40), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), default=_utc_now, nullable=False)
    sent_at = Column(DateTime(timezone=True), nullable=True)

    audit_logs = relationship('MailAuditLog', back_populates='mail', cascade='all, delete-orphan')

    __table_args__ = (
        Index('idx_mail_queue_status_next_retry', 'status', 'next_retry_at'),
        Index('idx_mail_queue_created', 'created_at'),
    )


class MailAuditLog(Base):
    __tablename__ = 'mail_audit_logs'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    mail_id = Column(String(36), ForeignKey('mail_queue.id', ondelete='CASCADE'), nullable=False, index=True)
    event_type = Column(String(30), nullable=False, index=True)
    details = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utc_now, nullable=False)

    mail = relationship('MailQueue', back_populates='audit_logs')

    __table_args__ = (
        Index('idx_mail_audit_mail_event', 'mail_id', 'event_type'),
        Index('idx_mail_audit_created', 'created_at'),
    )


class MailUnsubscribe(Base):
    __tablename__ = 'mail_unsubscribes'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    recipient_email_hash = Column(String(64), nullable=False, unique=True, index=True)
    reason = Column(String(200), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utc_now, nullable=False)


def init_mail_tables():
    from .sqlalchemy_db import Base, engine
    Base.metadata.create_all(engine)
