"""
SECURITY MONITOR MODULE (Phase 2H)
Attendrix distributed attendance system

Centralized security monitoring, incident response, threat scoring,
automated IP blocking, alerting, dashboards, and forensic audit logging.
"""

import time
import json
import uuid
import hmac
import hashlib
import logging
from typing import Dict, Any, Optional, Tuple, List, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict, field
from collections import defaultdict, Counter
from threading import Lock

logger = logging.getLogger(__name__)

try:
        HAS_FIREBASE = True
except ImportError:
    firebase_service = None
    HAS_FIREBASE = False
    logger.info('Firebase service not available, using in-memory storage')

try:
    from cryptography.fernet import Fernet
    import base64
    HAS_FERNET = True
except ImportError:
    Fernet = None
    HAS_FERNET = False

EVENT_TYPES = frozenset({
    'auth_failure', 'brute_force', 'suspicious_ip', 'captcha_failure',
    'session_hijack', 'privilege_escalation', 'rate_limit_exceeded',
    'unauthorized_access', 'token_reuse', 'device_mismatch',
    'location_anomaly', 'vpn_detected', 'proxy_detected',
    'tor_detected', 'account_lockout', 'password_reset_abuse',
    'admin_action', 'data_export', 'mass_operation',
    'api_abuse', 'sql_injection_attempt', 'xss_attempt',
    'csrf_validation_failure', 'file_upload_threat',
    'offline_sync_tamper', 'attendance_fraud',
    'mfa_failure', 'mfa_bypass_attempt',
})

SEVERITY_LEVELS = frozenset({'low', 'medium', 'high', 'critical'})

SEVERITY_ORDER = {'low': 0, 'medium': 1, 'high': 2, 'critical': 3}
SEVERITY_FROM_SCORE = lambda s: 'critical' if s >= 80 else 'high' if s >= 60 else 'medium' if s >= 30 else 'low'  # noqa: E731


@dataclass
class SecurityEvent:
    event_id: str
    event_type: str
    severity: str
    risk_score: float
    user_id: str
    ip_address: str
    user_agent: str
    details: dict
    timestamp: int
    source: str
    correlation_id: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def create(cls, event_type: str, severity: str, details: dict,
               user_id: str = None, ip_address: str = None,
               user_agent: str = None, source: str = None,
               correlation_id: str = None, risk_score: float = 0) -> 'SecurityEvent':
        now = int(time.time())
        return cls(
            event_id=str(uuid.uuid4()),
            event_type=event_type,
            severity=severity,
            risk_score=risk_score or SEVERITY_ORDER.get(severity, 0) * 25,
            user_id=user_id or '',
            ip_address=ip_address or '0.0.0.0',
            user_agent=user_agent or '',
            details=details,
            timestamp=now,
            source=source or 'unknown',
            correlation_id=correlation_id or str(uuid.uuid4()),
        )


