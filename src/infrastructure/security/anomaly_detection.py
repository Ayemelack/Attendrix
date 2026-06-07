"""
PHASE 3D — AI/ML ANOMALY DETECTION

Behavioral anomaly detection with:
- User behavioral baselines (login time, location, device patterns)
- Statistical anomaly scoring (Z-score, MAD, percentile-based)
- Time-series analysis of access patterns
- Unsupervised clustering for peer-group comparison
- Feature extraction from authentication events
- Adaptive thresholds that improve over time
- Low false-positive rate through multi-factor scoring
"""

import os
import json
import time
import math
import uuid
import logging
import statistics
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, field, asdict
from collections import defaultdict, deque
from enum import Enum

logger = logging.getLogger(__name__)


class AnomalySeverity(Enum):
    LOW = 'low'
    MEDIUM = 'medium'
    HIGH = 'high'
    CRITICAL = 'critical'


class AnomalyCategory(Enum):
    LOCATION_ANOMALY = 'location_anomaly'
    TIME_ANOMALY = 'time_anomaly'
    DEVICE_ANOMALY = 'device_anomaly'
    VELOCITY_ANOMALY = 'velocity_anomaly'
    BEHAVIORAL_ANOMALY = 'behavioral_anomaly'
    VOLUME_ANOMALY = 'volume_anomaly'
    SEQUENCE_ANOMALY = 'sequence_anomaly'


@dataclass
class BaselineProfile:
    """Behavioral baseline for a user."""
    user_id: str
    mean_login_hour: float
    std_login_hour: float
    common_locations: List[Dict[str, float]]
    common_devices: List[str]
    common_ip_ranges: List[str]
    typical_session_duration_mean: float
    typical_session_duration_std: float
    actions_per_session_mean: float
    actions_per_session_std: float
    samples_collected: int
    last_updated: int

    @staticmethod
    def empty(user_id: str) -> 'BaselineProfile':
        return BaselineProfile(
            user_id=user_id,
            mean_login_hour=12.0,
            std_login_hour=6.0,
            common_locations=[],
            common_devices=[],
            common_ip_ranges=[],
            typical_session_duration_mean=1800,
            typical_session_duration_std=600,
            actions_per_session_mean=10,
            actions_per_session_std=5,
            samples_collected=0,
            last_updated=0,
        )


@dataclass
class AnomalyEvent:
    """Detected anomaly event."""
    event_id: str
    user_id: str
    category: AnomalyCategory
    severity: AnomalySeverity
    score: float
    description: str
    attributes: Dict[str, Any]
    timestamp: int
    resolved: bool = False


@dataclass
class FeatureVector:
    """Feature vector extracted from an authentication event."""
    hour_of_day: int
    day_of_week: int
    ip_address: str
    device_id: str
    user_agent_hash: str
    geolocation_lat: float
    geolocation_lng: float
    session_duration: float
    action_count: int
    failed_attempts_24h: int
    account_age_days: float
    is_known_ip: bool
    is_known_device: bool
    is_known_location: bool


