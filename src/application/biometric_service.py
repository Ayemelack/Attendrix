import logging
from datetime import datetime
from typing import Optional, Dict, Any, List
import base64
import hashlib
import math
import secrets

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
    
    # ── FACE RECOGNITION ──

    def enroll_face(self, user_id: str, descriptor: List[float], institution_id: str = None) -> Dict[str, Any]:
        """Enroll a face descriptor (128-dim embedding from face-api.js)"""
        try:
            if not descriptor or len(descriptor) != 128:
                return {'success': False, 'error': 'Invalid face descriptor (must be 128 floats)'}

            enrollment_id = secrets.token_hex(8)
            enrollment_data = {
                'id': enrollment_id,
                'user_id': user_id,
                'institution_id': institution_id,
                'biometric_type': 'face',
                'biometric_data': descriptor,
                'is_active': True,
                'enrollment_date': datetime.utcnow().isoformat(),
                'last_verified': datetime.utcnow().isoformat(),
                'verification_count': 0,
                'trust_score': 0.8,
            }

            self.firebase_service.create_document('biometric_enrollments', enrollment_data, enrollment_id)
            logger.info(f"Face enrolled for user {user_id} (id={enrollment_id})")
            return {'success': True, 'enrollment_id': enrollment_id, 'message': 'Face enrolled successfully'}

        except Exception as e:
            logger.error(f"Face enrollment error: {str(e)}")
            return {'success': False, 'error': 'Failed to enroll face'}

    def verify_face(self, user_id: str, descriptor: List[float], threshold: float = 0.45) -> Dict[str, Any]:
        """Verify a face descriptor against enrolled faces using Euclidean distance.
        Threshold 0.45 per spec — matches face-api.js FaceMatcher default."""
        try:
            if not descriptor or len(descriptor) != 128:
                return {'verified': False, 'error': 'Invalid face descriptor (must be 128 floats)'}

            enrollments = self.firebase_service.query_documents(
                'biometric_enrollments',
                filters=[
                    {'field': 'user_id', 'value': user_id},
                    {'field': 'biometric_type', 'value': 'face'},
                    {'field': 'is_active', 'value': True}
                ]
            )

            if not enrollments:
                return {'verified': False, 'trust_score': 0.0, 'message': 'No face enrolled'}

            best_distance = float('inf')
            best_enrollment = None

            for enrollment in enrollments:
                enrolled_descriptor = enrollment.get('biometric_data', [])
                if not enrolled_descriptor or len(enrolled_descriptor) != 128:
                    continue

                distance = self._euclidean_distance(descriptor, enrolled_descriptor)
                if distance < best_distance:
                    best_distance = distance
                    best_enrollment = enrollment

            if best_enrollment is None:
                return {'verified': False, 'trust_score': 0.0, 'message': 'No valid enrolled faces'}

            similarity = max(0.0, 1.0 - best_distance)
            verified = best_distance <= threshold
            trust_score = min(1.0, similarity)

            if verified:
                self.firebase_service.update_document('biometric_enrollments', best_enrollment['id'], {
                    'last_verified': datetime.utcnow().isoformat(),
                    'verification_count': best_enrollment.get('verification_count', 0) + 1,
                    'trust_score': min(1.0, best_enrollment.get('trust_score', 0.8) + 0.02)
                })
                logger.info(f"Face verified for user {user_id} (distance={best_distance:.4f})")
            else:
                logger.warning(f"Face verification FAILED for user {user_id} (distance={best_distance:.4f} > threshold={threshold})")

            return {
                'verified': verified,
                'confidence': round(similarity, 4),
                'distance': round(best_distance, 4),
                'threshold': threshold,
                'trust_score': trust_score,
                'enrollment_id': best_enrollment['id'],
                'message': 'Face matched' if verified else 'Face does not match enrolled face'
            }

        except Exception as e:
            logger.error(f"Face verification error: {str(e)}")
            return {'verified': False, 'error': 'Failed to verify face'}

    def verify_face_against_all(self, descriptor: List[float], institution_id: str = None,
                                threshold: float = 0.45) -> Dict[str, Any]:
        """Match a face descriptor against ALL enrolled faces (multi-user).
        Returns the best match or 'unknown' if no match found.
        Used when the student's identity must be verified against all enrollments."""
        try:
            if not descriptor or len(descriptor) != 128:
                return {'verified': False, 'error': 'Invalid face descriptor'}

            all_enrollments = self.get_all_face_descriptors(institution_id)
            if not all_enrollments:
                return {'verified': False, 'label': 'unknown', 'message': 'No enrolled faces found'}

            best_distance = float('inf')
            best_match = None

            for entry in all_enrollments:
                enrolled_desc = entry.get('descriptor', [])
                if not enrolled_desc or len(enrolled_desc) != 128:
                    continue
                distance = self._euclidean_distance(descriptor, enrolled_desc)
                if distance < best_distance:
                    best_distance = distance
                    best_match = entry

            if best_match is None:
                return {'verified': False, 'label': 'unknown', 'message': 'No valid match found'}

            similarity = max(0.0, 1.0 - best_distance)
            verified = best_distance <= threshold

            if not verified:
                return {
                    'verified': False,
                    'label': 'unknown',
                    'confidence': round(similarity, 4),
                    'distance': round(best_distance, 4),
                    'reason': 'Face mismatch',
                    'message': 'Face does not match enrolled face'
                }

            return {
                'verified': True,
                'label': best_match['label'],
                'user_name': best_match['user_name'],
                'confidence': round(similarity, 4),
                'distance': round(best_distance, 4),
                'threshold': threshold,
                'message': f"Face verified → Student identified ({best_match['user_name']})"
            }

        except Exception as e:
            logger.error(f"verify_face_against_all error: {str(e)}")
            return {'verified': False, 'label': 'unknown', 'error': 'Failed to verify face'}

    def get_all_face_descriptors(self, institution_id: str = None) -> List[Dict[str, Any]]:
        """Return ALL active face enrollments with labels for FaceMatcher.
        Each entry: { label: <student_id>, descriptor: [128 floats], user_name: <name> }
        Called BEFORE verification starts to build labeled descriptors."""
        try:
            filters = [
                {'field': 'biometric_type', 'value': 'face'},
                {'field': 'is_active', 'value': True}
            ]
            if institution_id:
                filters.append({'field': 'institution_id', 'value': institution_id})

            enrollments = self.firebase_service.query_documents(
                'biometric_enrollments', filters=filters
            )

            if not enrollments:
                return []

            # Enrich with user names
            result = []
            for e in enrollments:
                desc = e.get('biometric_data', [])
                if not desc or len(desc) != 128:
                    continue
                uid = e.get('user_id', 'unknown')
                # Look up user name
                user = self.firebase_service.get_document('users', uid) if uid != 'unknown' else None
                name = ''
                if user:
                    name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip()
                result.append({
                    'label': uid,
                    'user_name': name or uid,
                    'descriptor': desc
                })

            logger.info(f"Loaded {len(result)} face descriptors for matching")
            return result

        except Exception as e:
            logger.error(f"get_all_face_descriptors error: {str(e)}")
            return []

    def get_face_status(self, user_id: str) -> Dict[str, Any]:
        """Check if user has active face enrollment"""
        try:
            enrollments = self.firebase_service.query_documents(
                'biometric_enrollments',
                filters=[
                    {'field': 'user_id', 'value': user_id},
                    {'field': 'biometric_type', 'value': 'face'},
                    {'field': 'is_active', 'value': True}
                ]
            )

            if not enrollments:
                return {'enrolled': False, 'total_enrollments': 0}

            return {
                'enrolled': True,
                'total_enrollments': len(enrollments),
                'enrollment': {
                    'id': enrollments[0]['id'],
                    'enrollment_date': enrollments[0]['enrollment_date'],
                    'last_verified': enrollments[0].get('last_verified'),
                    'verification_count': enrollments[0].get('verification_count', 0),
                    'trust_score': enrollments[0].get('trust_score', 0.0)
                }
            }

        except Exception as e:
            logger.error(f"Face status error: {str(e)}")
            return {'enrolled': False, 'error': 'Failed to get face status'}

    def revoke_face(self, user_id: str) -> Dict[str, Any]:
        """Revoke all face enrollments for a user"""
        try:
            enrollments = self.firebase_service.query_documents(
                'biometric_enrollments',
                filters=[
                    {'field': 'user_id', 'value': user_id},
                    {'field': 'biometric_type', 'value': 'face'},
                    {'field': 'is_active', 'value': True}
                ]
            )

            revoked = 0
            for enrollment in enrollments:
                self.firebase_service.update_document('biometric_enrollments', enrollment['id'], {
                    'is_active': False,
                    'revoked_date': datetime.utcnow().isoformat()
                })
                revoked += 1

            logger.info(f"Revoked {revoked} face enrollment(s) for user {user_id}")
            return {'success': True, 'revoked': revoked, 'message': f'Revoked {revoked} face enrollment(s)'}

        except Exception as e:
            logger.error(f"Face revocation error: {str(e)}")
            return {'success': False, 'error': 'Failed to revoke face enrollments'}

    def _euclidean_distance(self, a: List[float], b: List[float]) -> float:
        """Euclidean distance between two vectors"""
        return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))

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
