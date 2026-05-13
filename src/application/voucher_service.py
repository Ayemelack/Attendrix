import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
import secrets
import string

from src.domain.entities import Voucher, UserRole

logger = logging.getLogger(__name__)


class VoucherService:
    """Service for managing vouchers/invitation codes"""
    
    def __init__(self, firebase_service):
        self.firebase_service = firebase_service
    
    def generate_voucher(self, email: str, role: UserRole, institution_id: str) -> Voucher:
        """Generate a new voucher"""
        try:
            # Generate unique voucher code
            code = self._generate_voucher_code()
            
            # Create voucher entity
            voucher = Voucher(
                id=str(secrets.token_hex(8)),
                code=code,
                email=email,
                role=role,
                institution_id=institution_id,
                is_used=False,
                created_at=datetime.utcnow(),
                expires_at=expires_at or (datetime.utcnow() + timedelta(days=7))
            )
            
            # Store voucher in database
            voucher_data = {
                'id': voucher.id,
                'code': voucher.code,
                'email': voucher.email,
                'role': voucher.role,
                'institution_id': voucher.institution_id,
                'is_used': voucher.is_used,
                'created_at': voucher.created_at.isoformat(),
                'expires_at': voucher.expires_at.isoformat()
            }
            
            self.firebase_service.create_document('vouchers', voucher_data, voucher.id)
            
            logger.info(f"Generated voucher {code} for {email}")
            return voucher
            
        except Exception as e:
            logger.error(f"Voucher generation failed: {str(e)}")
            raise Exception(f"Failed to generate voucher: {str(e)}")
    
    def validate_voucher(self, code: str) -> Optional[Voucher]:
        """Validate a voucher code"""
        try:
            # Query for unused voucher with matching code
            vouchers = self.firebase_service.query_documents(
                'vouchers',
                filters=[
                    {'field': 'code', 'value': code},
                    {'field': 'is_used', 'value': False}
                ]
            )
            
            if not vouchers:
                return None
            
            voucher_data = vouchers[0]
            
            # Check if voucher has expired
            expires_at = datetime.fromisoformat(voucher_data['expires_at'])
            if datetime.utcnow() > expires_at:
                return None
            
            return Voucher(
                id=voucher_data['id'],
                code=voucher_data['code'],
                email=voucher_data['email'],
                role=UserRole(voucher_data['role']),
                institution_id=voucher_data['institution_id'],
                is_used=voucher_data['is_used'],
                created_at=datetime.fromisoformat(voucher_data['created_at']),
                expires_at=expires_at
            )
            
        except Exception as e:
            logger.error(f"Voucher validation failed: {str(e)}")
            return None
    
    def use_voucher(self, code: str, user_email: str) -> bool:
        """Mark a voucher as used"""
        try:
            # Find the voucher
            voucher = self.validate_voucher(code)
            if not voucher:
                return False
            
            # Check if voucher email matches user email
            if voucher.email != user_email:
                return False
            
            # Mark voucher as used
            self.firebase_service.update_document('vouchers', voucher.id, {
                'is_used': True,
                'used_at': datetime.utcnow().isoformat()
            })
            
            logger.info(f"Voucher {code} used by {user_email}")
            return True
            
        except Exception as e:
            logger.error(f"Voucher usage failed: {str(e)}")
            return False
    
    def _generate_voucher_code(self) -> str:
        """Generate a unique voucher code"""
        # Generate 8-character alphanumeric code
        characters = string.ascii_uppercase + string.digits
        return ''.join(secrets.choice(characters) for _ in range(8))
    
    def get_user_vouchers(self, email: str) -> List[Dict[str, Any]]:
        """Get all vouchers for a user"""
        try:
            vouchers = self.firebase_service.query_documents(
                'vouchers',
                filters=[{'field': 'email', 'value': email}]
            )
            
            return [{
                'code': v['code'],
                'role': v['role'],
                'is_used': v['is_used'],
                'created_at': v['created_at'],
                'expires_at': v['expires_at']
            } for v in vouchers]
            
        except Exception as e:
            logger.error(f"Failed to get user vouchers: {str(e)}")
            return []
