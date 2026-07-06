import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
import secrets
import string

from src.domain.entities import Voucher, UserRole
from src.infrastructure.pg_repositories import pg_repos
from src.infrastructure.models import Voucher as PGVoucher

logger = logging.getLogger(__name__)


class VoucherService:
    """Service for managing vouchers/invitation codes"""

    def __init__(self):
        pass

    def generate_voucher(self, email: str, role: UserRole, institution_id: str,
                         expires_at: Optional[datetime] = None) -> Voucher:
        """Generate a new voucher"""
        try:
            code = self._generate_voucher_code()
            now = datetime.utcnow()

            pg_voucher = PGVoucher(
                id=str(secrets.token_hex(8)),
                code=code,
                role=role,
                institution_id=institution_id,
                email_binding=email,
                is_used=False,
                created_at=now
            )

            pg_repos.voucher.create(pg_voucher)

            voucher = Voucher(
                id=pg_voucher.id,
                code=code,
                email=email,
                role=role,
                institution_id=institution_id,
                is_used=False,
                created_at=now,
                expires_at=expires_at or (now + timedelta(days=7))
            )

            logger.info(f"Generated voucher {code} for {email}")
            return voucher

        except Exception as e:
            logger.error(f"Voucher generation failed: {str(e)}")
            raise Exception(f"Failed to generate voucher: {str(e)}")

    def validate_voucher(self, code: str) -> Optional[Voucher]:
        """Validate a voucher code"""
        try:
            voucher = pg_repos.voucher.get_by_code(code)
            if not voucher or voucher.is_used:
                return None

            expires_at = voucher.created_at + timedelta(days=7) if voucher.created_at else datetime.utcnow()
            if datetime.utcnow() > expires_at:
                return None

            return Voucher(
                id=voucher.id,
                code=voucher.code,
                email=voucher.email_binding or '',
                role=voucher.role,
                institution_id=voucher.institution_id,
                is_used=voucher.is_used,
                created_at=voucher.created_at or datetime.utcnow(),
                expires_at=expires_at
            )

        except Exception as e:
            logger.error(f"Voucher validation failed: {str(e)}")
            return None

    def use_voucher(self, code: str, user_email: str) -> bool:
        """Mark a voucher as used"""
        try:
            voucher = self.validate_voucher(code)
            if not voucher:
                return False

            if voucher.email != user_email:
                return False

            return pg_repos.voucher.mark_as_used_by_code(code, voucher.id)

        except Exception as e:
            logger.error(f"Voucher usage failed: {str(e)}")
            return False

    def _generate_voucher_code(self) -> str:
        characters = string.ascii_uppercase + string.digits
        return ''.join(secrets.choice(characters) for _ in range(8))

    def get_user_vouchers(self, email: str) -> List[Dict[str, Any]]:
        """Get all vouchers for a user"""
        try:
            vouchers = pg_repos.voucher.query(email_binding=email)

            return [{
                'code': v.code,
                'role': v.role.value if hasattr(v.role, 'value') else str(v.role),
                'is_used': v.is_used,
                'created_at': v.created_at.isoformat() if v.created_at else None,
                'expires_at': (v.created_at + timedelta(days=7)).isoformat() if v.created_at else None
            } for v in vouchers]

        except Exception as e:
            logger.error(f"Failed to get user vouchers: {str(e)}")
            return []