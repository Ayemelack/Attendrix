"""
GEOLOCATION SECURITY MODULE
Attendrix distributed attendance system

GPS validation, geofencing, and attendance radius restrictions.
Enforces location-based attendance rules and prevents spoofing.
"""

import math
from dataclasses import dataclass
from typing import Tuple, Optional, Dict, Any, List
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
        self.previous_locations = {}  # {user_id: Location}
        self.institution_geofences = {}  # {institution_id: GeoFence}

    def validate_attendance_location(
        self,
        user_location: Location,
        institution_geofence: GeoFence,
        allow_buffer: bool = False,
        user_id: Optional[str] = None,
    ) -> Tuple[bool, Optional[str], Dict[str, Any]]:
        """
        Validate if user location allows attendance.
        
        Args:
            user_location: User's current GPS location
            institution_geofence: Institution's geofence boundary
            allow_buffer: If True, allow attendance with buffer distance warning
            user_id: Optional user ID for speed calculation and logging
            
        Returns:
            (is_valid, error_message, metadata)
        """
        checks = {}

        # Validate location data integrity
        coord_valid = self._is_valid_coordinate(user_location.latitude, user_location.longitude)
        checks['coordinate_valid'] = coord_valid
        if not coord_valid:
            return False, 'Invalid GPS coordinates', {
                'reason': 'coordinate_invalid',
                'checks': checks,
            }

        # Check GPS accuracy
        accuracy_penalty = 0.0
        if user_location.accuracy is not None:
            if user_location.accuracy > 100:
                logger.warning(
                    f'GPS accuracy poor: {user_location.accuracy}m (acceptable: <100m)',
                    extra={'accuracy': user_location.accuracy}
                )
                accuracy_penalty = min(user_location.accuracy / 500, 1.0)
                checks['accuracy_warning'] = f'GPS accuracy poor: {user_location.accuracy}m'
            else:
                checks['accuracy_ok'] = True

        # Speed check (impossible travel detection)
        speed_suspicious = False
        if user_id and user_id in self.previous_locations:
            prev_loc = self.previous_locations[user_id]
            if prev_loc.timestamp and user_location.timestamp:
                time_diff = (user_location.timestamp - prev_loc.timestamp)
                if time_diff > 0:
                    dist = self._haversine_distance(
                        prev_loc.latitude, prev_loc.longitude,
                        user_location.latitude, user_location.longitude,
                    )
                    speed_ms = dist / time_diff
                    speed_kph = speed_ms * 3.6
                    checks['speed_kph'] = round(speed_kph, 1)
                    if speed_kph > 500:
                        speed_suspicious = True
                        checks['speed_warning'] = f'Impossible travel detected: {speed_kph:.0f} km/h'

        # Check if within geofence
        distance = institution_geofence.distance_to(user_location.latitude, user_location.longitude)
        is_within = institution_geofence.contains(user_location)

        metadata = {
            'distance_to_center': distance,
            'geofence_radius': institution_geofence.radius_meters,
            'user_location': user_location.to_dict(),
            'institution_geofence': institution_geofence.to_dict(),
            'accuracy_penalty': accuracy_penalty,
            'speed_suspicious': speed_suspicious,
            'checks': checks,
        }

        # Store location for future speed checks
        if user_id:
            self.previous_locations[user_id] = user_location

        if speed_suspicious:
            logger.warning(
                f'Geolocation speed violation for user {user_id}: {checks.get("speed_kph", "unknown")} km/h',
                extra=metadata
            )

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

    def configure_institution_geofence(self, institution_id: str, lat: float, lon: float, radius_meters: float):
        """Configure per-institution geofence."""
        geofence = GeoFence(lat, lon, radius_meters)
        self.institution_geofences[institution_id] = geofence
        logger.info(f'Geofence configured for institution {institution_id}: center=({lat},{lon}), radius={radius_meters}m')

    def get_institution_geofence(self, institution_id: str) -> Optional[GeoFence]:
        """Get configured geofence for an institution."""
        return self.institution_geofences.get(institution_id)

    def list_configured_geofences(self) -> List[Dict[str, Any]]:
        """List all configured geofences."""
        return [
            {'institution_id': inst_id, **gf.to_dict()}
            for inst_id, gf in self.institution_geofences.items()
        ]

    def calculate_distance_from_institution(self, lat: float, lon: float, institution_id: str) -> Optional[float]:
        """Calculate distance from a location to an institution's geofence center."""
        geofence = self.institution_geofences.get(institution_id)
        if not geofence:
            return None
        return geofence.distance_to(lat, lon)

    def is_within_geofence(self, lat: float, lon: float, institution_id: str) -> bool:
        """Check if location is within an institution's geofence."""
        geofence = self.institution_geofences.get(institution_id)
        if not geofence:
            return False
        loc = Location(latitude=lat, longitude=lon)
        return geofence.contains(loc)

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

    @staticmethod
    def _haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculate distance between two coordinates in meters."""
        R = 6371000
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
        c = 2 * math.asin(math.sqrt(a))
        return R * c


class GeofenceManager:
    """Manages geofence configurations with persistence support."""

    def __init__(self):
        self._geofences = {}  # {institution_id: GeoFence}

    def load_geofences(self) -> Dict[str, Any]:
        """Load geofences from Firebase or database."""
        try:
            if current_app:
                firebase = current_app.config.get('FIREBASE_DB')
                if False:
                    data = firebase.child('geofences').get().val()
                    if data:
                        for inst_id, config in data.items():
                            self._geofences[inst_id] = GeoFence(
                                config['lat'], config['lon'], config['radius_meters']
                            )
                        return {'loaded': len(data), 'source': 'firebase'}
        except Exception as e:
            logger.warning(f'Could not load geofences from Firebase: {e}')
        return {'loaded': 0, 'source': 'memory'}

    def save_geofence(self, institution_id: str, geofence: GeoFence) -> bool:
        """Save geofence configuration."""
        try:
            self._geofences[institution_id] = geofence
            if current_app:
                firebase = current_app.config.get('FIREBASE_DB')
                if False:
                    firebase.child('geofences').child(institution_id).set({
                        'lat': geofence.center_lat,
                        'lon': geofence.center_lon,
                        'radius_meters': geofence.radius_meters,
                    })
            logger.info(f'Geofence saved for institution {institution_id}')
            return True
        except Exception as e:
            logger.error(f'Failed to save geofence for {institution_id}: {e}')
            return False

    def delete_geofence(self, institution_id: str) -> bool:
        """Remove geofence configuration."""
        try:
            self._geofences.pop(institution_id, None)
            if current_app:
                firebase = current_app.config.get('FIREBASE_DB')
                if False:
                    firebase.child('geofences').child(institution_id).remove()
            logger.info(f'Geofence deleted for institution {institution_id}')
            return True
        except Exception as e:
            logger.error(f'Failed to delete geofence for {institution_id}: {e}')
            return False

    def validate_location_for_institution(self, lat: float, lon: float, institution_id: str) -> Dict[str, Any]:
        """Full validation of location for an institution."""
        geofence = self._geofences.get(institution_id)
        if not geofence:
            return {
                'valid': False,
                'error': f'No geofence configured for institution {institution_id}',
            }
        distance = geofence.distance_to(lat, lon)
        within = distance <= geofence.radius_meters
        return {
            'valid': within,
            'distance_meters': distance,
            'within_geofence': within,
            'geofence': geofence.to_dict(),
            'institution_id': institution_id,
        }

    def get_all_geofences(self) -> Dict[str, GeoFence]:
        """Get all configured geofences."""
        return dict(self._geofences)


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
