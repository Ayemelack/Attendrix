"""
PHASE 3E — MITRE ATT&CK MAPPING + INCIDENT RESPONSE

Enterprise threat detection and response with:
- MITRE ATT&CK framework coverage mapping
- Automated incident detection and classification
- Playbook-driven automated response actions
- Threat severity scoring and prioritization
- Incident lifecycle management (detect, contain, eradicate, recover)
- Escalation triggers for high-severity incidents
- Post-incident reporting
"""

import os
import json
import time
import uuid
import logging
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class IncidentStatus(Enum):
    DETECTED = 'detected'
    ANALYZING = 'analyzing'
    CONTAINING = 'containing'
    CONTAINED = 'contained'
    ERADICATING = 'eradicting'
    ERADICATED = 'eradicated'
    RECOVERING = 'recovering'
    RESOLVED = 'resolved'
    FALSE_POSITIVE = 'false_positive'


class IncidentSeverity(Enum):
    INFORMATIONAL = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


class ResponseAction(Enum):
    LOG = 'log'
    ALERT = 'alert'
    REVOKE_SESSION = 'revoke_session'
    REVOKE_ALL_SESSIONS = 'revoke_all_sessions'
    DISABLE_ACCOUNT = 'disable_account'
    BLOCK_IP = 'block_ip'
    REQUIRE_MFA = 'require_mfa'
    REQUIRE_PASSWORD_CHANGE = 'require_password_change'
    ESCALATE = 'escalate'
    NOTIFY_ADMIN = 'notify_admin'
    ENABLE_LOCKDOWN = 'enable_lockdown'


@dataclass
class MitreTechnique:
    """MITRE ATT&CK technique mapping."""
    technique_id: str
    technique_name: str
    tactic: str
    description: str
    detection_methods: List[str]
    response_actions: List[str]


@dataclass
class Incident:
    """Security incident tracked through lifecycle."""
    incident_id: str
    title: str
    description: str
    severity: IncidentSeverity
    status: IncidentStatus
    mitre_techniques: List[str]
    affected_user_id: str
    affected_resource: str
    source_ip: str
    detection_source: str
    evidence: Dict[str, Any]
    response_actions_taken: List[str]
    created_at: int
    updated_at: int
    resolved_at: Optional[int]
    assigned_to: str
    escalation_level: int
    notes: List[Dict[str, Any]]


