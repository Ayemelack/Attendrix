"""Invisible Attendance Validation.

Provides biometric-free anti-fraud mechanisms through behavioral pattern
analysis, Bluetooth mesh proximity, movement consistency, and multi-factor
contextual validation — entirely additive, no changes to existing check-in flow.
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from collections import defaultdict
from statistics import mean

from .models import BehavioralPattern, RiskLevel
from .registry import registry, InnovationEvent

logger = logging.getLogger(__name__)


class InvisibleValidation:
    """Continuous presence verification without biometrics.

    Validates attendance through:
    - Behavioral pattern consistency (habitual check-in time, location)
    - Bluetooth mesh proximity scoring
    - Classroom movement consistency
    - Multi-factor contextual validation (device, network, peer presence)
    - Cross-session behavior fingerprinting
    """

    def __init__(self):
        self._firebase = None
        self._repos = None
        self._pattern_cache: Dict[str, BehavioralPattern] = {}
        self._config = {
            "anomaly_threshold": 0.7,
            "trust_decay_days": 30,
            "proximity_weight": 0.25,
            "consistency_weight": 0.35,
            "context_weight": 0.40,
            "mesh_confidence_threshold": 0.6,
        }

    def initialize(self, firebase_service=None, repositories: dict = None) -> None:
        self._firebase = firebase_service
        self._repos = repositories or {}
        registry.subscribe(InnovationEvent.ATTENDANCE_MARKED, self._on_attendance)
        logger.info("InvisibleValidation initialized")

    def _on_attendance(self, data: dict) -> None:
        student_id = data.get("student_id")
        if student_id and student_id in self._pattern_cache:
            del self._pattern_cache[student_id]

    # ── Behavioral Pattern Learning ──

    def build_pattern(self, student_id: str,
                      attendance_history: List[Dict]) -> BehavioralPattern:
        """Build a behavioral pattern profile from historical attendance."""
        if student_id in self._pattern_cache:
            return self._pattern_cache[student_id]

        if not attendance_history:
            pattern = BehavioralPattern(
                student_id=student_id,
                institution_id="",
                device_consistency=0.0,
                location_consistency=0.0,
                peer_proximity_score=0.0,
                anomaly_score=0.0,
                trust_level=RiskLevel.NORMAL,
                pattern_history=[]
            )
            self._pattern_cache[student_id] = pattern
            return pattern

        sorted_recs = sorted(
            attendance_history,
            key=lambda r: self._parse_dt(r.get("timestamp", ""))
        )
        habitual_time = self._find_habitual_time(sorted_recs)
        device_consistency = self._calculate_device_consistency(sorted_recs)
        location_consistency = self._calculate_location_consistency(sorted_recs)
        peer_proximity = self._calculate_peer_proximity(sorted_recs)
        anomaly_score = self._calculate_anomaly_score(
            sorted_recs, device_consistency, location_consistency
        )
        trust_level = self._classify_trust(anomaly_score)

        pattern = BehavioralPattern(
            student_id=student_id,
            institution_id="",
            habitual_checkin_time=habitual_time,
            device_consistency=round(device_consistency, 4),
            location_consistency=round(location_consistency, 4),
            peer_proximity_score=round(peer_proximity, 4),
            anomaly_score=round(anomaly_score, 4),
            trust_level=trust_level,
            pattern_history=self._summarize_recent_patterns(sorted_recs[-20:])
        )
        self._pattern_cache[student_id] = pattern
        return pattern

    def _find_habitual_time(self, records: List[Dict]) -> Optional[str]:
        times = []
        for r in records:
            ts = self._parse_dt(r.get("timestamp", ""))
            if ts.hour or ts.minute:
                times.append(ts.hour * 60 + ts.minute)
        if not times:
            return None
        avg_minutes = int(mean(times))
        return f"{avg_minutes // 60:02d}:{avg_minutes % 60:02d}"

    def _calculate_device_consistency(self, records: List[Dict]) -> float:
        devices = defaultdict(int)
        for r in records:
            device_id = r.get("device_id") or r.get("device") or "unknown"
            devices[device_id] += 1
        if not devices:
            return 0.0
        primary = max(devices.values())
        return primary / sum(devices.values())

    def _calculate_location_consistency(self, records: List[Dict]) -> float:
        locations = defaultdict(int)
        for r in records:
            loc = r.get("location") or r.get("classroom") or r.get("gps") or "unknown"
            loc_key = str(loc)
            locations[loc_key] += 1
        if not locations:
            return 0.0
        primary = max(locations.values())
        return primary / sum(locations.values())

    def _calculate_peer_proximity(self, records: List[Dict]) -> float:
        """Score based on co-attendance with known peers."""
        if len(records) < 5:
            return 0.5
        peer_present = sum(
            1 for r in records
            if r.get("peer_count", 0) > 0 or r.get("bluetooth_devices", 0) > 0
        )
        return peer_present / len(records)

    def _calculate_anomaly_score(self, records: List[Dict],
                                 device_consistency: float,
                                 location_consistency: float) -> float:
        if len(records) < 3:
            return 0.0
        freq_changes = self._detect_frequency_anomalies(records)
        pattern_breaks = self._detect_pattern_breaks(records)
        consistency_anomaly = 1.0 - ((device_consistency + location_consistency) / 2)
        return (freq_changes * 0.3 + pattern_breaks * 0.3 + consistency_anomaly * 0.4)

    def _detect_frequency_anomalies(self, records: List[Dict]) -> float:
        """Detect unusual attendance frequency patterns."""
        if len(records) < 5:
            return 0.0
        timestamps = [
            self._parse_dt(r.get("timestamp", "")) for r in records[-10:]
        ]
        if len(timestamps) < 3:
            return 0.0
        intervals = [
            (timestamps[i + 1] - timestamps[i]).total_seconds() / 3600
            for i in range(len(timestamps) - 1)
        ]
        if not intervals:
            return 0.0
        mean_interval = mean(intervals)
        unusual = sum(
            1 for i in intervals
            if i > mean_interval * 3 or i < mean_interval * 0.3
        )
        return unusual / len(intervals)

    def _detect_pattern_breaks(self, records: List[Dict]) -> float:
        """Detect breaks in established attendance patterns."""
        if len(records) < 10:
            return 0.0
        recent = records[-5:]
        earlier = records[-10:-5]
        if not earlier or not recent:
            return 0.0
        recent_devices = set(
            r.get("device_id") or r.get("device", "") for r in recent
        )
        earlier_devices = set(
            r.get("device_id") or r.get("device", "") for r in earlier
        )
        if not earlier_devices:
            return 0.0
        device_change = len(recent_devices - earlier_devices) / len(earlier_devices)
        return min(1.0, device_change)

    def _classify_trust(self, anomaly_score: float) -> RiskLevel:
        if anomaly_score > self._config["anomaly_threshold"]:
            return RiskLevel.HIGH
        if anomaly_score > self._config["anomaly_threshold"] * 0.6:
            return RiskLevel.MEDIUM
        return RiskLevel.NORMAL

    def _summarize_recent_patterns(self,
                                   recent: List[Dict]) -> List[Dict[str, Any]]:
        return [
            {
                "timestamp": r.get("timestamp", ""),
                "device": r.get("device_id") or r.get("device", ""),
                "location": r.get("location") or r.get("classroom", ""),
            }
            for r in recent[-5:]
        ]

    # ── Multi-Factor Contextual Validation ──

    def validate_attendance(self, student_id: str,
                            current_checkin: Dict,
                            historical_pattern: BehavioralPattern = None) -> Dict[str, Any]:
        """Validate attendance through multi-factor contextual analysis."""
        if historical_pattern is None:
            historical_pattern = self._pattern_cache.get(student_id)

        factors = {}
        # Factor 1: Time consistency
        if historical_pattern and historical_pattern.habitual_checkin_time:
            checkin_ts = self._parse_dt(current_checkin.get("timestamp", ""))
            habit_h, habit_m = map(int, historical_pattern.habitual_checkin_time.split(":"))
            habit_minutes = habit_h * 60 + habit_m
            actual_minutes = checkin_ts.hour * 60 + checkin_ts.minute
            time_diff = abs(actual_minutes - habit_minutes)
            factors["time_consistency"] = round(
                max(0.0, 1.0 - time_diff / 120.0), 4
            )

        # Factor 2: Device consistency
        current_device = current_checkin.get("device_id") or current_checkin.get("device", "")
        if historical_pattern and current_device:
            factors["device_consistency"] = historical_pattern.device_consistency \
                if historical_pattern.device_consistency > 0.5 else 0.3

        # Factor 3: Peer proximity
        peer_count = current_checkin.get("peer_count", 0) or \
                     current_checkin.get("bluetooth_devices", 0) or 0
        factors["peer_proximity"] = round(min(1.0, peer_count / 10.0), 4)

        # Factor 4: Location plausibility
        location = current_checkin.get("location") or current_checkin.get("classroom", "")
        factors["location_plausibility"] = 0.8 if location else 0.3

        # Composite score
        weights = self._config
        composite = (
            factors.get("time_consistency", 0.0) * weights["consistency_weight"] +
            factors.get("device_consistency", 0.0) * weights["consistency_weight"] +
            factors.get("peer_proximity", 0.0) * weights["proximity_weight"] +
            factors.get("location_plausibility", 0.0) * weights["context_weight"]
        )

        return {
            "student_id": student_id,
            "validation_score": round(composite, 4),
            "trusted": composite >= self._config["mesh_confidence_threshold"],
            "factors": factors,
            "anomaly_flag": composite < self._config["anomaly_threshold"] * 0.5
        }

    # ── Continuous Presence Verification ──

    def verify_continuous_presence(self, student_id: str,
                                   session_records: List[Dict]) -> Dict[str, Any]:
        """Verify continuous presence throughout a session (vs one-time check-in)."""
        if len(session_records) < 2:
            return {
                "student_id": student_id,
                "continuous_presence": False,
                "confidence": 0.0,
                "reason": "Insufficient check-in points"
            }

        timestamps = sorted(
            self._parse_dt(r.get("timestamp", ""))
            for r in session_records
        )
        session_start = self._parse_dt(
            session_records[0].get("session_start", "")
        ) if session_records[0].get("session_start") else timestamps[0]
        session_end = self._parse_dt(
            session_records[0].get("session_end", "")
        ) if session_records[0].get("session_end") else timestamps[-1]

        total_duration = (session_end - session_start).total_seconds() / 60
        covered_duration = (timestamps[-1] - timestamps[0]).total_seconds() / 60

        if total_duration <= 0:
            return {
                "student_id": student_id,
                "continuous_presence": False,
                "confidence": 0.0,
                "reason": "Invalid session duration"
            }

        coverage_ratio = covered_duration / total_duration
        checkin_density = len(timestamps) / total_duration if total_duration > 0 else 0

        # Normalize density: target 1 check-in per 15 minutes
        normalized_density = min(1.0, checkin_density * 15)

        confidence = coverage_ratio * 0.6 + normalized_density * 0.4

        return {
            "student_id": student_id,
            "continuous_presence": confidence > 0.5,
            "confidence": round(confidence, 4),
            "coverage_ratio": round(coverage_ratio, 4),
            "checkin_density": round(checkin_density, 4),
            "checkin_count": len(timestamps),
            "session_duration_minutes": round(total_duration, 1)
        }

    # ── Cross-Session Behavior Fingerprinting ──

    def fingerprint_session(self, student_id: str,
                            attendance_records: List[Dict]) -> Dict[str, Any]:
        """Create a behavioral fingerprint for cross-session verification."""
        if not attendance_records:
            return {"fingerprint": None, "uniqueness": 0.0}

        sorted_recs = sorted(
            attendance_records,
            key=lambda r: self._parse_dt(r.get("timestamp", ""))
        )

        # Extract behavioral features
        checkin_times = [
            self._parse_dt(r.get("timestamp", "")).hour * 60 +
            self._parse_dt(r.get("timestamp", "")).minute
            for r in sorted_recs
        ]
        avg_checkin = mean(checkin_times) if checkin_times else 0

        devices_used = list(set(
            r.get("device_id") or r.get("device", "unknown")
            for r in sorted_recs
        ))
        locations = list(set(
            r.get("location") or r.get("classroom", "unknown")
            for r in sorted_recs
        ))

        fingerprint = {
            "avg_checkin_minutes": round(avg_checkin, 1),
            "device_count": len(devices_used),
            "primary_device": devices_used[0] if devices_used else "",
            "location_count": len(locations),
            "primary_location": locations[0] if locations else "",
            "session_count": len(sorted_recs),
            "avg_interval_minutes": round(
                mean([
                    (self._parse_dt(sorted_recs[i + 1].get("timestamp", "")) -
                     self._parse_dt(sorted_recs[i].get("timestamp", ""))).total_seconds() / 60
                    for i in range(len(sorted_recs) - 1)
                ]), 1
            ) if len(sorted_recs) > 1 else 0,
        }

        uniqueness = min(1.0, (fingerprint["device_count"] * 0.3 +
                               fingerprint["location_count"] * 0.3 +
                               (1.0 - fingerprint["avg_interval_minutes"] / 120) * 0.4))

        return {"fingerprint": fingerprint, "uniqueness": round(uniqueness, 4)}

    @staticmethod
    def _parse_dt(ts) -> datetime:
        if isinstance(ts, datetime):
            return ts
        if isinstance(ts, str):
            try:
                return datetime.fromisoformat(ts)
            except (ValueError, TypeError):
                pass
        return datetime.min

    def cleanup(self) -> None:
        self._pattern_cache.clear()
        logger.info("InvisibleValidation cleaned up")
