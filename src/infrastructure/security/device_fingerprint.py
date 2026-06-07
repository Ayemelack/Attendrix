"""
DEVICE FINGERPRINTING SECURITY MODULE
Attendrix distributed attendance system

Device identification, emulator detection, shared device detection, and device binding.
"""

import hashlib
import logging
from typing import Dict, Any, Tuple, Optional
from dataclasses import dataclass
from flask import request

logger = logging.getLogger(__name__)


@dataclass
class DeviceFingerprint:
    """Represents a device fingerprint."""
    fingerprint_id: str
    device_model: str = None
    device_type: str = None  # mobile, tablet, desktop, emulator
    os: str = None
    os_version: str = None
    browser: str = None
    browser_version: str = None
    user_agent_hash: str = None
    screen_resolution: str = None
    is_emulator: bool = False
    is_shared_device: bool = False
    is_rooted_jailbroken: bool = False
    is_development_device: bool = False
    entropy_score: float = 0.0  # 0-1, higher = more unique

    def to_dict(self) -> Dict[str, Any]:
        return {
            'fingerprint_id': self.fingerprint_id,
            'device_model': self.device_model,
            'device_type': self.device_type,
            'os': self.os,
            'os_version': self.os_version,
            'browser': self.browser,
            'is_emulator': self.is_emulator,
            'is_shared_device': self.is_shared_device,
            'is_rooted_jailbroken': self.is_rooted_jailbroken,
            'entropy_score': self.entropy_score,
        }