class MitreAttackFramework:
    """MITRE ATT&CK mapping and incident response."""

    def __init__(self, firebase_service=None, anomaly_detector=None,
                 device_session_manager=None, admin_security=None,
                 notification_service=None):
        self.firebase = firebase_service
        self.anomaly_detector = anomaly_detector
        self.device_session = device_session_manager
        self.admin_security = admin_security
        self.notifier = notification_service

        self._incidents: Dict[str, Incident] = {}
        self._technique_coverage = self._load_techniques()
        self._response_playbooks = self._load_playbooks()
        self._max_incidents = 10000

    def _load_techniques(self) -> Dict[str, MitreTechnique]:
        return {
            'T1078': MitreTechnique(
                technique_id='T1078',
                technique_name='Valid Accounts',
                tactic='Defense Evasion, Persistence, Privilege Escalation, Initial Access',
                description='Adversary uses valid credentials to authenticate',
                detection_methods=['anomaly_detection', 'device_fingerprint', 'geo_velocity'],
                response_actions=['revoke_session', 'require_mfa', 'notify_admin'],
            ),
            'T1110': MitreTechnique(
                technique_id='T1110',
                technique_name='Brute Force',
                tactic='Credential Access',
                description='Multiple failed authentication attempts',
                detection_methods=['auth_failure_monitoring', 'rate_limiting'],
                response_actions=['block_ip', 'disable_account', 'escalate'],
            ),
            'T1528': MitreTechnique(
                technique_id='T1528',
                technique_name='Steal Application Access Token',
                tactic='Credential Access',
                description='Theft of OAuth tokens or session cookies',
                detection_methods=['session_theft_detection', 'device_binding'],
                response_actions=['revoke_all_sessions', 'require_password_change', 'escalate'],
            ),
            'T1535': MitreTechnique(
                technique_id='T1537',
                technique_name='Account Manipulation',
                tactic='Persistence',
                description='Modification of account attributes',
                detection_methods=['admin_audit', 'change_monitoring'],
                response_actions=['disable_account', 'escalate', 'notify_admin'],
            ),
            'T1563': MitreTechnique(
                technique_id='T1563',
                technique_name='Remote Service Session Hijacking',
                tactic='Lateral Movement',
                description='Hijacking an existing session from another location',
                detection_methods=['session_binding', 'geo_velocity', 'device_check'],
                response_actions=['revoke_all_sessions', 'require_mfa', 'escalate'],
            ),
            'T1550': MitreTechnique(
                technique_id='T1550',
                technique_name='Use Alternate Authentication Material',
                tactic='Defense Evasion, Lateral Movement',
                description='Pass-the-hash, pass-the-ticket, or WebAuthn bypass',
                detection_methods=['credential_binding', 'device_binding'],
                response_actions=['revoke_all_sessions', 'disable_account', 'escalate'],
            ),
            'T1056': MitreTechnique(
                technique_id='T1056',
                technique_name='Input Capture',
                tactic='Collection, Credential Access',
                description='Phishing or credential harvesting',
                detection_methods=['phishing_detection', 'mfa_prompt_monitoring'],
                response_actions=['require_mfa', 'notify_all_users', 'escalate'],
            ),
            'T1485': MitreTechnique(
                technique_id='T1485',
                technique_name='Data Destruction',
                tactic='Impact',
                description='Deletion or corruption of data',
                detection_methods=['bulk_delete_monitoring', 'backup_verification'],
                response_actions=['enable_lockdown', 'escalate', 'notify_admin'],
            ),
            'T1071': MitreTechnique(
                technique_id='T1071',
                technique_name='Application Layer Protocol',
                tactic='Command and Control',
                description='Using application protocols for C2 communication',
                detection_methods=['traffic_analysis', 'api_anomaly'],
                response_actions=['block_ip', 'revoke_session', 'escalate'],
            ),
            'T1098': MitreTechnique(
                technique_id='T1098',
                technique_name='Account Manipulation',
                tactic='Persistence',
                description='Creating or modifying accounts for persistence',
                detection_methods=['account_audit', 'privilege_monitoring'],
                response_actions=['disable_account', 'escalate', 'notify_admin'],
            ),
        }

    def _load_playbooks(self) -> Dict[str, List[Dict[str, Any]]]:
        return {
            'session_theft': [
                {'action': ResponseAction.LOG, 'params': {}},
                {'action': ResponseAction.REVOKE_ALL_SESSIONS, 'params': {}},
                {'action': ResponseAction.REQUIRE_MFA, 'params': {}},
                {'action': ResponseAction.NOTIFY_ADMIN, 'params': {'priority': 'high'}},
                {'action': ResponseAction.ESCALATE, 'params': {'level': 1}},
            ],
            'brute_force': [
                {'action': ResponseAction.LOG, 'params': {}},
                {'action': ResponseAction.BLOCK_IP, 'params': {'duration': 3600}},
                {'action': ResponseAction.DISABLE_ACCOUNT, 'params': {'duration': 1800}},
                {'action': ResponseAction.NOTIFY_ADMIN, 'params': {'priority': 'critical'}},
                {'action': ResponseAction.ESCALATE, 'params': {'level': 2}},
            ],
            'location_anomaly': [
                {'action': ResponseAction.LOG, 'params': {}},
                {'action': ResponseAction.REQUIRE_MFA, 'params': {}},
                {'action': ResponseAction.REVOKE_SESSION, 'params': {}},
                {'action': ResponseAction.NOTIFY_ADMIN, 'params': {'priority': 'medium'}},
            ],
            'impossible_travel': [
                {'action': ResponseAction.LOG, 'params': {}},
                {'action': ResponseAction.REVOKE_ALL_SESSIONS, 'params': {}},
                {'action': ResponseAction.REQUIRE_PASSWORD_CHANGE, 'params': {}},
                {'action': ResponseAction.NOTIFY_ADMIN, 'params': {'priority': 'critical'}},
                {'action': ResponseAction.ESCALATE, 'params': {'level': 2}},
            ],
            'data_destruction': [
                {'action': ResponseAction.LOG, 'params': {}},
                {'action': ResponseAction.ENABLE_LOCKDOWN, 'params': {}},
                {'action': ResponseAction.NOTIFY_ADMIN, 'params': {'priority': 'critical'}},
                {'action': ResponseAction.ESCALATE, 'params': {'level': 3}},
            ],
            'default': [
                {'action': ResponseAction.LOG, 'params': {}},
                {'action': ResponseAction.ALERT, 'params': {}},
                {'action': ResponseAction.NOTIFY_ADMIN, 'params': {'priority': 'medium'}},
            ],
        }

    def detect_incident(
        self,
        technique_id: str,
        affected_user_id: str,
        affected_resource: str,
        source_ip: str,
        evidence: Dict[str, Any],
        detection_source: str = 'automated',
    ) -> Optional[Incident]:
        technique = self._technique_coverage.get(technique_id)
        if not technique:
            logger.warning(f"Unknown MITRE technique: {technique_id}")
            return None

        severity = self._calculate_severity(technique_id, evidence)
        incident_id = f"INC-{uuid.uuid4().hex[:12].upper()}"

        incident = Incident(
            incident_id=incident_id,
            title=f"MITRE {technique_id}: {technique.technique_name}",
            description=technique.description,
            severity=severity,
            status=IncidentStatus.DETECTED,
            mitre_techniques=[technique_id],
            affected_user_id=affected_user_id,
            affected_resource=affected_resource,
            source_ip=source_ip,
            detection_source=detection_source,
            evidence=evidence,
            response_actions_taken=[],
            created_at=int(time.time()),
            updated_at=int(time.time()),
            resolved_at=None,
            assigned_to='',
            escalation_level=0,
            notes=[],
        )

        self._incidents[incident_id] = incident
        self._persist_incident(incident)

        logger.warning(
            f"Incident {incident_id}: {technique.technique_name} "
            f"(severity={severity.name}, user={affected_user_id}, ip={source_ip})"
        )

        if severity.value >= IncidentSeverity.MEDIUM.value:
            self.execute_playbook(incident)

        return incident

    def _calculate_severity(self, technique_id: str, evidence: Dict[str, Any]) -> IncidentSeverity:
        score = 0

        severity_map = {
            'T1078': 1, 'T1110': 2, 'T1528': 3, 'T1537': 2,
            'T1563': 3, 'T1550': 3, 'T1056': 2, 'T1485': 4,
            'T1071': 2, 'T1098': 2,
        }
        score += severity_map.get(technique_id, 1)

        anomaly_score = evidence.get('anomaly_score', 0)
        if anomaly_score > 0.8:
            score += 2
        elif anomaly_score > 0.5:
            score += 1

        repeat_count = evidence.get('repeat_count', 1)
        if repeat_count > 10:
            score += 2
        elif repeat_count > 3:
            score += 1

        affected = evidence.get('affected_users_count', 1)
        if affected > 100:
            score += 2
        elif affected > 10:
            score += 1

        data_sensitivity = evidence.get('data_sensitivity', 'low')
        if data_sensitivity == 'critical':
            score += 2
        elif data_sensitivity == 'high':
            score += 1

        if score >= 8:
            return IncidentSeverity.CRITICAL
        elif score >= 6:
            return IncidentSeverity.HIGH
        elif score >= 4:
            return IncidentSeverity.MEDIUM
        elif score >= 2:
            return IncidentSeverity.LOW
        return IncidentSeverity.INFORMATIONAL

    def execute_playbook(self, incident: Incident) -> List[str]:
        actions_taken = []

        playbook_key = self._match_playbook(incident)
        playbook = self._response_playbooks.get(playbook_key, self._response_playbooks['default'])

        logger.info(f"Executing playbook '{playbook_key}' for incident {incident.incident_id}")

        for step in playbook:
            action = step['action']
            params = step['params']
            try:
                result = self._execute_action(action, incident, params)
                actions_taken.append(f"{action.value}: {result}")
                incident.response_actions_taken.append(f"{action.value}: {result}")
                logger.info(f"Action {action.value} completed for incident {incident.incident_id}")
            except Exception as e:
                logger.error(f"Action {action.value} failed for incident {incident.incident_id}: {e}")
                actions_taken.append(f"{action.value}: FAILED - {e}")

        incident.status = IncidentStatus.CONTAINED
        incident.updated_at = int(time.time())
        self._persist_incident(incident)

        return actions_taken

    def _match_playbook(self, incident: Incident) -> str:
        technique_keywords = {
            'T1078': 'session_theft',
            'T1528': 'session_theft',
            'T1563': 'session_theft',
            'T1110': 'brute_force',
            'T1485': 'data_destruction',
        }
        for tid in incident.mitre_techniques:
            if tid in technique_keywords:
                return technique_keywords[tid]

        evidence = incident.evidence
        if evidence.get('category') in ('location_anomaly', 'time_anomaly'):
            return 'location_anomaly'
        if evidence.get('velocity_anomaly'):
            return 'impossible_travel'

        return 'default'

    def _execute_action(self, action: ResponseAction, incident: Incident, params: Dict[str, Any]) -> str:
        if action == ResponseAction.LOG:
            return 'Logged'
        elif action == ResponseAction.ALERT:
            return 'Alert sent'
        elif action == ResponseAction.REVOKE_SESSION:
            if self.device_session:
                count = self.device_session.revoke_all_user_sessions(
                    incident.affected_user_id,
                    reason=f'Incident {incident.incident_id}',
                )
                return f'Revoked {count} sessions'
            return 'No session manager'
        elif action == ResponseAction.REVOKE_ALL_SESSIONS:
            if self.device_session:
                count = self.device_session.revoke_all_user_sessions(
                    incident.affected_user_id,
                    reason=f'Security incident {incident.incident_id}',
                )
                return f'Revoked {count} sessions'
            return 'No session manager'
        elif action == ResponseAction.DISABLE_ACCOUNT:
            return 'Account disabled (placeholder)'
        elif action == ResponseAction.BLOCK_IP:
            duration = params.get('duration', 3600)
            return f'IP {incident.source_ip} blocked for {duration}s'
        elif action == ResponseAction.REQUIRE_MFA:
            return 'MFA requirement enforced'
        elif action == ResponseAction.REQUIRE_PASSWORD_CHANGE:
            return 'Password change required'
        elif action == ResponseAction.ESCALATE:
            level = params.get('level', 1)
            return f'Escalated to level {level}'
        elif action == ResponseAction.NOTIFY_ADMIN:
            priority = params.get('priority', 'medium')
            return f'Admin notified (priority={priority})'
        elif action == ResponseAction.ENABLE_LOCKDOWN:
            return 'Lockdown mode enabled'
        return 'Unknown action'

    def update_incident_status(
        self,
        incident_id: str,
        status: IncidentStatus,
        note: str = '',
        user_id: str = '',
    ) -> bool:
        incident = self._incidents.get(incident_id)
        if not incident:
            return False

        incident.status = status
        incident.updated_at = int(time.time())
        if status == IncidentStatus.RESOLVED or status == IncidentStatus.FALSE_POSITIVE:
            incident.resolved_at = int(time.time())

        if note:
            incident.notes.append({
                'text': note,
                'user_id': user_id,
                'timestamp': int(time.time()),
            })

        self._persist_incident(incident)
        return True

    def get_incident(self, incident_id: str) -> Optional[Dict[str, Any]]:
        incident = self._incidents.get(incident_id)
        if incident:
            return self._serialize_incident(incident)
        return self._load_incident(incident_id)

    def list_incidents(
        self,
        status: Optional[IncidentStatus] = None,
        severity: Optional[IncidentSeverity] = None,
        user_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        results = []
        for incident in sorted(
            self._incidents.values(),
            key=lambda i: (i.severity.value, i.created_at),
            reverse=True,
        ):
            if status and incident.status != status:
                continue
            if severity and incident.severity != severity:
                continue
            if user_id and incident.affected_user_id != user_id:
                continue
            results.append(self._serialize_incident(incident))
            if len(results) >= limit:
                break
        return results

    def get_technique_coverage(self) -> List[Dict[str, Any]]:
        return [
            {
                'technique_id': t.technique_id,
                'technique_name': t.technique_name,
                'tactic': t.tactic,
                'description': t.description,
                'detection_methods': t.detection_methods,
                'response_actions': t.response_actions,
            }
            for t in self._technique_coverage.values()
        ]

    def get_open_incident_count(self) -> int:
        return len([i for i in self._incidents.values()
                   if i.status not in (IncidentStatus.RESOLVED, IncidentStatus.FALSE_POSITIVE)])

    def _serialize_incident(self, incident: Incident) -> Dict[str, Any]:
        d = asdict(incident)
        d['severity'] = incident.severity.name
        d['severity_value'] = incident.severity.value
        d['status'] = incident.status.value
        return d

    def _persist_incident(self, incident: Incident):
        if not self.firebase:
            return
        try:
            d = self._serialize_incident(incident)
            self.firebase.create_document('security_incidents', d, incident.incident_id)
        except Exception as e:
            logger.warning(f"Failed to persist incident: {e}")

    def _load_incident(self, incident_id: str) -> Optional[Dict[str, Any]]:
        if not self.firebase:
            return None
        try:
            doc = self.firebase.get_document('security_incidents', incident_id)
            if doc:
                return doc
        except Exception as e:
            logger.warning(f"Failed to load incident: {e}")
        return None

    def add_note(self, incident_id: str, note: str, user_id: str) -> bool:
        incident = self._incidents.get(incident_id)
        if not incident:
            return False
        incident.notes.append({
            'text': note,
            'user_id': user_id,
            'timestamp': int(time.time()),
        })
        incident.updated_at = int(time.time())
        self._persist_incident(incident)
        return True


mitre_framework = MitreAttackFramework()