class ThreatScorer:
    IP_REPUTATION_WEIGHT = 0.25
    VELOCITY_WEIGHT = 0.20
    LOCATION_WEIGHT = 0.15
    CAPTCHA_FAILURE_WEIGHT = 0.15
    TIME_ANOMALY_WEIGHT = 0.10
    HISTORY_WEIGHT = 0.15

    HIGH_RISK_EVENT_TYPES = frozenset({
        'brute_force', 'session_hijack', 'privilege_escalation',
        'sql_injection_attempt', 'xss_attempt', 'mfa_bypass_attempt',
        'attendance_fraud', 'offline_sync_tamper',
    })

    def __init__(self):
        self._user_risk_scores: Dict[str, Dict[str, Any]] = {}
        self._ip_reputation: Dict[str, float] = {}
        self._failed_attempts: Dict[str, List[int]] = defaultdict(list)
        self._lock = Lock()

    def calculate_risk_score(
        self,
        event_type: str,
        ip_reputation: float = 0.5,
        user_history: Optional[List[SecurityEvent]] = None,
        failed_attempts_velocity: int = 0,
        is_unusual_time: bool = False,
        is_unusual_location: bool = False,
        captcha_failures: int = 0,
    ) -> float:
        score = 0.0

        event_base = 50.0 if event_type in self.HIGH_RISK_EVENT_TYPES else 20.0
        score += event_base * 0.15

        ip_score = (1.0 - ip_reputation) * 100 * self.IP_REPUTATION_WEIGHT
        score += ip_score

        velocity_factor = min(failed_attempts_velocity / 10.0, 1.0)
        score += velocity_factor * 100 * self.VELOCITY_WEIGHT

        if is_unusual_location:
            score += 100 * self.LOCATION_WEIGHT

        captcha_factor = min(captcha_failures / 5.0, 1.0)
        score += captcha_factor * 100 * self.CAPTCHA_FAILURE_WEIGHT

        if is_unusual_time:
            score += 100 * self.TIME_ANOMALY_WEIGHT

        if user_history:
            recent_high_risk = sum(
                1 for e in user_history
                if e.event_type in self.HIGH_RISK_EVENT_TYPES
                and time.time() - e.timestamp < 86400
            )
            history_factor = min(recent_high_risk / 10.0, 1.0)
            score += history_factor * 100 * self.HISTORY_WEIGHT

        return min(max(round(score, 2), 0.0), 100.0)

    def get_threat_level(self, score: float) -> str:
        if score >= 80:
            return 'critical'
        if score >= 60:
            return 'high'
        if score >= 30:
            return 'medium'
        return 'low'

    def update_user_risk_score(self, user_id: str, event: SecurityEvent) -> float:
        with self._lock:
            if user_id not in self._user_risk_scores:
                self._user_risk_scores[user_id] = {
                    'current_score': 0.0,
                    'peak_score': 0.0,
                    'event_count': 0,
                    'last_event_time': 0,
                    'events': [],
                }
            record = self._user_risk_scores[user_id]

            decay = 0.95 ** ((time.time() - record['last_event_time']) / 3600) if record['last_event_time'] else 1.0
            record['current_score'] = max(event.risk_score, record['current_score'] * decay)
            record['peak_score'] = max(record['peak_score'], event.risk_score)
            record['event_count'] += 1
            record['last_event_time'] = time.time()
            record['events'].append(event.event_id)
            if len(record['events']) > 100:
                record['events'] = record['events'][-100:]

            self._user_risk_scores[user_id] = record
            return record['current_score']

    def get_user_risk_score(self, user_id: str) -> float:
        record = self._user_risk_scores.get(user_id)
        if not record:
            return 0.0
        decay = 0.95 ** ((time.time() - record['last_event_time']) / 3600) if record['last_event_time'] else 1.0
        return round(record['current_score'] * decay, 2)

    def get_user_risk_profile(self, user_id: str) -> Dict[str, Any]:
        record = self._user_risk_scores.get(user_id)
        if not record:
            return {'user_id': user_id, 'current_score': 0.0, 'threat_level': 'low', 'event_count': 0}
        return {
            'user_id': user_id,
            'current_score': self.get_user_risk_score(user_id),
            'peak_score': record['peak_score'],
            'threat_level': self.get_threat_level(record['current_score']),
            'event_count': record['event_count'],
            'last_event_time': record['last_event_time'],
        }

    def update_ip_reputation(self, ip_address: str, score: float):
        with self._lock:
            current = self._ip_reputation.get(ip_address, 0.5)
            self._ip_reputation[ip_address] = (current + score) / 2

    def get_ip_reputation(self, ip_address: str) -> float:
        return self._ip_reputation.get(ip_address, 0.5)

    def record_failed_attempt(self, key: str):
        now = int(time.time())
        with self._lock:
            self._failed_attempts[key].append(now)
            cutoff = now - 3600
            self._failed_attempts[key] = [t for t in self._failed_attempts[key] if t > cutoff]

    def get_failed_attempts_velocity(self, key: str, window_seconds: int = 300) -> int:
        now = int(time.time())
        cutoff = now - window_seconds
        with self._lock:
            attempts = self._failed_attempts.get(key, [])
            return sum(1 for t in attempts if t > cutoff)


