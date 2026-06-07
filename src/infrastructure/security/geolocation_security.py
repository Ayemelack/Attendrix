"""
GEOLOCATION SECURITY MODULE
Attendrix distributed attendance system

GPS validation, geofencing, and attendance radius restrictions.
Enforces location-based attendance rules and prevents spoofing.
"""

import math
from dataclasses import dataclass
from typing import Tuple, Optional, Dict, Any
from flask import current_app
import logging

logger = logging.getLogger(__name__)


@dataclass
class Location:
    """Represents a geographic coordinate."""
    latitude: float
    longitude: float
    accuracy: float = None  # meters
    timestamp: int = None  # Unix timestamp

    def to_dict(self) -> Dict[str, Any]:
        return {
            'latitude': self.latitude,
            'longitude': self.longitude,
            'accuracy': self.accuracy,
            'timestamp': self.timestamp,
        }


class GeoFence:
    """Represents a circular geographic boundary."""
    
    def __init__(self, center_lat: float, center_lon: float, radius_meters: float):
        """
        Initialize geofence.
        
        Args:
            center_lat: Center latitude
            center_lon: Center longitude
            radius_meters: Radius in meters
        """
        self.center_lat = center_lat
        self.center_lon = center_lon
        self.radius_meters = radius_meters

    def contains(self, location: Location) -> bool:
        """Check if location is within geofence."""
        distance = self.distance_to(location.latitude, location.longitude)
        return distance <= self.radius_meters

    def distance_to(self, lat: float, lon: float) -> float:
        """Calculate distance to point using Haversine formula (meters)."""
        R = 6371000  # Earth radius in meters
        
        lat1_rad = math.radians(self.center_lat)
        lat2_rad = math.radians(lat)
        delta_lat = math.radians(lat - self.center_lat)
        delta_lon = math.radians(lon - self.center_lon)
        
        a = math.sin(delta_lat / 2) ** 2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2
        c = 2 * math.asin(math.sqrt(a))
        
        return R * c

    def to_dict(self) -> Dict[str, Any]:
        return {
            'center': {'lat': self.center_lat, 'lon': self.center_lon},
            'radius_meters': self.radius_meters,
        }


class GeolocationValidator:
    """Validates attendance locations and enforces geofencing."""
    
    def __init__(self):
        self.warning_threshold = 50  # meters — warn if outside this distance

    def validate_attendance_location(
        self,
        user_location: Location,
        institution_geofence: GeoFence,
        allow_buffer: bool = False,
    ) -> Tuple[bool, Optional[str], Dict[str, Any]]:
        """
        Validate if user location allows attendance.
        
        Args:
            user_location: User's current GPS location
            institution_geofence: Institution's geofence boundary
            allow_buffer: If True, allow attendance with buffer distance warning
            
        Returns:
            (is_valid, error_message, metadata)
        """
        # Validate location data integrity
        if not self._is_valid_coordinate(user_location.latitude, user_location.longitude):
            return False, 'Invalid GPS coordinates', {'reason': 'coordinate_invalid'}

        # Check GPS accuracy
        if user_location.accuracy and user_location.accuracy > 100:
            logger.warning(
                f'GPS accuracy poor: {user_location.accuracy}m (acceptable: <100m)',
                extra={'accuracy': user_location.accuracy}
            )

        # Check if within geofence
        distance = institution_geofence.distance_to(user_location.latitude, user_location.longitude)
        is_within = institution_geofence.contains(user_location)

        metadata = {
            'distance_to_center': distance,
            'geofence_radius': institution_geofence.radius_meters,
            'user_location': user_location.to_dict(),
            'institution_geofence': institution_geofence.to_dict(),
        }

        if is_within:
            return True, None, metadata

        # Outside geofence — check if warning threshold applies
        if allow_buffer and distance < (institution_geofence.radius_meters + self.warning_threshold):
            logger.info(
                f'User outside geofence but within buffer: {distance}m from center',
                extra={'distance': distance}
            )
            return False, f'You are {distance:.0f}m outside the attendance zone. Move closer to campus.', metadata

        logger.warning(
            f'User outside geofence: {distance}m (geofence: {institution_geofence.radius_meters}m)',
            extra=metadata
        )
        return False, f'You are {distance:.0f}m outside the allowed attendance zone.', metadata

    def _is_valid_coordinate(self, lat: float, lon: float) -> bool:
        """Validate GPS coordinate ranges."""
        try:
            lat_f = float(lat)
            lon_f = float(lon)
            return -90 <= lat_f <= 90 and -180 <= lon_f <= 180
        except (TypeError, ValueError):
            return False

    def calculate_buffer_zone(self, geofence: GeoFence, buffer_meters: float) -> GeoFence:
        """Create a buffer zone around geofence for warnings."""
        return GeoFence(
            geofence.center_lat,
            geofence.center_lon,
            geofence.radius_meters + buffer_meters,
        )


class LocationProofOfWork:
    """Generates and validates location proof tokens to prevent location spoofing."""
    
    def __init__(self):
        """Initialize with challenge-response mechanism."""
        pass

    def generate_location_challenge(self, institution_id: str, session_id: str) -> Dict[str, Any]:
        """Generate a location challenge that requires GPS response."""
        import uuid
        import time
        
        challenge_id = str(uuid.uuid4())
        timestamp = int(time.time())
        
        return {
            'challenge_id': challenge_id,
            'institution_id': institution_id,
            'session_id': session_id,
            'timestamp': timestamp,
            'expires_at': timestamp + 300,  # 5 minutes
        }

    def validate_location_response(
        self,
        challenge: Dict[str, Any],
        location: Location,
        geofence: GeoFence,
        max_age_seconds: int = 30,
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate location response to challenge.
        
        Args:
            challenge: Original location challenge
            location: GPS location response
            geofence: Attendance zone
            max_age_seconds: Max age of GPS reading
            
        Returns:
            (is_valid, error_message)
        """
        import time
        
        current_time = int(time.time())
        
        # Check challenge expiration
        if current_time > challenge['expires_at']:
            return False, 'Location challenge expired'

        # Check location freshness
        if location.timestamp and (current_time - location.timestamp) > max_age_seconds:
            return False, f'GPS reading too old (>{max_age_seconds}s)'

        # Validate location within geofence
        if not geofence.contains(location):
            distance = geofence.distance_to(location.latitude, location.longitude)
            return False, f'Location {distance:.0f}m outside allowed zone'

        return True, None