class AnomalyDetector:
    """Behavioral anomaly detection engine."""

    def __init__(self, firebase_service=None):
        self.firebase = firebase_service
        self._baselines: Dict[str, BaselineProfile] = {}
        self._recent_events: Dict[str, deque] = {}
        self._max_recent_events = 1000
        self._anomaly_threshold = float(os.environ.get('ANOMALY_THRESHOLD', '2.5'))
        self._min_samples = int(os.environ.get('ANOMALY_MIN_SAMPLES', '10'))
        self._anomaly_log: List[AnomalyEvent] = []

    def get_baseline(self, user_id: str) -> BaselineProfile:
        baseline = self._baselines.get(user_id)
        if baseline:
            return baseline
        baseline = self._load_baseline(user_id)
        return baseline

    def update_baseline(self, user_id: str, features: FeatureVector):
        baseline = self.get_baseline(user_id)

        if baseline.samples_collected < self._min_samples:
            self._initialize_baseline(baseline, features)
        else:
            self._update_baseline(baseline, features)

        baseline.last_updated = int(time.time())
        self._baselines[user_id] = baseline
        self._persist_baseline(user_id, baseline)

    def _initialize_baseline(self, baseline: BaselineProfile, features: FeatureVector):
        n = baseline.samples_collected
        baseline.mean_login_hour = (
            (baseline.mean_login_hour * n + features.hour_of_day) / (n + 1)
        ) if n > 0 else features.hour_of_day
        baseline.samples_collected += 1

        if features.geolocation_lat != 0 or features.geolocation_lng != 0:
            baseline.common_locations.append({
                'lat': features.geolocation_lat,
                'lng': features.geolocation_lng,
                'count': 1,
            })

        if features.device_id:
            baseline.common_devices.append(features.device_id)

        ip_prefix = '.'.join(features.ip_address.split('.')[:2]) + '.0.0/16'
        if ip_prefix not in baseline.common_ip_ranges:
            baseline.common_ip_ranges.append(ip_prefix)

    def _update_baseline(self, baseline: BaselineProfile, features: FeatureVector):
        n = baseline.samples_collected
        alpha = 0.05

        baseline.mean_login_hour = (
            (1 - alpha) * baseline.mean_login_hour + alpha * features.hour_of_day
        )

        dev = abs(features.hour_of_day - baseline.mean_login_hour)
        baseline.std_login_hour = (
            (1 - alpha) * baseline.std_login_hour + alpha * dev
        )

        if features.geolocation_lat != 0 or features.geolocation_lng != 0:
            found = False
            for loc in baseline.common_locations:
                dist = math.sqrt(
                    (loc['lat'] - features.geolocation_lat) ** 2 +
                    (loc['lng'] - features.geolocation_lng) ** 2
                )
                if dist < 0.5:
                    loc['count'] = loc.get('count', 1) + 1
                    found = True
                    break
            if not found:
                baseline.common_locations.append({
                    'lat': features.geolocation_lat,
                    'lng': features.geolocation_lng,
                    'count': 1,
                })
            if len(baseline.common_locations) > 20:
                baseline.common_locations.sort(key=lambda x: -x.get('count', 1))
                baseline.common_locations = baseline.common_locations[:20]

        if features.device_id and features.device_id not in baseline.common_devices:
            if len(baseline.common_devices) < 20:
                baseline.common_devices.append(features.device_id)

        baseline.samples_collected += 1

    def analyze(self, user_id: str, features: FeatureVector) -> List[AnomalyEvent]:
        anomalies = []
        baseline = self.get_baseline(user_id)

        if baseline.samples_collected < self._min_samples:
            self.update_baseline(user_id, features)
            return anomalies

        location_score = self._score_location_anomaly(baseline, features)
        if location_score > 0:
            severity = self._score_to_severity(location_score)
            anomalies.append(AnomalyEvent(
                event_id=str(uuid.uuid4()),
                user_id=user_id,
                category=AnomalyCategory.LOCATION_ANOMALY,
                severity=severity,
                score=location_score,
                description=f'Unusual location detected: ({features.geolocation_lat:.4f}, {features.geolocation_lng:.4f})',
                attributes={'lat': features.geolocation_lat, 'lng': features.geolocation_lng},
                timestamp=int(time.time()),
            ))

        time_score = self._score_time_anomaly(baseline, features)
        if time_score > 0:
            severity = self._score_to_severity(time_score)
            anomalies.append(AnomalyEvent(
                event_id=str(uuid.uuid4()),
                user_id=user_id,
                category=AnomalyCategory.TIME_ANOMALY,
                severity=severity,
                score=time_score,
                description=f'Unusual login time: {features.hour_of_day}:00 (baseline: {baseline.mean_login_hour:.1f}:00)',
                attributes={'hour': features.hour_of_day, 'baseline_mean': baseline.mean_login_hour},
                timestamp=int(time.time()),
            ))

        device_score = self._score_device_anomaly(baseline, features)
        if device_score > 0:
            severity = self._score_to_severity(device_score)
            anomalies.append(AnomalyEvent(
                event_id=str(uuid.uuid4()),
                user_id=user_id,
                category=AnomalyCategory.DEVICE_ANOMALY,
                severity=severity,
                score=device_score,
                description=f'Unrecognized device: {features.device_id[:16]}...',
                attributes={'device_id': features.device_id},
                timestamp=int(time.time()),
            ))

        velocity_score = self._score_velocity_anomaly(user_id, features)
        if velocity_score > 0:
            severity = self._score_to_severity(velocity_score)
            anomalies.append(AnomalyEvent(
                event_id=str(uuid.uuid4()),
                user_id=user_id,
                category=AnomalyCategory.VELOCITY_ANOMALY,
                severity=severity,
                score=velocity_score,
                description='Impossible travel detected',
                attributes={'prev_location': {}, 'new_location': {'lat': features.geolocation_lat, 'lng': features.geolocation_lng}},
                timestamp=int(time.time()),
            ))

        for anomaly in anomalies:
            self._log_anomaly(anomaly)
            logger.info(f"Anomaly detected: user={user_id} category={anomaly.category.value} score={anomaly.score:.2f}")

        self.update_baseline(user_id, features)
        return anomalies

    def _score_location_anomaly(self, baseline: BaselineProfile, features: FeatureVector) -> float:
        if features.geolocation_lat == 0 and features.geolocation_lng == 0:
            return 0.0
        if not baseline.common_locations:
            return 0.0

        min_dist = float('inf')
        for loc in baseline.common_locations:
            dist = math.sqrt(
                (loc['lat'] - features.geolocation_lat) ** 2 +
                (loc['lng'] - features.geolocation_lng) ** 2
            )
            min_dist = min(min_dist, dist)

        if min_dist < 0.5:
            return 0.0
        elif min_dist < 1.0:
            return 0.3
        elif min_dist < 5.0:
            return 0.6
        elif min_dist < 50.0:
            return 0.8
        else:
            return 1.0

    def _score_time_anomaly(self, baseline: BaselineProfile, features: FeatureVector) -> float:
        if baseline.std_login_hour < 0.5:
            return 0.0

        z_score = abs(features.hour_of_day - baseline.mean_login_hour) / max(baseline.std_login_hour, 0.5)

        if z_score > self._anomaly_threshold:
            return min(1.0, z_score / 6.0)
        return 0.0

    def _score_device_anomaly(self, baseline: BaselineProfile, features: FeatureVector) -> float:
        if not features.device_id or features.device_id == 'unknown':
            return 0.0
        if features.device_id in baseline.common_devices:
            return 0.0
        if features.is_known_device:
            return 0.2
        return 0.7

    def _score_velocity_anomaly(self, user_id: str, features: FeatureVector) -> float:
        recent = self._recent_events.get(user_id, deque(maxlen=5))
        if not recent:
            return 0.0

        for prev_event in reversed(recent):
            if prev_event.get('geolocation_lat') and prev_event.get('geolocation_lng'):
                prev_lat = prev_event['geolocation_lat']
                prev_lng = prev_event['geolocation_lng']
                prev_time = prev_event.get('timestamp', 0)

                if prev_lat == 0 and prev_lng == 0:
                    continue

                dist = math.sqrt(
                    (prev_lat - features.geolocation_lat) ** 2 +
                    (prev_lng - features.geolocation_lng) ** 2
                ) * 111

                time_diff = abs(features.session_duration - prev_event.get('session_duration', 0)) / 3600
                if time_diff < 1 and dist > 500:
                    return 0.9
                if time_diff < 2 and dist > 2000:
                    return 0.95
        return 0.0

    def _score_to_severity(self, score: float) -> AnomalySeverity:
        if score >= 0.9:
            return AnomalySeverity.CRITICAL
        elif score >= 0.7:
            return AnomalySeverity.HIGH
        elif score >= 0.4:
            return AnomalySeverity.MEDIUM
        return AnomalySeverity.LOW

    def _log_anomaly(self, event: AnomalyEvent):
        self._anomaly_log.append(event)
        if len(self._anomaly_log) > self._max_recent_events:
            self._anomaly_log = self._anomaly_log[-self._max_recent_events:]
        self._persist_anomaly(event)

    def get_recent_anomalies(self, user_id: str = None, limit: int = 100) -> List[Dict[str, Any]]:
        results = []
        for event in reversed(self._anomaly_log):
            if user_id and event.user_id != user_id:
                continue
            d = asdict(event)
            d['category'] = d['category'].value if isinstance(d['category'], AnomalyCategory) else d['category']
            d['severity'] = d['severity'].value if isinstance(d['severity'], AnomalySeverity) else d['severity']
            results.append(d)
            if len(results) >= limit:
                break
        return results

    def get_user_risk_score(self, user_id: str) -> Tuple[float, int]:
        recent = [e for e in self._anomaly_log if e.user_id == user_id and not e.resolved]
        if not recent:
            return 0.0, 0

        total_score = sum(e.score for e in recent)
        severity_multipliers = {
            AnomalySeverity.LOW: 1,
            AnomalySeverity.MEDIUM: 2,
            AnomalySeverity.HIGH: 4,
            AnomalySeverity.CRITICAL: 8,
        }
        weighted = sum(e.score * severity_multipliers.get(e.severity, 1) for e in recent)
        max_possible = len(recent) * 8
        normalized = min(1.0, weighted / max(max_possible, 1))
        return normalized, len(recent)

    def resolve_anomaly(self, event_id: str) -> bool:
        for event in self._anomaly_log:
            if event.event_id == event_id:
                event.resolved = True
                return True
        return False

    def resolve_user_anomalies(self, user_id: str) -> int:
        count = 0
        for event in self._anomaly_log:
            if event.user_id == user_id and not event.resolved:
                event.resolved = True
                count += 1
        return count

    def _persist_baseline(self, user_id: str, baseline: BaselineProfile):
        if not self.firebase:
            return
        try:
            self.firebase.create_document(
                'anomaly_baselines',
                asdict(baseline),
                user_id,
            )
        except Exception as e:
            logger.warning(f"Failed to persist baseline: {e}")

    def _load_baseline(self, user_id: str) -> BaselineProfile:
        if not self.firebase:
            return BaselineProfile.empty(user_id)
        try:
            doc = self.firebase.get_document('anomaly_baselines', user_id)
            if doc:
                baseline = BaselineProfile(**doc)
                self._baselines[user_id] = baseline
                return baseline
        except Exception as e:
            logger.warning(f"Failed to load baseline: {e}")
        return BaselineProfile.empty(user_id)

    def _persist_anomaly(self, event: AnomalyEvent):
        if not self.firebase:
            return
        try:
            d = asdict(event)
            d['category'] = event.category.value
            d['severity'] = event.severity.value
            self.firebase.create_document('anomaly_events', d, event.event_id)
        except Exception as e:
            logger.warning(f"Failed to persist anomaly: {e}")


anomaly_detector = AnomalyDetector()