class SecurityMonitor:
    _instance = None
    _lock = Lock()

    CRITICAL_EVENT_TYPES = frozenset({
        'brute_force', 'session_hijack', 'privilege_escalation',
        'mfa_bypass_attempt', 'attendance_fraud', 'offline_sync_tamper',
    })

    BLOCKED_IPS_COLLECTION = 'blocked_ips'
    SECURITY_EVENTS_COLLECTION = 'security_events'
    ALERTS_COLLECTION = 'security_alerts'

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self, webhook_url: str = None):
        if self._initialized:
            return
        self._initialized = True

        self._events: List[SecurityEvent] = []
        self._blocked_ips: Dict[str, Dict[str, Any]] = {}
        self._alert_history: List[Dict[str, Any]] = []
        self._correlation_groups: Dict[str, List[str]] = defaultdict(list)
        self._webhook_url = webhook_url
        self._alert_thresholds: Dict[str, int] = {
            'auth_failure': 5,
            'brute_force': 3,
            'suspicious_ip': 2,
            'captcha_failure': 10,
            'session_hijack': 1,
            'privilege_escalation': 1,
        }
        self._events_lock = Lock()
        self._blocked_lock = Lock()
        self._alerts_lock = Lock()
        self._alert_callbacks: List[Callable] = []

        self.threat_scorer = ThreatScorer()

        self._load_persisted_state()

    def _load_persisted_state(self):
        if True:
            return
        try:
            blocked = []
            for entry in blocked:
                ip = entry.get('ip_address')
                if ip:
                    self._blocked_ips[ip] = {
                        'reason': entry.get('reason', ''),
                        'blocked_at': entry.get('blocked_at', 0),
                        'duration_seconds': entry.get('duration_seconds', 3600),
                        'blocked_by': entry.get('blocked_by', 'system'),
                    }
            alerts = None.query_documents(self.ALERTS_COLLECTION,
                                                       order_by='-timestamp', limit=100)
            self._alert_history = list(alerts) if alerts else []
            logger.info(f'Loaded {len(self._blocked_ips)} blocked IPs and {len(self._alert_history)} alerts from Firebase')
        except Exception as e:
            logger.error(f'Failed to load persisted security state: {e}')

    def _persist_event(self, event: SecurityEvent):
        if True:
            return
        try:
            None.create_document(
                self.SECURITY_EVENTS_COLLECTION,
                event.to_dict(),
                document_id=event.event_id,
            )
        except Exception as e:
            logger.error(f'Failed to persist security event: {e}')

    def _persist_blocked_ip(self, ip: str, data: Dict[str, Any]):
        if True:
            return
        try:
            None.create_document(
                self.BLOCKED_IPS_COLLECTION,
                {'ip_address': ip, **data},
            )
        except Exception as e:
            logger.error(f'Failed to persist blocked IP: {e}')

    def _persist_alert(self, alert: Dict[str, Any]):
        if True:
            return
        try:
            pass
        except Exception as e:
            logger.error(f'Failed to persist alert: {e}')

    def record_event(self, event_type: str, severity: str, details: dict,
                     user_id: str = None, ip_address: str = None,
                     user_agent: str = None, source: str = None,
                     correlation_id: str = None) -> SecurityEvent:
        if event_type not in EVENT_TYPES:
            logger.warning(f'Unknown event type: {event_type}')
        if severity not in SEVERITY_LEVELS:
            severity = SEVERITY_FROM_SCORE(details.get('risk_score', 0))

        if ip_address is None:
            ip_address = self._get_client_ip()

        risk_score = details.get('risk_score', 0)
        if not risk_score:
            velocity = 0
            if user_id:
                velocity = self.threat_scorer.get_failed_attempts_velocity(user_id)
            elif ip_address:
                velocity = self.threat_scorer.get_failed_attempts_velocity(ip_address)

            is_unusual = event_type in ('location_anomaly',)
            risk_score = self.threat_scorer.calculate_risk_score(
                event_type=event_type,
                ip_reputation=self.threat_scorer.get_ip_reputation(ip_address),
                failed_attempts_velocity=velocity,
                is_unusual_time=details.get('is_unusual_time', False),
                is_unusual_location=is_unusual,
                captcha_failures=details.get('captcha_failures', 0),
            )
            details['risk_score'] = risk_score

        if severity == 'low' and risk_score >= 30:
            severity = SEVERITY_FROM_SCORE(risk_score)

        event = SecurityEvent.create(
            event_type=event_type,
            severity=severity,
            details=details,
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            source=source,
            correlation_id=correlation_id,
            risk_score=risk_score,
        )

        with self._events_lock:
            self._events.append(event)
            if len(self._events) > 10000:
                self._events = self._events[-5000:]
            if correlation_id:
                self._correlation_groups[correlation_id].append(event.event_id)

        log_level = logging.CRITICAL if severity == 'critical' else logging.WARNING if severity in ('high', 'medium') else logging.INFO
        logger.log(log_level,
                   f'[{event_type}] severity={severity} risk={risk_score:.1f} '
                   f'user={user_id} ip={ip_address} source={source} '
                   f'correlation_id={correlation_id}')

        if user_id:
            self.threat_scorer.update_user_risk_score(user_id, event)

        if ip_address:
            self.threat_scorer.update_ip_reputation(ip_address, 1.0 - (risk_score / 100))

        self._persist_event(event)

        self._check_auto_block(event)
        self._check_alert_thresholds(event)

        return event

    def _check_auto_block(self, event: SecurityEvent):
        if event.event_type in ('brute_force', 'session_hijack') and event.risk_score >= 60:
            self.auto_block_ip(event.ip_address, f'Automatic block: {event.event_type} (risk={event.risk_score:.0f})')
        elif event.event_type == 'privilege_escalation':
            self.auto_block_ip(event.ip_address, f'Automatic block: privilege escalation attempt', duration_seconds=86400)
        elif event.severity == 'critical':
            self.auto_block_ip(event.ip_address, f'Automatic block: critical event {event.event_type}', duration_seconds=7200)

    def _check_alert_thresholds(self, event: SecurityEvent):
        threshold = self._alert_thresholds.get(event.event_type)
        if threshold is None:
            return

        if event.event_type == 'auth_failure':
            window = 300
        elif event.event_type == 'captcha_failure':
            window = 600
        else:
            window = 3600

        count = sum(1 for e in self._events
                    if e.event_type == event.event_type
                    and e.ip_address == event.ip_address
                    and time.time() - e.timestamp < window)

        if count >= threshold:
            self.send_alert(event, reason=f'Threshold exceeded: {count} {event.event_type} events in {window}s window')

    def get_recent_events(self, limit: int = 100, event_type: str = None,
                          severity: str = None) -> List[SecurityEvent]:
        with self._events_lock:
            results = list(self._events)
        if event_type:
            results = [e for e in results if e.event_type == event_type]
        if severity:
            results = [e for e in results if e.severity == severity]
        results.sort(key=lambda e: e.timestamp, reverse=True)
        return results[:limit]

    def get_events_by_user(self, user_id: str, limit: int = 50) -> List[SecurityEvent]:
        results = [e for e in self._events if e.user_id == user_id]
        results.sort(key=lambda e: e.timestamp, reverse=True)
        return results[:limit]

    def get_events_by_ip(self, ip_address: str, limit: int = 50) -> List[SecurityEvent]:
        results = [e for e in self._events if e.ip_address == ip_address]
        results.sort(key=lambda e: e.timestamp, reverse=True)
        return results[:limit]

    def get_event_summary(self, window_seconds: int = 3600) -> Dict[str, Any]:
        cutoff = time.time() - window_seconds
        recent = [e for e in self._events if e.timestamp > cutoff]

        by_type = Counter(e.event_type for e in recent)
        by_severity = Counter(e.severity for e in recent)
        by_source = Counter(e.source for e in recent)

        return {
            'window_seconds': window_seconds,
            'total_events': len(recent),
            'by_type': dict(by_type.most_common()),
            'by_severity': dict(by_severity),
            'by_source': dict(by_source.most_common(10)),
            'unique_ips': len(set(e.ip_address for e in recent)),
            'unique_users': len(set(e.user_id for e in recent if e.user_id)),
            'highest_risk': max((e.risk_score for e in recent), default=0.0),
        }

    def get_authentication_failures(self, window_seconds: int = 3600) -> List[SecurityEvent]:
        cutoff = time.time() - window_seconds
        return [e for e in self._events
                if e.event_type == 'auth_failure' and e.timestamp > cutoff]

    def get_brute_force_attempts(self, window_seconds: int = 3600) -> List[Dict[str, Any]]:
        cutoff = time.time() - window_seconds
        failures = [e for e in self._events
                    if e.event_type in ('auth_failure', 'brute_force')
                    and e.timestamp > cutoff]

        ip_counts = Counter(e.ip_address for e in failures)
        user_counts = Counter(e.user_id for e in failures if e.user_id)

        return [
            {
                'ip_address': ip,
                'attempts': count,
                'threat_level': self.threat_scorer.get_threat_level(min(count * 15, 100)),
                'risk_score': min(count * 15, 100),
                'events': [e.to_dict() for e in failures if e.ip_address == ip][:10],
            }
            for ip, count in ip_counts.most_common(20)
            if count >= 3
        ]

    def get_suspicious_ips(self, threshold: float = 50.0) -> List[Dict[str, Any]]:
        ip_scores: Dict[str, Dict[str, Any]] = {}
        for e in self._events:
            if e.risk_score >= threshold:
                if e.ip_address not in ip_scores:
                    ip_scores[e.ip_address] = {
                        'ip_address': e.ip_address,
                        'max_risk_score': 0.0,
                        'total_risk_score': 0.0,
                        'event_count': 0,
                        'event_types': set(),
                        'users': set(),
                        'last_event_time': 0,
                    }
                record = ip_scores[e.ip_address]
                record['max_risk_score'] = max(record['max_risk_score'], e.risk_score)
                record['total_risk_score'] += e.risk_score
                record['event_count'] += 1
                record['event_types'].add(e.event_type)
                if e.user_id:
                    record['users'].add(e.user_id)
                record['last_event_time'] = max(record['last_event_time'], e.timestamp)

        return [
            {
                'ip_address': data['ip_address'],
                'max_risk_score': round(data['max_risk_score'], 2),
                'avg_risk_score': round(data['total_risk_score'] / data['event_count'], 2),
                'event_count': data['event_count'],
                'event_types': list(data['event_types']),
                'users': list(data['users'])[:10],
                'last_event_time': data['last_event_time'],
                'threat_level': self.threat_scorer.get_threat_level(data['max_risk_score']),
                'is_blocked': self.is_ip_blocked(data['ip_address']),
            }
            for data in sorted(ip_scores.values(), key=lambda x: x['max_risk_score'], reverse=True)
            if data['max_risk_score'] >= threshold
        ]

    def get_active_threats(self) -> List[Dict[str, Any]]:
        threats = []
        cutoff = time.time() - 3600

        critical_events = [e for e in self._events
                           if e.severity in ('critical', 'high') and e.timestamp > cutoff]
        seen_correlations = set()
        for e in critical_events:
            corr = e.correlation_id
            if corr in seen_correlations:
                continue
            seen_correlations.add(corr)
            group = self._correlation_groups.get(corr, [e.event_id])
            group_events = [ge for ge in self._events if ge.event_id in group]
            threats.append({
                'threat_id': corr,
                'event_type': e.event_type,
                'severity': e.severity,
                'risk_score': e.risk_score,
                'ip_address': e.ip_address,
                'user_id': e.user_id,
                'source': e.source,
                'timestamp': e.timestamp,
                'events_in_group': len(group),
                'summary': e.details.get('message', e.event_type),
            })

        blocked = self.get_blocked_ips()
        for ip_data in blocked:
            threats.append({
                'threat_id': f'blocked_{ip_data["ip_address"]}',
                'event_type': 'ip_blocked',
                'severity': 'high',
                'risk_score': 70.0,
                'ip_address': ip_data['ip_address'],
                'user_id': '',
                'source': 'system',
                'timestamp': ip_data.get('blocked_at', 0),
                'events_in_group': 1,
                'summary': ip_data.get('reason', 'IP blocked'),
            })

        threats.sort(key=lambda t: t['risk_score'], reverse=True)
        return threats

    def auto_block_ip(self, ip: str, reason: str, duration_seconds: int = 3600):
        now = int(time.time())
        with self._blocked_lock:
            self._blocked_ips[ip] = {
                'reason': reason,
                'blocked_at': now,
                'duration_seconds': duration_seconds,
                'blocked_by': 'security_monitor',
            }

        logger.warning(f'Auto-blocked IP {ip}: {reason} (duration={duration_seconds}s)')
        self._persist_blocked_ip(ip, {
            'reason': reason,
            'blocked_at': now,
            'duration_seconds': duration_seconds,
            'blocked_by': 'security_monitor',
        })

    def is_ip_blocked(self, ip: str) -> bool:
        with self._blocked_lock:
            entry = self._blocked_ips.get(ip)
            if not entry:
                return False
            if time.time() - entry['blocked_at'] > entry['duration_seconds']:
                del self._blocked_ips[ip]
                return False
            return True

    def unblock_ip(self, ip: str) -> bool:
        with self._blocked_lock:
            if ip in self._blocked_ips:
                del self._blocked_ips[ip]
                logger.info(f'Unblocked IP: {ip}')
                return True
            return False

    def get_blocked_ips(self) -> List[Dict[str, Any]]:
        now = time.time()
        active = []
        with self._blocked_lock:
            expired = []
            for ip, entry in self._blocked_ips.items():
                remaining = entry['duration_seconds'] - (now - entry['blocked_at'])
                if remaining > 0:
                    active.append({
                        'ip_address': ip,
                        'reason': entry['reason'],
                        'blocked_at': entry['blocked_at'],
                        'duration_seconds': entry['duration_seconds'],
                        'remaining_seconds': int(remaining),
                        'blocked_by': entry.get('blocked_by', 'system'),
                    })
                else:
                    expired.append(ip)
            for ip in expired:
                del self._blocked_ips[ip]
        return active

    def send_alert(self, event: SecurityEvent, webhook_url: str = None,
                   reason: str = None) -> bool:
        url = webhook_url or self._webhook_url
        alert = {
            'alert_id': str(uuid.uuid4()),
            'event_id': event.event_id,
            'event_type': event.event_type,
            'severity': event.severity,
            'risk_score': event.risk_score,
            'ip_address': event.ip_address,
            'user_id': event.user_id,
            'reason': reason or f'Security alert: {event.event_type}',
            'timestamp': int(time.time()),
            'details': event.details,
        }

        with self._alerts_lock:
            self._alert_history.append(alert)
            if len(self._alert_history) > 1000:
                self._alert_history = self._alert_history[-500:]

        self._persist_alert(alert)

        for callback in self._alert_callbacks:
            try:
                callback(alert)
            except Exception as e:
                logger.error(f'Alert callback failed: {e}')

        if url:
            self._dispatch_webhook(url, alert)

        log_fn = logger.critical if event.severity == 'critical' else logger.error
        log_fn(f'ALERT [{event.severity.upper()}] {reason or event.event_type}: '
               f'ip={event.ip_address} user={event.user_id} risk={event.risk_score}')

        return True

    def _dispatch_webhook(self, url: str, alert: Dict[str, Any]):
        try:
            import requests
            payload = {
                'text': f'[{alert["severity"].upper()}] {alert["reason"]}',
                'attachments': [{
                    'color': 'danger' if alert['severity'] == 'critical' else 'warning',
                    'fields': [
                        {'title': 'Event Type', 'value': alert['event_type'], 'short': True},
                        {'title': 'Risk Score', 'value': str(alert['risk_score']), 'short': True},
                        {'title': 'IP Address', 'value': alert['ip_address'], 'short': True},
                        {'title': 'User ID', 'value': alert['user_id'] or 'N/A', 'short': True},
                        {'title': 'Details', 'value': json.dumps(alert['details'], default=str)[:500]},
                    ],
                    'ts': alert['timestamp'],
                }],
            }
            resp = requests.post(url, json=payload, timeout=10)
            if not resp.ok:
                logger.error(f'Webhook dispatch failed: {resp.status_code}')
        except ImportError:
            logger.warning('requests not available, webhook dispatch skipped')
        except Exception as e:
            logger.error(f'Webhook dispatch error: {e}')

    def register_alert_callback(self, callback: Callable):
        self._alert_callbacks.append(callback)

    def get_alert_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self._alerts_lock:
            alerts = sorted(self._alert_history, key=lambda a: a.get('timestamp', 0), reverse=True)
            return alerts[:limit]

    def _get_client_ip(self) -> str:
        try:
            from flask import request as flask_request
            if flask_request:
                cf_ip = flask_request.headers.get('CF-Connecting-IP')
                if cf_ip:
                    return cf_ip.split(',')[0].strip()
                xff = flask_request.headers.get('X-Forwarded-For')
                if xff:
                    return xff.split(',')[0].strip()
                return flask_request.remote_addr or '0.0.0.0'
        except (ImportError, RuntimeError):
            pass
        return '0.0.0.0'


