import html
import json
import logging
import os
import re
import secrets
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from zoneinfo import ZoneInfo

from config.settings import get_config
from src.domain.entities import DemoBooking, DemoBookingStatus
from src.infrastructure.repositories import demo_booking_repo
from src.infrastructure.demo_sql_repositories import (
    DemoLead,
    OnboardingSession,
    DemoBooking as SQLDemoBooking,
    DemoAnalyticsEvent,
    lead_repo,
    session_repo,
    booking_repo,
    analytics_repo,
)

logger = logging.getLogger(__name__)

EMAIL_REGEX = re.compile(r'^[^\s@]+@[^\s@]+\.[^\s@]{2,}$')
PHONE_REGEX = re.compile(r'^[\d\s\-\+\(\)]{7,20}$')
NAME_REGEX = re.compile(r"^[a-zA-Z\s'.\-]{2,100}$")
COUNTRY_REGEX = re.compile(r'^[A-Z]{2}$')
SQL_INJECTION_PATTERNS = re.compile(r'\b(SELECT|INSERT|UPDATE|DELETE|DROP|UNION|--|;|\*|OR|AND)\b', re.IGNORECASE)
SIZE_OPTIONS = ['<500', '500-2000', '2000-5000', '5000-10000', '10000+']
ALLOWED_ROLES = ['super_admin', 'institutional_admin', 'lecturer', 'student', 'employee', 'other']
TIME_FORMAT = '%H:%M'
DATE_FORMAT = '%Y-%m-%d'


def sanitize_text(value: Optional[str]) -> str:
    if not value:
        return ''
    cleaned = html.escape(str(value).strip())
    return SQL_INJECTION_PATTERNS.sub('', cleaned)


def normalize_timezone(timezone: str) -> Optional[ZoneInfo]:
    if not timezone:
        return None
    try:
        return ZoneInfo(timezone)
    except Exception:
        return None


def parse_datetime_slot(date_value: str, time_value: str, timezone: str) -> Optional[datetime]:
    try:
        tz = normalize_timezone(timezone) or ZoneInfo('UTC')
        dt = datetime.strptime(f"{date_value} {time_value}", f"{DATE_FORMAT} {TIME_FORMAT}")
        return dt.replace(tzinfo=tz).astimezone(ZoneInfo('UTC'))
    except Exception:
        return None


def verify_captcha(response_token: str) -> bool:
    if not response_token:
        return False

    config = get_config()
    secret_key = config.get('RECAPTCHA_SECRET_KEY')
    if not secret_key:
        return False

    payload = urllib.parse.urlencode({
        'secret': secret_key,
        'response': response_token
    }).encode('utf-8')

    try:
        request = urllib.request.Request(
            'https://www.google.com/recaptcha/api/siteverify',
            data=payload,
            method='POST'
        )
        with urllib.request.urlopen(request, timeout=10) as response:
            result = json.loads(response.read().decode('utf-8'))
            return bool(result.get('success'))
    except Exception as exc:
        logger.warning('Captcha verification failed: %s', exc)
        return False


