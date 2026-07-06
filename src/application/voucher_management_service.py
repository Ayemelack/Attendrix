import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
import secrets
import string
import uuid

from src.domain.entities import UserRole
from src.infrastructure.pg_repositories import pg_repos
from src.infrastructure.models import Voucher

logger = logging.getLogger(__name__)


class VoucherManagementService:
    """Professional voucher management system with PostgreSQL implementation"""

    def __init__(self):
        self.voucher_length = 8
        self.expiry_days = 30

    def generate_voucher_batch(self, role: UserRole, institution_id: str,
                               quantity: int = 10, email_binding: Optional[str] = None,
                               fixed_code: Optional[str] = None,
                               generated_by: str = 'system') -> List[Dict[str, Any]]:
        """Generate multiple vouchers for bulk distribution"""
        try:
            vouchers = []
            batch_id = f"batch_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"

            for i in range(quantity):
                voucher_code = fixed_code if fixed_code and i == 0 else self._generate_secure_voucher_code()
                now = datetime.utcnow()

                voucher = Voucher(
                    id=str(uuid.uuid4()),
                    code=voucher_code,
                    role=role if isinstance(role, UserRole) else UserRole(role),
                    institution_id=institution_id,
                    email_binding=email_binding,
                    is_used=False,
                    created_at=now
                )

                pg_repos.voucher.create(voucher)

                voucher_dict = {
                    'id': voucher.id,
                    'code': voucher.code,
                    'role': voucher.role.value if hasattr(voucher.role, 'value') else str(voucher.role),
                    'institution_id': voucher.institution_id,
                    'email_binding': voucher.email_binding,
                    'is_used': voucher.is_used,
                    'created_at': now.isoformat(),
                    'expires_at': (now + timedelta(days=self.expiry_days)).isoformat(),
                    'generated_by': generated_by,
                    'batch_id': batch_id
                }
                vouchers.append(voucher_dict)

            logger.info(f"Generated {quantity} vouchers for role {role.value if isinstance(role, UserRole) else role}")
            return vouchers

        except Exception as e:
            logger.error(f"Voucher batch generation failed: {str(e)}")
            return []

    def validate_voucher_for_registration(self, voucher_code: str, email: str,
                                          requested_role: UserRole, institution_id: str) -> Dict[str, Any]:
        """Comprehensive voucher validation for registration"""
        try:
            if not self._is_valid_voucher_format(voucher_code):
                return {
                    'valid': False,
                    'error': 'Invalid voucher format',
                    'error_code': 'INVALID_FORMAT'
                }

            voucher = pg_repos.voucher.get_by_code(voucher_code)
            if not voucher:
                return {
                    'valid': False,
                    'error': 'Voucher code not found',
                    'error_code': 'NOT_FOUND'
                }

            if getattr(voucher, 'revoked', False):
                return {
                    'valid': False,
                    'error': 'Voucher has been revoked',
                    'error_code': 'REVOKED'
                }

            if voucher.is_used:
                return {
                    'valid': False,
                    'error': 'Voucher has already been used',
                    'error_code': 'ALREADY_USED'
                }

            if voucher.institution_id != institution_id:
                return {
                    'valid': False,
                    'error': 'Voucher is not valid for this institution',
                    'error_code': 'INSTITUTION_MISMATCH'
                }

            voucher_role = voucher.role.value if hasattr(voucher.role, 'value') else str(voucher.role)
            req_role = requested_role.value if hasattr(requested_role, 'value') else str(requested_role)
            if voucher_role != req_role:
                return {
                    'valid': False,
                    'error': f'Voucher is for {voucher_role.replace("_", " ").title()} role, not {req_role.replace("_", " ").title()}',
                    'error_code': 'ROLE_MISMATCH'
                }

            if voucher.email_binding and voucher.email_binding != email:
                return {
                    'valid': False,
                    'error': 'Voucher is assigned to a different email address',
                    'error_code': 'EMAIL_MISMATCH'
                }

            return {
                'valid': True,
                'voucher_id': voucher.id,
                'role': voucher.role if hasattr(voucher.role, 'value') else UserRole(voucher_role),
                'institution_id': voucher.institution_id,
                'message': 'Voucher is valid for registration'
            }

        except Exception as e:
            logger.error(f"Voucher validation error: {str(e)}")
            return {
                'valid': False,
                'error': 'Voucher validation failed',
                'error_code': 'SYSTEM_ERROR'
            }

    def consume_voucher(self, voucher_code: str, user_id: str) -> bool:
        """Mark voucher as used after successful registration"""
        try:
            return pg_repos.voucher.mark_as_used_by_code(voucher_code, user_id)

        except Exception as e:
            logger.error(f"Voucher consumption error: {str(e)}")
            return False

    def get_voucher_statistics(self, institution_id: str) -> Dict[str, Any]:
        """Get voucher usage statistics"""
        try:
            all_vouchers = pg_repos.voucher.query(institution_id=institution_id)

            now = datetime.utcnow()
            used = [v for v in all_vouchers if v.is_used]
            revoked = [v for v in all_vouchers if getattr(v, 'revoked', False)]
            active_but_expired = [
                v for v in all_vouchers
                if not v.is_used and not getattr(v, 'revoked', False)
                and v.created_at + timedelta(days=self.expiry_days) < now
            ]

            stats = {
                'total_generated': len(all_vouchers),
                'used': len(used),
                'unused': len(all_vouchers) - len(used) - len(active_but_expired) - len(revoked),
                'expired': len(active_but_expired),
                'revoked': len(revoked),
                'by_role': {},
                'recent_activity': []
            }

            for voucher in all_vouchers:
                role = voucher.role.value if hasattr(voucher.role, 'value') else str(voucher.role)
                stats['by_role'][role] = stats['by_role'].get(role, 0) + 1

            recent = sorted(all_vouchers, key=lambda x: x.created_at or datetime.min, reverse=True)[:10]
            stats['recent_activity'] = [
                {
                    'id': v.id,
                    'code': v.code,
                    'role': v.role.value if hasattr(v.role, 'value') else str(v.role),
                    'is_used': v.is_used,
                    'created_at': v.created_at.isoformat() if v.created_at else None
                }
                for v in recent
            ]

            return stats

        except Exception as e:
            logger.error(f"Voucher statistics error: {str(e)}")
            return {}

    def list_vouchers(self, institution_id: str, page: int = 1, per_page: int = 20,
                      search: str = '', status_filter: str = '', role_filter: str = '') -> Dict[str, Any]:
        """List vouchers for an institution with pagination, search and filters"""
        try:
            all_vouchers = pg_repos.voucher.query(institution_id=institution_id)

            now = datetime.utcnow()
            for v in all_vouchers:
                v._expired = now > v.created_at + timedelta(days=self.expiry_days)
                revoked = getattr(v, 'revoked', False)
                v._status = 'revoked' if revoked else ('used' if v.is_used else ('expired' if v._expired else 'active'))
                if v.used_by:
                    try:
                        user = pg_repos.user.get(v.used_by)
                        v.used_by_email = user.email if user else v.used_by
                    except Exception:
                        v.used_by_email = v.used_by

            if search:
                s = search.upper()
                filtered = []
                for v in all_vouchers:
                    used_by_email = getattr(v, 'used_by_email', '') or ''
                    if (s in v.code.upper() or
                            s in (v.used_by or '').upper() or
                            s in used_by_email.upper()):
                        filtered.append(v)
                all_vouchers = filtered

            if status_filter:
                all_vouchers = [v for v in all_vouchers if v._status == status_filter]

            if role_filter:
                all_vouchers = [
                    v for v in all_vouchers
                    if (v.role.value if hasattr(v.role, 'value') else str(v.role)) == role_filter
                ]

            all_vouchers.sort(key=lambda x: x.created_at or datetime.min, reverse=True)
            total = len(all_vouchers)
            total_pages = max(1, (total + per_page - 1) // per_page)
            page = max(1, min(page, total_pages))
            start_idx = (page - 1) * per_page
            end_idx = start_idx + per_page
            items = all_vouchers[start_idx:end_idx]

            used = sum(1 for v in all_vouchers if v.is_used)
            unused = sum(1 for v in all_vouchers if not v.is_used and not getattr(v, 'revoked', False) and not v._expired)
            expired = sum(1 for v in all_vouchers if v._expired and not v.is_used)
            revoked = sum(1 for v in all_vouchers if getattr(v, 'revoked', False))

            item_dicts = []
            for v in items:
                item = {
                    'id': v.id,
                    'code': v.code,
                    'role': v.role.value if hasattr(v.role, 'value') else str(v.role),
                    'is_used': v.is_used,
                    'used_by': v.used_by,
                    'used_by_email': getattr(v, 'used_by_email', v.used_by),
                    'created_at': v.created_at.isoformat() if v.created_at else None,
                    '_status': v._status,
                    '_expired': v._expired,
                }
                item_dicts.append(item)

            return {
                'vouchers': item_dicts,
                'total': total,
                'page': page,
                'total_pages': total_pages,
                'stats': {
                    'total': total,
                    'used': used,
                    'unused': unused,
                    'expired': expired,
                    'revoked': revoked,
                },
                'statuses': ['active', 'used', 'expired', 'revoked'],
                'roles': ['student', 'lecturer', 'institutional_admin'],
            }

        except Exception as e:
            logger.error(f"List vouchers error: {str(e)}")
            return {
                'vouchers': [], 'total': 0, 'page': 1, 'total_pages': 1,
                'stats': {}, 'statuses': ['active', 'used', 'expired', 'revoked'],
                'roles': ['student', 'lecturer', 'institutional_admin']
            }

    def revoke_voucher(self, voucher_id: str) -> bool:
        """Revoke a voucher so it can no longer be used"""
        try:
            voucher = pg_repos.voucher.get(voucher_id)
            if not voucher:
                return False
            voucher.revoked = True
            voucher.revoked_at = datetime.utcnow()
            pg_repos.voucher.update(voucher)
            logger.info(f"Voucher {voucher_id} revoked")
            return True
        except Exception as e:
            logger.error(f"Revoke voucher error: {str(e)}")
            return False

    def _generate_secure_voucher_code(self) -> str:
        characters = string.ascii_uppercase + string.digits
        return ''.join(secrets.choice(characters) for _ in range(self.voucher_length))

    def _is_valid_voucher_format(self, voucher_code: str) -> bool:
        if not voucher_code:
            return False
        if len(voucher_code) != self.voucher_length:
            return False
        if not voucher_code.isalnum() or not voucher_code.isupper():
            return False
        return True