class DeviceFingerprintAnalyzer:
    """Analyzes and validates device fingerprints."""

    def __init__(self):
        """Initialize device fingerprint analyzer."""
        self.device_cache = {}  # {user_id: [fingerprints]}

    def generate_fingerprint(
        self,
        user_agent: Optional[str] = None,
        device_data: Optional[Dict[str, Any]] = None,
    ) -> DeviceFingerprint:
        """
        Generate device fingerprint from request data.
        
        Args:
            user_agent: HTTP User-Agent header
            device_data: Client-provided device data (sanitized)
            
        Returns:
            DeviceFingerprint object
        """
        ua = user_agent or (request.headers.get('User-Agent', '') if request else '')
        
        fingerprint = DeviceFingerprint(
            fingerprint_id=self._hash_fingerprint_data(ua, device_data)
        )

        # Parse User-Agent
        if ua:
            fingerprint = self._parse_user_agent(ua, fingerprint)

        # Analyze client-provided device data
        if device_data:
            fingerprint = self._analyze_device_data(device_data, fingerprint)

        # Calculate entropy score (uniqueness)
        fingerprint.entropy_score = self._calculate_entropy(fingerprint)

        return fingerprint

    def validate_device(
        self,
        user_id: str,
        fingerprint: DeviceFingerprint,
        require_non_emulator: bool = True,
        require_non_rooted: bool = True,
        block_suspicious: bool = False,
    ) -> Tuple[bool, Optional[str], Dict[str, Any]]:
        """
        Validate device against security policies.
        
        Args:
            user_id: User ID for device history tracking
            fingerprint: Device fingerprint to validate
            require_non_emulator: Block emulator devices
            require_non_rooted: Block rooted/jailbroken devices
            block_suspicious: Block low-entropy (generic) devices
            
        Returns:
            (is_valid, error_message, metadata)
        """
        metadata = {
            'fingerprint': fingerprint.to_dict(),
            'user_id': user_id,
        }

        # Check for emulator
        if require_non_emulator and fingerprint.is_emulator:
            logger.warning(
                f'Emulator device rejected for user {user_id}',
                extra=metadata
            )
            return False, 'Attendance cannot be recorded from emulator devices.', metadata

        # Check for rooted/jailbroken
        if require_non_rooted and fingerprint.is_rooted_jailbroken:
            logger.warning(
                f'Rooted/jailbroken device rejected for user {user_id}',
                extra=metadata
            )
            return False, 'Your device appears to be rooted/jailbroken. Please use a standard device.', metadata

        # Check for development device
        if fingerprint.is_development_device:
            logger.warning(
                f'Development device detected for user {user_id}',
                extra=metadata
            )

        # Check entropy (low entropy = generic/spoofed device)
        if block_suspicious and fingerprint.entropy_score < 0.3:
            logger.warning(
                f'Low-entropy device (suspicious) rejected: {fingerprint.entropy_score}',
                extra=metadata
            )
            return False, 'Your device fingerprint is not recognized. Please use your registered device.', metadata

        # Check for shared device pattern
        if fingerprint.is_shared_device:
            logger.info(f'Shared device detected for user {user_id}', extra=metadata)
            # Don't block, but log for audit
            metadata['warning'] = 'Shared device detected - verify before recording attendance'

        return True, None, metadata

    def detect_device_change(
        self,
        user_id: str,
        current_fingerprint: DeviceFingerprint,
        similarity_threshold: float = 0.85,
    ) -> Tuple[bool, Optional[str], Dict[str, Any]]:
        """
        Detect if user is using a different device.
        
        Args:
            user_id: User ID
            current_fingerprint: Current device fingerprint
            similarity_threshold: 0-1, how similar must be to pass
            
        Returns:
            (is_same_device, warning_message, metadata)
        """
        previous_fingerprints = self.device_cache.get(user_id, [])
        
        if not previous_fingerprints:
            # First device for user
            self._register_device(user_id, current_fingerprint)
            return True, None, {'is_first_device': True}

        # Calculate similarity with known devices
        similarities = [
            self._calculate_similarity(current_fingerprint, prev)
            for prev in previous_fingerprints
        ]

        max_similarity = max(similarities) if similarities else 0.0
        is_known_device = max_similarity >= similarity_threshold

        metadata = {
            'max_similarity': max_similarity,
            'threshold': similarity_threshold,
            'is_known_device': is_known_device,
            'num_known_devices': len(previous_fingerprints),
        }

        if not is_known_device:
            logger.warning(
                f'Device change detected for user {user_id} (similarity: {max_similarity})',
                extra=metadata
            )
            message = (
                f'This appears to be a new device. '
                f'If this is unexpected, verify your account security. '
                f'(Similarity: {max_similarity*100:.0f}%)'
            )
            return False, message, metadata

        return True, None, metadata

    def _parse_user_agent(self, ua: str, fp: DeviceFingerprint) -> DeviceFingerprint:
        """Parse User-Agent string to extract device info."""
        ua_lower = ua.lower()

        # Detect device type
        if 'mobile' in ua_lower or 'android' in ua_lower:
            fp.device_type = 'mobile'
        elif 'tablet' in ua_lower or 'ipad' in ua_lower:
            fp.device_type = 'tablet'
        else:
            fp.device_type = 'desktop'

        # Detect OS
        if 'windows' in ua_lower:
            fp.os = 'Windows'
        elif 'mac' in ua_lower:
            fp.os = 'macOS'
        elif 'android' in ua_lower:
            fp.os = 'Android'
        elif 'iphone' or 'ipad' in ua_lower:
            fp.os = 'iOS'
        elif 'linux' in ua_lower:
            fp.os = 'Linux'

        # Detect browser
        if 'chrome' in ua_lower:
            fp.browser = 'Chrome'
        elif 'firefox' in ua_lower:
            fp.browser = 'Firefox'
        elif 'safari' in ua_lower:
            fp.browser = 'Safari'
        elif 'edge' in ua_lower:
            fp.browser = 'Edge'

        # Detect emulator patterns
        if any(emulator in ua_lower for emulator in ['emulator', 'simulator', 'bluestacks', 'nox', 'memu']):
            fp.is_emulator = True

        fp.user_agent_hash = hashlib.sha256(ua.encode()).hexdigest()[:16]
        
        return fp

    def _analyze_device_data(self, device_data: Dict[str, Any], fp: DeviceFingerprint) -> DeviceFingerprint:
        """Analyze client-provided device data."""
        # Device model
        if 'model' in device_data:
            fp.device_model = device_data['model']

        # Detect rooted/jailbroken
        if device_data.get('isRooted') or device_data.get('isJailbroken'):
            fp.is_rooted_jailbroken = True

        # Detect development device
        if device_data.get('isDebugBuild') or device_data.get('isDeveloperMode'):
            fp.is_development_device = True

        # Screen resolution (can detect emulators with common res)
        if 'screenResolution' in device_data:
            fp.screen_resolution = device_data['screenResolution']
            # Common emulator resolutions
            if fp.screen_resolution in ['480x800', '600x1024', '720x1280']:
                fp.is_emulator = True

        # Detect shared device (if multiple users reported from same device)
        if device_data.get('multipleUsers'):
            fp.is_shared_device = True

        return fp

    def _hash_fingerprint_data(self, ua: str, device_data: Optional[Dict] = None) -> str:
        """Generate fingerprint ID hash."""
        data = ua or ''
        if device_data:
            data += str(sorted(device_data.items()))
        return hashlib.sha256(data.encode()).hexdigest()[:16]

    def _calculate_entropy(self, fingerprint: DeviceFingerprint) -> float:
        """
        Calculate uniqueness/entropy of fingerprint (0-1).
        Higher = more unique (less likely spoofed).
        """
        entropy = 0.0
        
        # Unique device model increases entropy
        if fingerprint.device_model:
            entropy += 0.15
        
        # Specific browser/OS combination increases entropy
        if fingerprint.browser and fingerprint.os:
            entropy += 0.20
        
        # Non-emulator increases entropy
        if not fingerprint.is_emulator:
            entropy += 0.25
        
        # Non-shared device increases entropy
        if not fingerprint.is_shared_device:
            entropy += 0.15
        
        # Not rooted/jailbroken increases entropy
        if not fingerprint.is_rooted_jailbroken:
            entropy += 0.15
        
        # Specific screen resolution increases entropy
        if fingerprint.screen_resolution:
            entropy += 0.10
        
        return min(entropy, 1.0)  # Cap at 1.0

    def _calculate_similarity(self, fp1: DeviceFingerprint, fp2: DeviceFingerprint) -> float:
        """
        Calculate similarity between two fingerprints (0-1).
        1.0 = identical, 0.0 = completely different.
        """
        similarity = 0.0
        
        if fp1.device_model and fp1.device_model == fp2.device_model:
            similarity += 0.25
        
        if fp1.device_type and fp1.device_type == fp2.device_type:
            similarity += 0.20
        
        if fp1.os and fp1.os == fp2.os:
            similarity += 0.20
        
        if fp1.browser and fp1.browser == fp2.browser:
            similarity += 0.15
        
        if fp1.is_emulator == fp2.is_emulator:
            similarity += 0.10
        
        if fp1.screen_resolution and fp1.screen_resolution == fp2.screen_resolution:
            similarity += 0.10
        
        return min(similarity, 1.0)

    def _register_device(self, user_id: str, fingerprint: DeviceFingerprint):
        """Register a device for a user."""
        if user_id not in self.device_cache:
            self.device_cache[user_id] = []
        self.device_cache[user_id].append(fingerprint)