class DemoBookingService:

    @staticmethod
    def generate_csrf_token() -> str:
        return secrets.token_hex(32)

    @staticmethod
    def validate_email(email: str) -> Optional[str]:
        if not email or not EMAIL_REGEX.match(email):
            return 'Please provide a valid email address.'
        return None

    @staticmethod
    def validate_name(name: str) -> Optional[str]:
        if not name or not NAME_REGEX.match(name):
            return 'Please provide a valid full name (letters, spaces, hyphens only).'
        return None

    @staticmethod
    def validate_phone(phone: str) -> Optional[str]:
        if not phone or not PHONE_REGEX.match(phone):
            return 'Please provide a valid phone number.'
        return None

    @staticmethod
    def validate_required(value: str, field_name: str) -> Optional[str]:
        if not value or not value.strip():
            return f'{field_name} is required.'
        return None

    @staticmethod
    def validate_time_slot(time: str) -> Optional[str]:
        valid_times = ['09:00', '10:00', '11:00', '13:00', '14:00', '15:00', '16:00']
        if time not in valid_times:
            return 'Please select a valid time slot.'
        return None

    def validate_booking_input(self, data: Dict[str, Any]) -> List[str]:
        errors = []
        name_err = self.validate_name(data.get('fullName', ''))
        if name_err: errors.append(name_err)

        email_err = self.validate_email(data.get('email', ''))
        if email_err: errors.append(email_err)

        phone_err = self.validate_phone(data.get('phone', ''))
        if phone_err: errors.append(phone_err)

        inst_err = self.validate_required(data.get('institution', ''), 'Institution')
        if inst_err: errors.append(inst_err)

        time_err = self.validate_time_slot(data.get('time', ''))
        if time_err: errors.append(time_err)

        return errors

    def create_demo_lead(self, data: Dict[str, Any]):
        email = data['email'].strip().lower()
        lead = lead_repo.get_by_email(email)
        if lead:
            return lead

        lead = DemoLead(
            email=email,
            full_name=sanitize_text(data.get('fullName', '')),
            institution_name=sanitize_text(data.get('institution', '')),
            institution_type=sanitize_text(data.get('institutionType', '')),
            institution_size=sanitize_text(data.get('numberOfStudents', '')),
            role=sanitize_text(data.get('role', '')),
            country=sanitize_text(data.get('country', '')).upper(),
            phone=sanitize_text(data.get('phone', '')),
            source='schedule-demo',
            ip_address=data.get('_ip', ''),
            user_agent=data.get('_ua', ''),
            metadata_={
                'source': 'request-demo-api',
                'referrer': data.get('referrer', '')
            }
        )
        return lead_repo.save(lead)

    def create_onboarding_session(self, lead: DemoLead, data: Dict[str, Any]):
        token = secrets.token_urlsafe(32)
        session = OnboardingSession(
            demo_lead_id=lead.id,
            session_token=token,
            status='pending',
            current_step='request_demo',
            progress={'stage': 'requested'},
            prefill_data={
                'fullName': sanitize_text(data.get('fullName', '')),
                'email': lead.email,
                'institution': sanitize_text(data.get('institution', '')),
                'institutionType': sanitize_text(data.get('institutionType', '')),
                'numberOfStudents': sanitize_text(data.get('numberOfStudents', '')),
                'phone': sanitize_text(data.get('phone', ''))
            },
            selected_timezone=sanitize_text(data.get('timezone', '')),
            selected_date=sanitize_text(data.get('date', '')),
            selected_time=sanitize_text(data.get('time', '')),
            expires_at=datetime.utcnow() + timedelta(days=30),
            metadata_={
                'ip_address': data.get('_ip', ''),
                'user_agent': data.get('_ua', ''),
            }
        )
        return session_repo.create(session)

    def record_analytics_event(self, email: str, event_name: str, properties: Dict[str, Any]) -> None:
        lead = lead_repo.get_by_email(email)
        session_token = properties.get('session_token')
        session = session_repo.get_by_token(session_token) if session_token else None
        event = analytics_repo.save(
            DemoAnalyticsEvent(
                demo_lead_id=lead.id if lead else None,
                onboarding_session_id=session.id if session else None,
                event_name=event_name,
                event_category=properties.get('category'),
                event_properties=properties,
                country=properties.get('country'),
                institution_type=properties.get('institution_type')
            )
        )
        logger.debug('Analytics event recorded: %s', event_name)

    def check_existing_booking(self, email: str) -> Optional[Dict[str, Any]]:
        """Check if email already has an active booking. Returns the booking if found."""
        existing = demo_booking_repo.get_active_by_email(email)
        if existing:
            return existing
        sql_existing = booking_repo.get_active_by_email(email)
        if sql_existing:
            return {
                'booking_token': sql_existing.booking_token,
                'preferred_time': sql_existing.scheduled_timezone,
                'preferred_date': sql_existing.scheduled_at_utc.isoformat() if sql_existing.scheduled_at_utc else '',
                'full_name': sql_existing.demo_lead.full_name,
                'institution': sql_existing.demo_lead.institution_name
            }
        return None

    def create_booking(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new demo booking with full validation and persistence."""
        validation_errors = self.validate_booking_input(data)
        if validation_errors:
            return {'success': False, 'errors': validation_errors}

        email = data['email'].strip().lower()
        existing = self.check_existing_booking(email)
        if existing:
            return {
                'success': False,
                'duplicate': True,
                'message': 'This email address is already associated with an existing Attendrix demo booking. Please use another email or continue with your existing booking.',
                'existing_token': existing.get('booking_token')
            }

        db_session = None
        try:
            from src.infrastructure.sqlalchemy_db import get_db_session
            db_session = get_db_session()
            lead_repo._get_session(db_session)
            session_repo._get_session(db_session)
            booking_repo._get_session(db_session)

            session_token = data.get('sessionToken')
            lead = self.create_demo_lead(data)
            session = session_repo.get_by_token(session_token) if session_token else None
            if not session or session.demo_lead_id != lead.id:
                session = self.create_onboarding_session(lead, data)

            timezone = sanitize_text(data.get('timezone', 'UTC')) or 'UTC'
            scheduled_utc = parse_datetime_slot(data.get('date', ''), data.get('time', ''), timezone)
            if not scheduled_utc:
                return {'success': False, 'message': 'Please select a valid date, time and timezone for the demo.'}

            conflict = booking_repo.get_conflict(scheduled_utc)
            if conflict:
                return {'success': False, 'message': 'The selected timeslot is already booked. Please choose another available time.'}

            booking_token = secrets.token_urlsafe(24)
            sql_booking = SQLDemoBooking(
                demo_lead_id=lead.id,
                onboarding_session_id=session.id,
                booking_token=booking_token,
                status=DemoBookingStatus.CONFIRMED.value,
                scheduled_at_utc=scheduled_utc,
                scheduled_timezone=timezone,
                confirmed_at=datetime.utcnow(),
                metadata_={
                    'source': 'schedule-demo',
                    'ip_address': data.get('_ip', ''),
                    'user_agent': data.get('_ua', ''),
                    'preferred_date': data.get('date', ''),
                    'preferred_time': data.get('time', ''),
                }
            )
            booking_repo.save(sql_booking)

            try:
                demo_booking = DemoBooking(
                    id=sql_booking.id,
                    email=lead.email,
                    full_name=lead.full_name,
                    phone=lead.phone,
                    institution=lead.institution_name,
                    institution_type=lead.institution_type,
                    number_of_students=lead.institution_size,
                    preferred_date=data.get('date', ''),
                    preferred_time=data.get('time', ''),
                    status=sql_booking.status,
                    booking_token=sql_booking.booking_token,
                    csrf_token=None,
                    session_token=session.session_token,
                    meeting_url=sql_booking.meeting_url,
                    meeting_provider=sql_booking.meeting_provider,
                    onboarding_progress=session.progress,
                    onboarding_completed=False,
                    metadata=sql_booking.metadata_ if hasattr(sql_booking, 'metadata_') else {},
                    created_at=sql_booking.created_at,
                    updated_at=sql_booking.updated_at,
                    expires_at=session.expires_at,
                    confirmed_at=sql_booking.confirmed_at,
                    scheduled_at=sql_booking.scheduled_at_utc
                )
                booking_dict = demo_booking_repo.to_dict(demo_booking)
                demo_booking_repo.create(booking_dict, document_id=demo_booking.id)
            except Exception:
                logger.warning('SQL booking created but Firestore fallback failed for %s', email)

            email_status = 'disabled'
            email_error = ''
            email_api_response = None
            logger.info(
                'STAGE: booking_saved | email=%s | token=%s | time=%s | date=%s',
                email, booking_token, data.get('time'), data.get('date'),
            )
            try:
                from src.infrastructure.email_service import email_service as _email_svc
                _avail = _email_svc.is_available
                _prov = _email_svc.provider
                _from = _email_svc._config.get('from_email', '')
                logger.info(
                    'STAGE: email_service_check | email=%s | available=%s | provider=%s | from=%s',
                    email, _avail, _prov, _from,
                )
                if _avail:
                    logger.info(
                        'STAGE: email_queued | email=%s | provider=%s | from=%s | subject=Your Attendrix Demo is Confirmed',
                        email, _prov, _from,
                    )
                    app_url = os.environ.get('APP_URL', 'http://localhost:5000')
                    portal_url = f"{app_url}/demo-prep?token={booking_token}"
                    result = _email_svc.send_demo_confirmation(
                        to_email=lead.email,
                        to_name=lead.full_name,
                        institution=lead.institution_name or data.get('institution', ''),
                        demo_date=data.get('date', ''),
                        demo_time=data.get('time', ''),
                        timezone=timezone,
                        booking_token=booking_token,
                        portal_url=portal_url,
                    )
                    email_status = result.get('status', 'failed')
                    email_api_response = result.get('api_response')
                    if email_status == 'failed':
                        email_error = result.get('message', 'Email delivery failed')
                        logger.error(
                            'STAGE: email_failed | email=%s | reason=%s | api_response=%s',
                            email, email_error, email_api_response,
                        )
                    else:
                        logger.info(
                            'STAGE: email_accepted | email=%s | email_id=%s | api_response=%s',
                            email, result.get('email_id'), email_api_response,
                        )
                else:
                    logger.warning(
                        'STAGE: email_disabled | email=%s | provider=%s | enabled=%s',
                        email, _prov, _email_svc._config.get('email_enabled'),
                    )
            except Exception as email_err:
                logger.error('STAGE: email_exception | email=%s | error=%s', email, email_err)
                email_status = 'failed'
                email_error = str(email_err)
                email_api_response = {'exception': str(email_err)}

            try:
                booking_repo._get_session(db_session)
                sql_booking.metadata_ = sql_booking.metadata_ or {}
                sql_booking.metadata_['email_status'] = email_status
                sql_booking.metadata_['email_error'] = email_error
                sql_booking.metadata_['email_sent_at'] = datetime.utcnow().isoformat() if email_status == 'sent' else None
                sql_booking.metadata_['email_api_response'] = email_api_response
                booking_repo._commit()
            except Exception as meta_err:
                logger.warning('Failed to update metadata with email status: %s', meta_err)

            # If email service is available but sending failed, report error to user
            # (booking is still saved in DB so user can retry, but the API returns failure)
            if email_status == 'failed' and any(os.environ.get(k) for k in ('SMTP_HOST','RESEND_API_KEY')):
                logger.warning(
                    'Booking created for %s but email FAILED — returning error to user: %s',
                    email, email_error,
                )
                return {
                    'success': False,
                    'message': 'Your demo was booked successfully, but we could not send the confirmation email. Please contact support@attendrix.com for assistance.',
                    'token': booking_token,
                    'session_token': session.session_token,
                    'booking': {
                        'time': data.get('time', ''),
                        'date': data.get('date', ''),
                        'name': lead.full_name,
                        'institution': lead.institution_name or data.get('institution', '')
                    },
                    'email_status': email_status,
                    'email_error': email_error,
                    'email_api_response': email_api_response,
                }

            return {
                'success': True,
                'token': booking_token,
                'session_token': session.session_token,
                'booking': {
                    'time': data.get('time', ''),
                    'date': data.get('date', ''),
                    'name': lead.full_name,
                    'institution': lead.institution_name or data.get('institution', '')
                },
                'email_status': email_status,
                'email_api_response': email_api_response,
            }
        except Exception as exc:
            logger.error('Demo booking persistence failed for %s: %s', email, exc)
            return {'success': False, 'message': 'Unable to complete booking right now. Please try again shortly.'}
        finally:
            if db_session is not None:
                try:
                    db_session.close()
                except Exception:
                    pass

    def restore_booking(self, email: str) -> Optional[Dict[str, Any]]:
        """Restore a user's existing booking by email for continuity."""
        email = email.strip().lower()
        sql_booking = booking_repo.get_active_by_email(email)
        if sql_booking:
            result = self._serialize_sql_booking(sql_booking)
            result['session_token'] = sql_booking.session.session_token if sql_booking.session else None
            return result

        booking = demo_booking_repo.get_active_by_email(email)
        if not booking:
            return None

        expires_at = booking.get('expires_at')
        if expires_at:
            try:
                exp = datetime.fromisoformat(expires_at) if isinstance(expires_at, str) else expires_at
                if exp < datetime.utcnow():
                    demo_booking_repo.update(booking['id'], {
                        'status': DemoBookingStatus.EXPIRED.value,
                        'updated_at': datetime.utcnow().isoformat()
                    })
                    return None
            except (ValueError, TypeError):
                pass

        meta = booking.get('metadata', {}) or {}
        return {
            'success': True,
            'token': booking.get('booking_token'),
            'session_token': booking.get('session_token'),
            'booking': {
                'time': booking.get('preferred_time', ''),
                'date': booking.get('preferred_date', ''),
                'name': booking.get('full_name', ''),
                'institution': booking.get('institution', ''),
                'email': booking.get('email', ''),
                'phone': booking.get('phone', ''),
                'status': booking.get('status', ''),
                'email_status': meta.get('email_status', 'pending') if isinstance(meta, dict) else 'pending',
            }
        }

    def get_booking_by_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Retrieve booking by secure token with expiry check."""
        if not token:
            return None

        sql_booking = booking_repo.get_by_token(token)
        if sql_booking:
            result = self._serialize_sql_booking(sql_booking)
            result['session_token'] = sql_booking.session.session_token if sql_booking.session else None
            return result

        booking = demo_booking_repo.get_by_token(token)
        if not booking:
            return None

        status = booking.get('status', '')
        if status in (DemoBookingStatus.EXPIRED.value, DemoBookingStatus.CANCELLED.value):
            return None

        expires_at = booking.get('expires_at')
        if expires_at:
            try:
                exp = datetime.fromisoformat(expires_at) if isinstance(expires_at, str) else expires_at
                if exp < datetime.utcnow():
                    demo_booking_repo.update(booking['id'], {
                        'status': DemoBookingStatus.EXPIRED.value,
                        'updated_at': datetime.utcnow().isoformat()
                    })
                    return None
            except (ValueError, TypeError):
                pass

        meta = booking.get('metadata', {}) or {}
        return {
            'token': token,
            'name': booking.get('full_name', ''),
            'email': booking.get('email', ''),
            'institution': booking.get('institution', ''),
            'time': booking.get('preferred_time', ''),
            'date': booking.get('preferred_date', ''),
            'phone': booking.get('phone', ''),
            'status': status,
            'created_at': booking.get('created_at', ''),
            'meeting_url': booking.get('meeting_url', ''),
            'onboarding_progress': booking.get('onboarding_progress', {}),
            'onboarding_completed': booking.get('onboarding_completed', False),
            'session_token': booking.get('session_token'),
            'email_status': meta.get('email_status', 'pending') if isinstance(meta, dict) else 'pending',
        }

    def get_booking_by_session_token(self, session_token: str) -> Optional[Dict[str, Any]]:
        """Retrieve booking by onboarding session token."""
        if not session_token:
            return None

        sql_booking = booking_repo.get_by_session_token(session_token)
        if sql_booking:
            return self._serialize_sql_booking(sql_booking)

        booking = demo_booking_repo.get_active_by_session_token(session_token)
        if not booking:
            return None

        status = booking.get('status', '')
        if status in (DemoBookingStatus.EXPIRED.value, DemoBookingStatus.CANCELLED.value):
            return None

        expires_at = booking.get('expires_at')
        if expires_at:
            try:
                exp = datetime.fromisoformat(expires_at) if isinstance(expires_at, str) else expires_at
                if exp < datetime.utcnow():
                    demo_booking_repo.update(booking['id'], {
                        'status': DemoBookingStatus.EXPIRED.value,
                        'updated_at': datetime.utcnow().isoformat()
                    })
                    return None
            except (ValueError, TypeError):
                pass

        meta = booking.get('metadata', {}) or {}
        return {
            'token': booking.get('booking_token') or booking.get('token'),
            'name': booking.get('full_name', ''),
            'email': booking.get('email', ''),
            'institution': booking.get('institution', ''),
            'time': booking.get('preferred_time', ''),
            'date': booking.get('preferred_date', ''),
            'phone': booking.get('phone', ''),
            'status': status,
            'created_at': booking.get('created_at', ''),
            'meeting_url': booking.get('meeting_url', ''),
            'onboarding_progress': booking.get('onboarding_progress', {}),
            'onboarding_completed': booking.get('onboarding_completed', False),
            'session_token': session_token,
            'email_status': meta.get('email_status', 'pending') if isinstance(meta, dict) else 'pending',
        }

    def _serialize_sql_booking(self, sql_booking: SQLDemoBooking) -> Dict[str, Any]:
        meta = sql_booking.metadata_ or {}
        return {
            'token': sql_booking.booking_token,
            'name': sql_booking.demo_lead.full_name if sql_booking.demo_lead else '',
            'email': sql_booking.demo_lead.email if sql_booking.demo_lead else '',
            'institution': sql_booking.demo_lead.institution_name if sql_booking.demo_lead else '',
            'time': sql_booking.scheduled_timezone or '',
            'date': sql_booking.scheduled_at_utc.isoformat() if sql_booking.scheduled_at_utc else '',
            'phone': sql_booking.demo_lead.phone if sql_booking.demo_lead else '',
            'status': sql_booking.status,
            'created_at': sql_booking.created_at.isoformat() if sql_booking.created_at else '',
            'meeting_url': sql_booking.meeting_url,
            'onboarding_progress': sql_booking.session.progress if sql_booking.session else {},
            'onboarding_completed': sql_booking.status == DemoBookingStatus.SCHEDULED.value,
            'session_token': sql_booking.session.session_token if sql_booking.session else None,
            'email_status': meta.get('email_status', 'pending'),
            'email_error': meta.get('email_error', ''),
        }

    def update_booking(self, token: str, data: Dict[str, Any]) -> bool:
        """Update booking fields by token."""
        sql_booking = booking_repo.get_by_token(token)
        if sql_booking:
            update_data = {k: v for k, v in data.items() if v is not None}
            if not update_data:
                return False
            for key, value in update_data.items():
                if hasattr(sql_booking, key):
                    setattr(sql_booking, key, value)
            sql_booking.updated_at = datetime.utcnow()
            booking_repo._commit()
            booking_repo._cleanup()
            return True

        booking = demo_booking_repo.get_by_token(token)
        if not booking:
            return False
        update_data = {k: v for k, v in data.items() if v is not None}
        update_data['updated_at'] = datetime.utcnow().isoformat()
        return demo_booking_repo.update(booking['id'], update_data)

    def update_status(self, token: str, status: str) -> bool:
        """Transition booking to a new lifecycle state."""
        sql_booking = booking_repo.get_by_token(token)
        if sql_booking:
            sql_booking.status = status
            sql_booking.updated_at = datetime.utcnow()
            booking_repo._commit()
            booking_repo._cleanup()
            return True
        return demo_booking_repo.update_status(token, status)

    def mark_onboarding_complete(self, token: str) -> bool:
        """Mark onboarding as complete and transition to scheduled state."""
        return self.update_booking(token, {
            'status': DemoBookingStatus.SCHEDULED.value
        })


demo_booking_service = DemoBookingService()
