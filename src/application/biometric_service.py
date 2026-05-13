import logging
from datetime import datetime
from typing import Optional, Dict, Any, List
import base64
import hashlib

logger = logging.getLogger(__name__)


class BiometricService:
    """Professional biometric enrollment and verification service"""
    
    def __init__(self, firebase_service):
        self.firebase_service = firebase_service
    
    def enroll_device_fingerprint(self, user_id: str, device_data: Dict[str, Any]) -> Dict[str, Any]:
        """Enroll device fingerprint for user"""
        try:
            # Generate device fingerprint hash
            fingerprint_data = {
                'user_agent': device_data.get('user_agent', ''),
                'screen_resolution': device_data.get('screen_resolution', ''),
                'timezone': device_data.get('timezone', ''),
                'language': device_data.get('language', ''),
                'platform': device_data.get('platform', ''),
                'hardware_concurrency': device_data.get('hardware_concurrency', 0),
                'canvas_fingerprint': device_data.get('canvas_fingerprint', ''),
                'webgl_renderer': device_data.get('webgl_renderer', ''),
                'plugins': device_data.get('plugins', []),
                'fonts': device_data.get('fonts', []),
                'local_storage': device_data.get('local_storage', {}),
                'session_storage': device_data.get('session_storage', {}),
                'indexed_db': device_data.get('indexed_db', False)
            }
            
            # Create secure fingerprint hash
            fingerprint_string = str(sorted(fingerprint_data.items()))
            fingerprint_hash = hashlib.sha256(fingerprint_string.encode()).hexdigest()
            
            # Store biometric enrollment
            enrollment_data = {
                'id': str(hash(user_id + str(datetime.utcnow()))[:16]),
                'user_id': user_id,
                'biometric_type': 'device_fingerprint',
                'biometric_data': fingerprint_hash,
                'device_metadata': fingerprint_data,
                'is_active': True,
                'enrollment_date': datetime.utcnow().isoformat(),
                'last_verified': datetime.utcnow().isoformat(),
                'verification_count': 0,
                'trust_score': 0.7  # Initial trust score
            }
            
            self.firebase_service.create_document('biometric_enrollments', enrollment_data, enrollment_data['id'])
            
            logger.info(f"Device fingerprint enrolled for user {user_id}")
            return {
                'success': True,
                'enrollment_id': enrollment_data['id'],
                'trust_score': enrollment_data['trust_score'],
                'message': 'Device fingerprint enrolled successfully'
            }
            
        except Exception as e:
            logger.error(f"Device fingerprint enrollment error: {str(e)}")
            return {
                'success': False,
                'error': 'Failed to enroll device fingerprint'
            }
    
    def verify_device_fingerprint(self, user_id: str, current_fingerprint_data: Dict[str, Any]) -> Dict[str, Any]:
        """Verify device fingerprint against enrolled data"""
        try:
            # Get user's enrolled fingerprints
            enrollments = self.firebase_service.query_documents(
                'biometric_enrollments',
                filters=[
                    {'field': 'user_id', 'value': user_id},
                    {'field': 'biometric_type', 'value': 'device_fingerprint'},
                    {'field': 'is_active', 'value': True}
                ]
            )
            
            if not enrollments:
                return {
                    'verified': False,
                    'trust_score': 0.0,
                    'message': 'No enrolled device fingerprint found'
                }
            
            # Generate current fingerprint hash
            current_fingerprint_string = str(sorted(current_fingerprint_data.items()))
            current_fingerprint_hash = hashlib.sha256(current_fingerprint_string.encode()).hexdigest()
            
            # Check against enrolled fingerprints
            for enrollment in enrollments:
                enrolled_hash = enrollment['biometric_data']
                
                # Calculate similarity score (simplified version)
                similarity_score = self._calculate_fingerprint_similarity(
                    current_fingerprint_data, 
                    enrollment['device_metadata']
                )
                
                if similarity_score >= 0.8:  # 80% similarity threshold
                    # Update enrollment
                    self.firebase_service.update_document('biometric_enrollments', enrollment['id'], {
                        'last_verified': datetime.utcnow().isoformat(),
                        'verification_count': enrollment.get('verification_count', 0) + 1,
                        'trust_score': min(1.0, enrollment.get('trust_score', 0.7) + 0.05)
                    })
                    
                    logger.info(f"Device fingerprint verified for user {user_id} with score {similarity_score}")
                    return {
                        'verified': True,
                        'trust_score': min(1.0, enrollment.get('trust_score', 0.7) + 0.05),
                        'similarity_score': similarity_score,
                        'enrollment_id': enrollment['id'],
                        'message': 'Device fingerprint verified successfully'
                    }
            
            # No match found
            return {
                'verified': False,
                'trust_score': 0.0,
                'similarity_score': 0.0,
                'message': 'Device fingerprint does not match enrolled devices'
            }
            
        except Exception as e:
            logger.error(f"Device fingerprint verification error: {str(e)}")
            return {
                'verified': False,
                'trust_score': 0.0,
                'error': 'Failed to verify device fingerprint'
            }
    
    def get_user_biometric_status(self, user_id: str) -> Dict[str, Any]:
        """Get user's biometric enrollment status"""
        try:
            enrollments = self.firebase_service.query_documents(
                'biometric_enrollments',
                filters=[
                    {'field': 'user_id', 'value': user_id},
                    {'field': 'is_active', 'value': True}
                ]
            )
            
            if not enrollments:
                return {
                    'enrolled': False,
                    'total_enrollments': 0,
                    'active_enrollments': 0,
                    'message': 'No biometric enrollments found'
                }
            
            active_enrollments = [e for e in enrollments if e.get('is_active', False)]
            
            return {
                'enrolled': True,
                'total_enrollments': len(enrollments),
                'active_enrollments': len(active_enrollments),
                'enrollments': [
                    {
                        'id': e['id'],
                        'type': e['biometric_type'],
                        'enrollment_date': e['enrollment_date'],
                        'last_verified': e.get('last_verified'),
                        'verification_count': e.get('verification_count', 0),
                        'trust_score': e.get('trust_score', 0.0)
                    } for e in active_enrollments
                ],
                'message': f'Found {len(active_enrollments)} active biometric enrollments'
            }
            
        except Exception as e:
            logger.error(f"Biometric status error: {str(e)}")
            return {
                'enrolled': False,
                'error': 'Failed to get biometric status'
            }
    
    def revoke_biometric_enrollment(self, enrollment_id: str, user_id: str) -> Dict[str, Any]:
        """Revoke a biometric enrollment"""
        try:
            # Verify ownership
            enrollment = self.firebase_service.get_document('biometric_enrollments', enrollment_id)
            if not enrollment or enrollment.get('user_id') != user_id:
                return {
                    'success': False,
                    'error': 'Enrollment not found or access denied'
                }
            
            # Deactivate enrollment
            self.firebase_service.update_document('biometric_enrollments', enrollment_id, {
                'is_active': False,
                'revoked_date': datetime.utcnow().isoformat(),
                'revocation_reason': 'User requested revocation'
            })
            
            logger.info(f"Biometric enrollment {enrollment_id} revoked for user {user_id}")
            return {
                'success': True,
                'message': 'Biometric enrollment revoked successfully'
            }
            
        except Exception as e:
            logger.error(f"Biometric revocation error: {str(e)}")
            return {
                'success': False,
                'error': 'Failed to revoke biometric enrollment'
            }
    
    def _calculate_fingerprint_similarity(self, current: Dict[str, Any], enrolled: Dict[str, Any]) -> float:
        """Calculate similarity score between two fingerprints"""
        try:
            similarity_score = 0.0
            total_fields = 0
            
            # Compare key fields
            key_fields = [
                'user_agent', 'screen_resolution', 'timezone', 'language',
                'platform', 'hardware_concurrency', 'webgl_renderer'
            ]
            
            for field in key_fields:
                total_fields += 1
                if field in current and field in enrolled:
                    if current[field] == enrolled[field]:
                        similarity_score += 1.0
                    elif isinstance(current[field], str) and isinstance(enrolled[field], str):
                        # String similarity
                        similarity = self._string_similarity(current[field], enrolled[field])
                        similarity_score += similarity
            
            # Check arrays (fonts, plugins)
            array_fields = ['fonts', 'plugins']
            for field in array_fields:
                if field in current and field in enrolled:
                    current_array = set(current[field]) if isinstance(current[field], list) else set()
                    enrolled_array = set(enrolled[field]) if isinstance(enrolled[field], list) else set()
                    
                    intersection = len(current_array.intersection(enrolled_array))
                    union = len(current_array.union(enrolled_array))
                    
                    if union > 0:
                        similarity_score += (intersection / union) * 2  # Weight arrays more heavily
                        total_fields += 2
            
            return similarity_score / max(total_fields, 1)
            
        except Exception as e:
            logger.error(f"Fingerprint similarity calculation error: {str(e)}")
            return 0.0
    
    def _string_similarity(self, str1: str, str2: str) -> float:
        """Calculate string similarity using Jaccard-like approach"""
        if not str1 or not str2:
            return 0.0
        
        set1 = set(str1.lower().split())
        set2 = set(str2.lower().split())
        
        intersection = len(set1.intersection(set2))
        union = len(set1.union(set2))
        
        return intersection / union if union > 0 else 0.0
