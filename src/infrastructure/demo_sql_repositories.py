from sqlalchemy import Column, String, Text, DateTime, Boolean, JSON, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
from .sqlalchemy_db import Base, get_db_session
from sqlalchemy.exc import IntegrityError


def _utc_now():
    return datetime.utcnow()


class DemoLead(Base):
    __tablename__ = 'demo_leads'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String(254), nullable=False, unique=True, index=True)
    full_name = Column(String(100), nullable=False)
    institution_name = Column(String(150), nullable=True)
    institution_type = Column(String(80), nullable=True)
    institution_size = Column(String(20), nullable=True)
    role = Column(String(40), nullable=True)
    country = Column(String(2), nullable=True)
    phone = Column(String(20), nullable=True)
    source = Column(String(100), nullable=True)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)
    metadata_ = Column('metadata', JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), default=_utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=_utc_now, nullable=False)

    onboarding_sessions = relationship('OnboardingSession', back_populates='demo_lead')


class OnboardingSession(Base):
    __tablename__ = 'demo_onboarding_sessions'
    __table_args__ = (UniqueConstraint('session_token', name='uq_onboarding_session_token'),)

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    demo_lead_id = Column(String(36), ForeignKey('demo_leads.id', ondelete='CASCADE'), nullable=False)
    session_token = Column(String(64), nullable=False, unique=True, index=True)
    status = Column(String(30), nullable=False, default='pending')
    current_step = Column(String(30), nullable=False, default='request_demo')
    progress = Column(JSON, nullable=False, default=dict)
    prefill_data = Column(JSON, nullable=False, default=dict)
    selected_timezone = Column(String(64), nullable=True)
    selected_date = Column(String(10), nullable=True)
    selected_time = Column(String(10), nullable=True)
    selected_datetime_utc = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    last_activity_at = Column(DateTime(timezone=True), default=_utc_now, nullable=False)
    metadata_ = Column('metadata', JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), default=_utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=_utc_now, nullable=False)

    demo_lead = relationship('DemoLead', back_populates='onboarding_sessions')
    bookings = relationship('DemoBooking', back_populates='session')


class DemoBooking(Base):
    __tablename__ = 'demo_bookings'
    __table_args__ = (UniqueConstraint('booking_token', name='uq_demo_booking_token'),)

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    demo_lead_id = Column(String(36), ForeignKey('demo_leads.id', ondelete='CASCADE'), nullable=False)
    onboarding_session_id = Column(String(36), ForeignKey('demo_onboarding_sessions.id', ondelete='CASCADE'), nullable=False)
    booking_token = Column(String(64), nullable=False, unique=True, index=True)
    status = Column(String(30), nullable=False, default='confirmed')
    scheduled_at_utc = Column(DateTime(timezone=True), nullable=True)
    scheduled_timezone = Column(String(64), nullable=True)
    meeting_url = Column(Text, nullable=True)
    meeting_provider = Column(String(50), nullable=True)
    reminder_sent_at = Column(DateTime(timezone=True), nullable=True)
    confirmed_at = Column(DateTime(timezone=True), nullable=True)
    rescheduled_at = Column(DateTime(timezone=True), nullable=True)
    cancelled_at = Column(DateTime(timezone=True), nullable=True)
    metadata_ = Column('metadata', JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), default=_utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=_utc_now, nullable=False)

    demo_lead = relationship('DemoLead')
    session = relationship('OnboardingSession', back_populates='bookings')


class DemoAnalyticsEvent(Base):
    __tablename__ = 'demo_analytics_events'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    demo_lead_id = Column(String(36), ForeignKey('demo_leads.id', ondelete='SET NULL'), nullable=True)
    onboarding_session_id = Column(String(36), ForeignKey('demo_onboarding_sessions.id', ondelete='SET NULL'), nullable=True)
    event_name = Column(String(80), nullable=False)
    event_category = Column(String(50), nullable=True)
    event_properties = Column(JSON, nullable=False, default=dict)
    country = Column(String(2), nullable=True)
    institution_type = Column(String(80), nullable=True)
    timestamp = Column(DateTime(timezone=True), default=_utc_now, nullable=False)


