import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
import secrets
import string

from src.domain.entities import UserRole

logger = logging.getLogger(__name__)


class VoucherManagementService:
    """Professional voucher management system with real database implementation"""
    
    def __init__(self, firebase_service):
        self.firebase_service = firebase_service
        self.voucher_length = 8
        self.expiry_days = 30
    
    def generate_voucher_batch(self, role: UserRole, institution_id: str, 
                            quantity: int = 10, email_binding: Optional[str] = None,
                            fixed_code: Optional[str] = None,
                            generated_by: str = 'system') -> List[Dict[str, Any]]:
        """Generate multiple vouchers for bulk distribution"""
        try:
            vouchers = []
            
            for i in range(quantity):
                voucher_code = fixed_code if fixed_code and i == 0 else self._generate_secure_voucher_code()
                voucher_id = str(secrets.token_hex(8))
                
                voucher_data = {
                    'id': voucher_id,
                    'code': voucher_code,
                    'role': role.value,
                    'institution_id': institution_id,
                    'email_binding': email_binding,  # Optional email binding
                    'is_used': False,
                    'created_at': datetime.utcnow().isoformat(),
                    'expires_at': (datetime.utcnow() + timedelta(days=self.expiry_days)).isoformat(),
                    'generated_by': generated_by,
                    'batch_id': f"batch_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
                }
                
                # Store in database
                self.firebase_service.create_document('vouchers', voucher_data, voucher_id)
                vouchers.append(voucher_data)
            
            logger.info(f"Generated {quantity} vouchers for role {role.value}")
            return vouchers
            
        except Exception as e:
            logger.error(f"Voucher batch generation failed: {str(e)}")
            return []
    
    def validate_voucher_for_registration(self, voucher_code: str, email: str, 
                                    requested_role: UserRole, institution_id: str) -> Dict[str, Any]:
        """Comprehensive voucher validation for registration"""
        try:
            # Check voucher format
            if not self._is_valid_voucher_format(voucher_code):
                return {
                    'valid': False,
                    'error': 'Invalid voucher format',
                    'error_code': 'INVALID_FORMAT'
                }
            
            # Query voucher from database
            vouchers = self.firebase_service.query_documents(
                'vouchers',
                filters=[{'field': 'code', 'value': voucher_code}]
            )
            
            if not vouchers:
                return {
                    'valid': False,
                    'error': 'Voucher code not found',
                    'error_code': 'NOT_FOUND'
                }
            
            voucher = vouchers[0]
            
            # Check if revoked
            if voucher.get('revoked', False):
                return {
                    'valid': False,
                    'error': 'Voucher has been revoked',
                    'error_code': 'REVOKED'
                }
            
            # Check if already used
            if voucher.get('is_used', False):
                return {
                    'valid': False,
                    'error': 'Voucher has already been used',
                    'error_code': 'ALREADY_USED'
                }
            
            # Check expiry
            expiry_date = datetime.fromisoformat(voucher['expires_at'])
            if datetime.utcnow() > expiry_date:
                return {
                    'valid': False,
                    'error': 'Voucher has expired',
                    'error_code': 'EXPIRED'
                }
            
            # Check institution match
            if voucher['institution_id'] != institution_id:
                return {
                    'valid': False,
                    'error': 'Voucher is not valid for this institution',
                    'error_code': 'INSTITUTION_MISMATCH'
                }
            
            # Check role match
            if voucher['role'] != requested_role.value:
                return {
                    'valid': False,
                    'error': f'Voucher is for {voucher["role"].replace("_", " ").title()} role, not {requested_role.value.replace("_", " ").title()}',
                    'error_code': 'ROLE_MISMATCH'
                }
            
            # Check email binding if exists
            if voucher.get('email_binding') and voucher['email_binding'] != email:
                return {
                    'valid': False,
                    'error': 'Voucher is assigned to a different email address',
                    'error_code': 'EMAIL_MISMATCH'
                }
            
            # All validations passed
            return {
                'valid': True,
                'voucher_id': voucher['id'],
                'role': UserRole(voucher['role']),
                'institution_id': voucher['institution_id'],
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
            # Get voucher
            vouchers = self.firebase_service.query_documents(
                'vouchers',
                filters=[{'field': 'code', 'value': voucher_code}]
            )
            
            if not vouchers:
                return False
            
            voucher = vouchers[0]
            
            # Mark as used
            self.firebase_service.update_document('vouchers', voucher['id'], {
                'is_used': True,
                'used_by': user_id,
                'used_at': datetime.utcnow().isoformat()
            })
            
            logger.info(f"Voucher {voucher_code} consumed by user {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Voucher consumption error: {str(e)}")
            return False
    
    def get_voucher_statistics(self, institution_id: str) -> Dict[str, Any]:
        """Get voucher usage statistics"""
        try:
            all_vouchers = self.firebase_service.query_documents(
                'vouchers',
                filters=[{'field': 'institution_id', 'value': institution_id}]
            )
            
            now = datetime.utcnow()
            used = [v for v in all_vouchers if v.get('is_used')]
            revoked = [v for v in all_vouchers if v.get('revoked')]
            expired = [v for v in all_vouchers if not v.get('is_used') and not v.get('revoked') and now > datetime.fromisoformat(v['expires_at'])]
            
            stats = {
                'total_generated': len(all_vouchers),
                'used': len(used),
                'unused': len(all_vouchers) - len(used) - len(expired) - len(revoked),
                'expired': len(expired),
                'revoked': len(revoked),
                'by_role': {},
                'recent_activity': []
            }
            
            for voucher in all_vouchers:
                role = voucher.get('role', 'unknown')
                stats['by_role'][role] = stats['by_role'].get(role, 0) + 1
            
            recent_vouchers = sorted(all_vouchers,
                                 key=lambda x: x.get('created_at', ''),
                                 reverse=True)[:10]
            stats['recent_activity'] = recent_vouchers
            
            return stats
            
        except Exception as e:
            logger.error(f"Voucher statistics error: {str(e)}")
            return {}
    
    def list_vouchers(self, institution_id: str, page: int = 1, per_page: int = 20,
                     search: str = '', status_filter: str = '', role_filter: str = '') -> Dict[str, Any]:
        """List vouchers for an institution with pagination, search and filters"""
        try:
            all_vouchers = self.firebase_service.query_documents(
                'vouchers',
                filters=[{'field': 'institution_id', 'value': institution_id}]
            )
            
            now = datetime.utcnow()
            for v in all_vouchers:
                v['_expired'] = now > datetime.fromisoformat(v['expires_at'])
                v['_status'] = 'revoked' if v.get('revoked') else ('used' if v.get('is_used') else ('expired' if v['_expired'] else 'active'))
                # Resolve used_by email
                if v.get('used_by'):
                    try:
                        user_doc = self.firebase_service.get_document('users', v['used_by'])
                        if user_doc:
                            v['used_by_email'] = user_doc.get('email', v['used_by'])
                        else:
                            v['used_by_email'] = v['used_by']
                    except:
                        v['used_by_email'] = v['used_by']
            
            if search:
                s = search.upper()
                all_vouchers = [v for v in all_vouchers if s in v.get('code', '').upper() or
                                s in (v.get('used_by') or '').upper() or
                                s in (v.get('used_by_email') or '').upper()]
            
            if status_filter:
                all_vouchers = [v for v in all_vouchers if v['_status'] == status_filter]
            
            if role_filter:
                all_vouchers = [v for v in all_vouchers if v.get('role') == role_filter]
            
            all_vouchers.sort(key=lambda x: x.get('created_at', ''), reverse=True)
            total = len(all_vouchers)
            total_pages = max(1, (total + per_page - 1) // per_page)
            page = max(1, min(page, total_pages))
            start = (page - 1) * per_page
            end = start + per_page
            items = all_vouchers[start:end]
            
            used = sum(1 for v in all_vouchers if v.get('is_used'))
            unused = sum(1 for v in all_vouchers if not v.get('is_used') and not v.get('revoked') and not v['_expired'])
            expired = sum(1 for v in all_vouchers if v['_expired'] and not v.get('is_used'))
            revoked = sum(1 for v in all_vouchers if v.get('revoked'))
            
            return {
                'vouchers': items,
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
            return {'vouchers': [], 'total': 0, 'page': 1, 'total_pages': 1, 'stats': {}, 'statuses': ['active', 'used', 'expired', 'revoked'], 'roles': ['student', 'lecturer', 'institutional_admin']}

    def revoke_voucher(self, voucher_id: str) -> bool:
        """Revoke a voucher so it can no longer be used"""
        try:
            doc = self.firebase_service.get_document('vouchers', voucher_id)
            if not doc:
                return False
            self.firebase_service.update_document('vouchers', voucher_id, {
                'revoked': True,
                'revoked_at': datetime.utcnow().isoformat()
            })
            logger.info(f"Voucher {voucher_id} revoked")
            return True
        except Exception as e:
            logger.error(f"Revoke voucher error: {str(e)}")
            return False

    def _generate_secure_voucher_code(self) -> str:
        """Generate cryptographically secure voucher code"""
        # Use uppercase letters and numbers only
        characters = string.ascii_uppercase + string.digits
        return ''.join(secrets.choice(characters) for _ in range(self.voucher_length))
    
    def _is_valid_voucher_format(self, voucher_code: str) -> bool:
        """Validate voucher code format"""
        if not voucher_code:
            return False
        
        # Must be exactly 8 characters
        if len(voucher_code) != self.voucher_length:
            return False
        
        # Must be alphanumeric uppercase
        if not voucher_code.isalnum() or not voucher_code.isupper():
            return False
        
        return True
