import logging
import re
import secrets
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List

from src.domain.entities import DemoBooking, DemoBookingStatus
from src.infrastructure.repositories import demo_booking_repo

logger = logging.getLogger(__name__)

EMAIL_REGEX = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
PHONE_REGEX = re.compile(r'^[\d\s\-\+\(\)]{7,20}$')
NAME_REGEX = re.compile(r'^[a-zA-Z\s\'.\-]{2,100}$')


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

    def check_existing_booking(self, email: str) -> Optional[Dict[str, Any]]:
        """Check if email already has an active booking. Returns the booking if found."""
        existing = demo_booking_repo.get_active_by_email(email)
        if existing:
            return existing
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

        booking = DemoBooking(
            id=None,
            email=email,
            full_name=data['fullName'].strip(),
            phone=data['phone'].strip(),
            institution=data['institution'].strip(),
            institution_type=data.get('institutionType', '').strip() or None,
            number_of_students=data.get('numberOfStudents') if data.get('numberOfStudents') else None,
            preferred_date=data.get('date', ''),
            preferred_time=data.get('time', ''),
            status=DemoBookingStatus.CONFIRMED.value,
            booking_token=None,
            csrf_token=None,
            session_token=None,
            meeting_url=None,
            meeting_provider=None,
            onboarding_progress={},
            onboarding_completed=False,
            metadata={
                'source': 'schedule-demo',
                'ip_address': data.get('_ip', ''),
                'user_agent': data.get('_ua', '')
            },
            created_at=None,
            updated_at=None,
            expires_at=datetime.utcnow() + timedelta(days=30),
            confirmed_at=datetime.utcnow(),
            scheduled_at=None
        )

        booking_dict = demo_booking_repo.to_dict(booking)
        doc_id = demo_booking_repo.create(booking_dict, document_id=booking.id)
        if not doc_id:
            logger.error(f"Failed to persist booking for {email}")
            return {'success': False, 'message': 'Failed to save booking. Please try again.'}

        logger.info(f"Demo booking created: {email} -> token={booking.booking_token}")
        return {
            'success': True,
            'token': booking.booking_token,
            'booking': {
                'time': booking.preferred_time,
                'date': booking.preferred_date,
                'name': booking.full_name,
                'institution': booking.institution
            }
        }

    def restore_booking(self, email: str) -> Optional[Dict[str, Any]]:
        """Restore a user's existing booking by email for continuity."""
        email = email.strip().lower()
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

        return {
            'success': True,
            'token': booking.get('booking_token'),
            'booking': {
                'time': booking.get('preferred_time', ''),
                'date': booking.get('preferred_date', ''),
                'name': booking.get('full_name', ''),
                'institution': booking.get('institution', ''),
                'email': booking.get('email', ''),
                'phone': booking.get('phone', ''),
                'status': booking.get('status', '')
            }
        }

    def get_booking_by_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Retrieve booking by secure token with expiry check."""
        if not token:
            return None
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
            'onboarding_completed': booking.get('onboarding_completed', False)
        }

    def update_booking(self, token: str, data: Dict[str, Any]) -> bool:
        """Update booking fields by token."""
        booking = demo_booking_repo.get_by_token(token)
        if not booking:
            return False
        update_data = {k: v for k, v in data.items() if v is not None}
        update_data['updated_at'] = datetime.utcnow().isoformat()
        return demo_booking_repo.update(booking['id'], update_data)

    def update_status(self, token: str, status: str) -> bool:
        """Transition booking to a new lifecycle state."""
        return demo_booking_repo.update_status(token, status)

    def mark_onboarding_complete(self, token: str) -> bool:
        """Mark onboarding as complete and transition to scheduled state."""
        return self.update_booking(token, {
            'onboarding_completed': True,
            'status': DemoBookingStatus.SCHEDULED.value
        })


demo_booking_service = DemoBookingService()