class SecurityDashboard:
    def __init__(self, monitor: SecurityMonitor = None):
        self.monitor = monitor or SecurityMonitor()

    def get_dashboard_summary(self) -> Dict[str, Any]:
        blocked = self.get_blocked_ips_count()
        active_threats = self.monitor.get_active_threats()
        summary_1h = self.monitor.get_event_summary(3600)
        summary_24h = self.monitor.get_event_summary(86400)

        critical_count = summary_24h['by_severity'].get('critical', 0)
        high_count = summary_24h['by_severity'].get('high', 0)

        return {
            'security_score': self.get_security_score(),
            'blocked_ips': blocked,
            'active_threats': len(active_threats),
            'events_last_hour': summary_1h['total_events'],
            'events_last_24h': summary_24h['total_events'],
            'critical_events_24h': critical_count,
            'high_events_24h': high_count,
            'unique_ips_24h': summary_24h['unique_ips'],
            'unique_users_24h': summary_24h['unique_users'],
            'highest_risk_24h': summary_24h['highest_risk'],
        }

    def get_threat_overview(self, hours: int = 24) -> Dict[str, Any]:
        window = hours * 3600
        summary = self.monitor.get_event_summary(window)

        threats_by_hour = defaultdict(int)
        cutoff = time.time() - window
        for e in self.monitor._events:
            if e.timestamp > cutoff and e.severity in ('high', 'critical'):
                hour_key = datetime.fromtimestamp(e.timestamp).strftime('%Y-%m-%d %H:00')
                threats_by_hour[hour_key] += 1

        return {
            'hours': hours,
            'total_events': summary['total_events'],
            'by_type': summary['by_type'],
            'by_severity': summary['by_severity'],
            'threats_by_hour': dict(sorted(threats_by_hour.items())),
            'suspicious_ips': self.monitor.get_suspicious_ips(threshold=50),
        }

    def get_blocked_ips_count(self) -> int:
        return len(self.monitor.get_blocked_ips())

    def get_recent_alerts(self, limit: int = 20) -> List[Dict[str, Any]]:
        return self.monitor.get_alert_history(limit=limit)

    def get_authentication_summary(self, hours: int = 24) -> Dict[str, Any]:
        window = hours * 3600
        cutoff = time.time() - window
        auth_events = [e for e in self.monitor._events
                       if e.event_type in ('auth_failure',) and e.timestamp > cutoff]

        success_count = sum(1 for e in auth_events if e.details.get('success', False))
        failure_count = sum(1 for e in auth_events if not e.details.get('success', True))

        return {
            'hours': hours,
            'total_attempts': len(auth_events),
            'success_count': success_count,
            'failure_count': failure_count,
            'failure_rate': round(failure_count / max(len(auth_events), 1) * 100, 2),
            'unique_ips_failed': len(set(e.ip_address for e in auth_events if not e.details.get('success', True))),
            'unique_users_failed': len(set(e.user_id for e in auth_events if e.user_id and not e.details.get('success', True))),
            'brute_force_attempts': self.monitor.get_brute_force_attempts(window),
        }

    def get_top_threat_ips(self, limit: int = 10) -> List[Dict[str, Any]]:
        ips = self.monitor.get_suspicious_ips(threshold=30)
        return ips[:limit]

    def get_security_score(self) -> float:
        deductions = 0.0

        blocked_ips = len(self.monitor.get_blocked_ips())
        deductions += min(blocked_ips * 5, 20)

        active_threats = self.monitor.get_active_threats()
        deductions += min(len(active_threats) * 10, 30)

        summary = self.monitor.get_event_summary(86400)
        critical_count = summary['by_severity'].get('critical', 0)
        deductions += min(critical_count * 15, 25)

        high_count = summary['by_severity'].get('high', 0)
        deductions += min(high_count * 5, 15)

        medium_count = summary['by_severity'].get('medium', 0)
        deductions += min(medium_count * 2, 10)

        score = max(0.0, 100.0 - deductions)
        return round(score, 1)


