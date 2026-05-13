import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import secrets
import string

from src.domain.entities import UserRole

logger = logging.getLogger(__name__)


class VoucherSeeder:
    """System voucher seeder for initial bootstrap"""
    
    def __init__(self, firebase_service):
        self.firebase_service = firebase_service
    
    def generate_seed_vouchers(self) -> Dict[str, Any]:
        """Generate initial seed vouchers for system bootstrap"""
        try:
            seed_vouchers = []
            
            # Generate 1 Institutional Admin voucher with FIXED CODE
            admin_voucher = self._generate_single_voucher(
                role=UserRole.INSTITUTIONAL_ADMIN,
                institution_id='inst_001',
                email_binding='admin@attendrix.demo',
                fixed_code='ADMIN123'
            )
            seed_vouchers.append(admin_voucher)
            
            # Generate 3 Lecturer vouchers with FIXED CODES
            lecturer_emails = [
                'lecturer1@attendrix.demo',
                'lecturer2@attendrix.demo', 
                'lecturer3@attendrix.demo'
            ]
            lecturer_codes = ['LECT4567', 'LECT4568', 'LECT4569']
            
            for i, email in enumerate(lecturer_emails):
                lecturer_voucher = self._generate_single_voucher(
                    role=UserRole.LECTURER,
                    institution_id='inst_001',
                    email_binding=email,
                    fixed_code=lecturer_codes[i]
                )
                seed_vouchers.append(lecturer_voucher)
            
            # Generate 10 Student vouchers with FIXED CODES
            student_emails = [
                'student1@attendrix.demo',
                'student2@attendrix.demo',
                'student3@attendrix.demo',
                'student4@attendrix.demo',
                'student5@attendrix.demo',
                'student6@attendrix.demo',
                'student7@attendrix.demo',
                'student8@attendrix.demo',
                'student9@attendrix.demo',
                'student10@attendrix.demo'
            ]
            student_codes = ['STUD7890', 'STUD7891', 'STUD7892', 'STUD7893', 'STUD7894', 'STUD7895', 'STUD7896', 'STUD7897', 'STUD7898', 'STUD7899']
            
            for i, email in enumerate(student_emails):
                student_voucher = self._generate_single_voucher(
                    role=UserRole.STUDENT,
                    institution_id='inst_001',
                    email_binding=email,
                    fixed_code=student_codes[i]
                )
                seed_vouchers.append(student_voucher)
            
            # Store all vouchers in database
            for voucher in seed_vouchers:
                self.firebase_service.create_document('vouchers', voucher, voucher['id'])
            
            logger.info(f"Generated {len(seed_vouchers)} seed vouchers successfully")
            
            return {
                'success': True,
                'vouchers_created': len(seed_vouchers),
                'vouchers': seed_vouchers,
                'message': 'Seed vouchers generated successfully'
            }
            
        except Exception as e:
            logger.error(f"Voucher seeding error: {str(e)}")
            return {
                'success': False,
                'error': 'Failed to generate seed vouchers'
            }
    
    def _generate_single_voucher(self, role: UserRole, institution_id: str, 
                               email_binding: Optional[str] = None, 
                               fixed_code: Optional[str] = None) -> Dict[str, Any]:
        """Generate a single voucher"""
        voucher_code = fixed_code if fixed_code else self._generate_secure_voucher_code()
        voucher_id = str(secrets.token_hex(8))
        
        return {
            'id': voucher_id,
            'code': voucher_code,
            'email_binding': email_binding,
            'role': role.value,
            'institution_id': institution_id,
            'is_used': False,
            'created_at': datetime.utcnow().isoformat(),
            'expires_at': (datetime.utcnow() + timedelta(days=90)).isoformat(),  # 90 days for seed
            'generated_by': 'system_seed',
            'batch_id': 'system_bootstrap_001'
        }
    
    def _generate_secure_voucher_code(self) -> str:
        """Generate cryptographically secure 8-character voucher code"""
        # Use uppercase letters and numbers only
        characters = string.ascii_uppercase + string.digits
        return ''.join(secrets.choice(characters) for _ in range(8))
    
    def get_test_vouchers(self) -> Dict[str, str]:
        """Get test vouchers for immediate use"""
        return {
            'institutional_admin': 'ADMIN123',
            'lecturer': 'LECT4567',
            'student': 'STUD7890'
        }
    
    def check_existing_vouchers(self) -> Dict[str, Any]:
        """Check if vouchers already exist in system"""
        try:
            vouchers = self.firebase_service.query_documents('vouchers', limit=10)
            
            return {
                'exists': len(vouchers) > 0,
                'count': len(vouchers),
                'sample': vouchers[:3] if vouchers else []
            }
            
        except Exception as e:
            logger.error(f"Voucher check error: {str(e)}")
            return {
                'exists': False,
                'count': 0,
                'error': str(e)
            }