class DemoTrial(Base):
    __tablename__ = 'demo_trials'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    demo_lead_id = Column(String(36), ForeignKey('demo_leads.id', ondelete='CASCADE'), nullable=False)
    onboarding_session_id = Column(String(36), ForeignKey('demo_onboarding_sessions.id', ondelete='CASCADE'), nullable=False)
    trial_status = Column(String(30), nullable=False, default='pending')
    trial_start_at = Column(DateTime(timezone=True), nullable=True)
    trial_end_at = Column(DateTime(timezone=True), nullable=True)
    expired_at = Column(DateTime(timezone=True), nullable=True)
    permissions = Column(JSON, nullable=False, default=dict)
    sandbox_data = Column(JSON, nullable=False, default=dict)
    metadata_ = Column('metadata', JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), default=_utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=_utc_now, nullable=False)


class _BaseRepository:
    def __init__(self):
        self._session = None
        self._owns_session = True

    def _get_session(self, session=None):
        if session is not None:
            self._session = session
            self._owns_session = False
        if self._session is None:
            self._session = get_db_session()
            self._owns_session = True
        return self._session

    def _commit(self):
        session = self._get_session()
        try:
            session.commit()
        except Exception:
            session.rollback()
            self._cleanup()
            raise

    def _cleanup(self):
        if self._session is not None and self._owns_session:
            self._session.close()
            self._session = None


class DemoLeadRepository(_BaseRepository):
    def get_by_email(self, email: str):
        session = self._get_session()
        return session.query(DemoLead).filter(DemoLead.email == email.lower().strip()).first()

    def save(self, lead: DemoLead):
        session = self._get_session()
        session.add(lead)
        self._commit()
        self._cleanup()
        return lead


class OnboardingSessionRepository(_BaseRepository):
    def get_by_token(self, token: str):
        session = self._get_session()
        return session.query(OnboardingSession).filter(OnboardingSession.session_token == token).first()

    def create(self, session: OnboardingSession):
        db_session = self._get_session()
        db_session.add(session)
        self._commit()
        self._cleanup()
        return session

    def update(self, session: OnboardingSession, values: dict):
        for key, val in values.items():
            setattr(session, key, val)
        session.updated_at = datetime.utcnow()
        self._commit()
        self._cleanup()
        return session


class DemoBookingRepository(_BaseRepository):
    def get_active_by_email(self, email: str):
        session = self._get_session()
        return session.query(DemoBooking).join(DemoLead).filter(
            DemoLead.email == email.lower().strip(),
            DemoBooking.status.notin_(['cancelled', 'expired'])
        ).order_by(DemoBooking.created_at.desc()).first()

    def get_by_token(self, token: str):
        session = self._get_session()
        return session.query(DemoBooking).filter(DemoBooking.booking_token == token).first()

    def get_by_session_token(self, session_token: str):
        session = self._get_session()
        return session.query(DemoBooking).join(OnboardingSession).filter(
            OnboardingSession.session_token == session_token
        ).order_by(DemoBooking.created_at.desc()).first()

    def save(self, booking: DemoBooking):
        session = self._get_session()
        session.add(booking)
        self._commit()
        self._cleanup()
        return booking

    def get_conflict(self, utc_dt):
        session = self._get_session()
        return session.query(DemoBooking).filter(
            DemoBooking.scheduled_at_utc == utc_dt,
            DemoBooking.status.notin_(['cancelled', 'expired'])
        ).first()


class DemoAnalyticsRepository(_BaseRepository):
    def save(self, event: DemoAnalyticsEvent):
        session = self._get_session()
        session.add(event)
        self._commit()
        self._cleanup()
        return event


class DemoTrialRepository(_BaseRepository):
    def save(self, trial: DemoTrial):
        session = self._get_session()
        session.add(trial)
        self._commit()
        self._cleanup()
        return trial


# Repository instances
lead_repo = DemoLeadRepository()
session_repo = OnboardingSessionRepository()
booking_repo = DemoBookingRepository()
analytics_repo = DemoAnalyticsRepository()
trial_repo = DemoTrialRepository()