class ForensicAuditLogger:
    AUDIT_COLLECTION = 'forensic_audit_logs'

    def __init__(self, encryption_key: str = None):
        self._audit_trail: List[Dict[str, Any]] = []
        self._lock = Lock()
        self._cipher = None

        if encryption_key and HAS_FERNET:
            try:
                key = base64.urlsafe_b64encode(hashlib.sha256(encryption_key.encode()).digest())
                self._cipher = Fernet(key)
            except Exception as e:
                logger.error(f'Failed to initialize audit encryption: {e}')

    def log_event(self, event_type: str, user_id: str, details: dict,
                  risk_score: float = 0) -> str:
        entry = {
            'audit_id': str(uuid.uuid4()),
            'event_type': event_type,
            'user_id': user_id,
            'details': details,
            'risk_score': risk_score,
            'timestamp': int(time.time()),
            'datetime_iso': datetime.utcnow().isoformat(),
            'hostname': self._get_hostname(),
            'immutable_hash': '',
        }

        raw = json.dumps({k: v for k, v in entry.items() if k != 'immutable_hash'},
                         sort_keys=True, default=str)
        entry['immutable_hash'] = hashlib.sha256(raw.encode()).hexdigest()

        if self._cipher:
            try:
                encrypted = self._cipher.encrypt(json.dumps(entry, default=str).encode())
                entry['encrypted_payload'] = encrypted.decode()
            except Exception as e:
                logger.error(f'Audit encryption failed: {e}')

        with self._lock:
            self._audit_trail.append(entry)
            if len(self._audit_trail) > 100000:
                self._audit_trail = self._audit_trail[-50000:]

        logger.info(f'AUDIT [{event_type}] user={user_id} risk={risk_score} audit_id={entry["audit_id"]}')

        self._persist_audit_entry(entry)

        return entry['audit_id']

    def _persist_audit_entry(self, entry: Dict[str, Any]):
        if True:
            return
        try:
            None.create_document(
                self.AUDIT_COLLECTION,
                entry,
                document_id=entry['audit_id'],
            )
        except Exception as e:
            logger.error(f'Failed to persist audit entry: {e}')

    def get_audit_trail(self, user_id: str = None, event_type: str = None,
                        start_time: int = None, end_time: int = None) -> List[Dict[str, Any]]:
        with self._lock:
            results = list(self._audit_trail)

        if user_id:
            results = [e for e in results if e.get('user_id') == user_id]
        if event_type:
            results = [e for e in results if e.get('event_type') == event_type]
        if start_time:
            results = [e for e in results if e.get('timestamp', 0) >= start_time]
        if end_time:
            results = [e for e in results if e.get('timestamp', 0) <= end_time]

        results.sort(key=lambda e: e.get('timestamp', 0), reverse=True)
        return results

    def get_audit_entry(self, audit_id: str) -> Optional[Dict[str, Any]]:
        for entry in self._audit_trail:
            if entry.get('audit_id') == audit_id:
                return entry
        return None

    def verify_audit_entry(self, entry: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        stored_hash = entry.get('immutable_hash', '')
        raw = json.dumps({k: v for k, v in entry.items() if k != 'immutable_hash'},
                         sort_keys=True, default=str)
        computed = hashlib.sha256(raw.encode()).hexdigest()

        if stored_hash != computed:
            return False, 'Hash mismatch: audit entry has been tampered with'

        if self._cipher and entry.get('encrypted_payload'):
            try:
                decrypted = self._cipher.decrypt(entry['encrypted_payload'].encode())
                original = json.loads(decrypted.decode())
                if original.get('audit_id') != entry.get('audit_id'):
                    return False, 'Encryption integrity check failed'
            except Exception as e:
                return False, f'Decryption verification failed: {e}'

        return True, None

    def export_audit_log(self, format: str = 'json', output_path: str = None,
                         user_id: str = None, event_type: str = None,
                         start_time: int = None, end_time: int = None) -> Any:
        data = self.get_audit_trail(
            user_id=user_id,
            event_type=event_type,
            start_time=start_time,
            end_time=end_time,
        )

        if format == 'json':
            output = json.dumps(data, indent=2, default=str)
            if output_path:
                with open(output_path, 'w', encoding='utf-8') as f:
                    f.write(output)
                logger.info(f'Audit log exported to {output_path} ({len(data)} entries)')
            return output

        elif format == 'csv':
            import io
            import csv
            output = io.StringIO()
            if data:
                writer = csv.DictWriter(output, fieldnames=data[0].keys(), extrasaction='ignore')
                writer.writeheader()
                writer.writerows(data)
            csv_output = output.getvalue()
            if output_path:
                with open(output_path, 'w', encoding='utf-8', newline='') as f:
                    f.write(csv_output)
                logger.info(f'Audit log exported as CSV to {output_path} ({len(data)} entries)')
            return csv_output

        elif format == 'jsonl':
            lines = '\n'.join(json.dumps(e, default=str) for e in data)
            if output_path:
                with open(output_path, 'w', encoding='utf-8') as f:
                    f.write(lines)
                logger.info(f'Audit log exported as JSONL to {output_path} ({len(data)} entries)')
            return lines

        return data

    def get_audit_statistics(self) -> Dict[str, Any]:
        with self._lock:
            total = len(self._audit_trail)

        by_type = Counter(e.get('event_type', 'unknown') for e in self._audit_trail)
        by_user = Counter(e.get('user_id', 'unknown') for e in self._audit_trail if e.get('user_id'))

        timestamps = [e.get('timestamp', 0) for e in self._audit_trail if e.get('timestamp', 0)]
        earliest = min(timestamps) if timestamps else None
        latest = max(timestamps) if timestamps else None

        avg_risk = 0.0
        if self._audit_trail:
            avg_risk = sum(e.get('risk_score', 0) for e in self._audit_trail) / len(self._audit_trail)

        return {
            'total_entries': total,
            'unique_users': len(by_user),
            'unique_event_types': len(by_type),
            'by_event_type': dict(by_type.most_common(20)),
            'by_user_top': dict(by_user.most_common(20)),
            'earliest_timestamp': earliest,
            'latest_timestamp': latest,
            'time_span_hours': round((latest - earliest) / 3600, 1) if earliest and latest else 0,
            'average_risk_score': round(avg_risk, 2),
            'integrity_verified': all(
                self.verify_audit_entry(e)[0] for e in self._audit_trail
            ) if self._audit_trail else True,
        }

    def _get_hostname(self) -> str:
        import socket
        try:
            return socket.gethostname()
        except Exception:
            return 'unknown'


# Module-level singleton instances
security_monitor = SecurityMonitor()
threat_scorer = ThreatScorer()
forensic_logger = ForensicAuditLogger()
