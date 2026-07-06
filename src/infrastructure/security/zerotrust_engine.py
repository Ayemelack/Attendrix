"""
PHASE 3 — ZERO-TRUST ENGINE (CENTRAL COORDINATOR)

Orchestrates all Phase 3 security modules:
- WebAuthn/FIDO2 passwordless authentication (3A)
- Device-bound session security (3B)
- ABAC policy engine (3C)
- Anomaly detection engine (3D)
- MITRE ATT&CK incident response (3E)
- Forensic logging (3F)
- Admin lockdown (3G)

Provides unified initialization, graceful degradation, health checks,
and integration hooks for the Flask application factory.
"""

import os
import time
import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, asdict
from flask import jsonify

logger = logging.getLogger(__name__)


@dataclass
class ModuleHealth:
    name: str
    phase: str
    available: bool
    status: str
    error: Optional[str] = None
    uptime: float = 0.0


class ZeroTrustEngine:
    """Central coordinator for all Phase 3 zero-trust modules."""

    def __init__(self):
        self._initialized = False
        self._start_time = time.time()

        self.webauthn = None
        self.device_session = None
        self.abac = None
        self.anomaly = None
        self.mitre = None
        self.forensic = None
        self.admin_lockdown = None

        self._init_order = []
        self._module_health: Dict[str, ModuleHealth] = {}

    def initialize(self, app=None):
        """Initialize all Phase 3 modules in dependency order."""
        if self._initialized:
            logger.warning("ZeroTrustEngine already initialized")
            return

        logger.info("Initializing Zero-Trust Engine (Phase 3)...")

        # Phase 3A — WebAuthn/FIDO2
        try:
            from src.infrastructure.security.webauthn_service import webauthn_service as ws
            self.webauthn = ws
            pass
            if self.webauthn.is_available():
                self._register_health('webauthn', '3A', True, 'operational')
                self._init_order.append('webauthn')
                logger.info("  [3A] WebAuthn/FIDO2 initialized")
            else:
                self._register_health('webauthn', '3A', False,
                                     'degraded — cryptography or cbor2 missing')
                logger.warning("  [3A] WebAuthn/FIDO2 unavailable (missing dependencies)")
        except Exception as e:
            self._register_health('webauthn', '3A', False, 'failed', str(e))
            logger.error(f"  [3A] WebAuthn/FIDO2 failed: {e}")

        # Phase 3B — Device-bound sessions
        try:
            from src.infrastructure.security.device_session import device_session_manager as dsm
            self.device_session = dsm
            pass
            self._register_health('device_session', '3B', True, 'operational')
            self._init_order.append('device_session')
            logger.info("  [3B] Device-bound session security initialized")
        except Exception as e:
            self._register_health('device_session', '3B', False, 'failed', str(e))
            logger.error(f"  [3B] Device-bound session security failed: {e}")

        # Phase 3C — ABAC engine
        try:
            from src.infrastructure.security.abac_engine import abac_engine as ae
            self.abac = ae
            self._register_health('abac', '3C', True, 'operational')
            self._init_order.append('abac')
            logger.info("  [3C] ABAC policy engine initialized")
        except Exception as e:
            self._register_health('abac', '3C', False, 'failed', str(e))
            logger.error(f"  [3C] ABAC policy engine failed: {e}")

        # Phase 3D — Anomaly detection
        try:
            from src.infrastructure.security.anomaly_detection import anomaly_detector as ad
            self.anomaly = ad
            pass
            self._register_health('anomaly', '3D', True, 'operational')
            self._init_order.append('anomaly')
            logger.info("  [3D] Anomaly detection initialized")
        except Exception as e:
            self._register_health('anomaly', '3D', False, 'failed', str(e))
            logger.error(f"  [3D] Anomaly detection failed: {e}")

        # Phase 3E — MITRE ATT&CK + Incident Response
        try:
            from src.infrastructure.security.mitre_attack import mitre_framework as mf
            self.mitre = mf
            pass
            self.mitre.anomaly_detector = self.anomaly
            self.mitre.device_session = self.device_session
            self._register_health('mitre', '3E', True, 'operational')
            self._init_order.append('mitre')
            logger.info("  [3E] MITRE ATT&CK framework initialized")
        except Exception as e:
            self._register_health('mitre', '3E', False, 'failed', str(e))
            logger.error(f"  [3E] MITRE ATT&CK framework failed: {e}")

        # Phase 3F — Forensic logging
        try:
            from src.infrastructure.security.forensic_logging import forensic_logger as fl
            self.forensic = fl
            pass
            self._register_health('forensic', '3F', True, 'operational')
            self._init_order.append('forensic')
            logger.info("  [3F] Forensic logging initialized")
        except Exception as e:
            self._register_health('forensic', '3F', False, 'failed', str(e))
            logger.error(f"  [3F] Forensic logging failed: {e}")

        # Phase 3G — Admin lockdown
        try:
            from src.infrastructure.security.admin_lockdown import admin_lockdown as al
            self.admin_lockdown = al
            pass
            self._register_health('admin_lockdown', '3G', True, 'operational')
            self._init_order.append('admin_lockdown')
            logger.info("  [3G] Admin lockdown initialized")
        except Exception as e:
            self._register_health('admin_lockdown', '3G', False, 'failed', str(e))
            logger.error(f"  [3G] Admin lockdown failed: {e}")

        # Register routes if app is provided
        if app:
            self._register_routes(app)

        self._initialized = True
        operational = sum(1 for h in self._module_health.values() if h.available)
        total = len(self._module_health)
        logger.info(f"Zero-Trust Engine initialized: {operational}/{total} modules operational")

    def _register_routes(self, app):
        """Register all Phase 3 route blueprints."""
        try:
            from src.presentation.routes.webauthn_routes import register_webauthn_routes
            register_webauthn_routes(app)
            logger.info("  WebAuthn routes registered")
        except Exception as e:
            logger.error(f"  WebAuthn route registration failed: {e}")

        @app.route('/api/v1/security/health', methods=['GET'])
        def security_health():
            return jsonify({
                'engine': 'zero-trust',
                'initialized': self._initialized,
                'uptime_seconds': int(time.time() - self._start_time),
                'modules': {k: asdict(v) for k, v in self._module_health.items()},
                'lockdown': self.admin_lockdown.get_lockdown_status() if self.admin_lockdown else None,
            })

    def _register_health(self, name: str, phase: str, available: bool,
                         status: str, error: str = None):
        self._module_health[name] = ModuleHealth(
            name=name,
            phase=phase,
            available=available,
            status=status,
            error=error,
            uptime=time.time() - self._start_time,
        )

    def get_health(self) -> Dict[str, Any]:
        return {
            'initialized': self._initialized,
            'uptime_seconds': int(time.time() - self._start_time),
            'modules': {k: asdict(v) for k, v in self._module_health.items()},
            'operational_count': sum(1 for h in self._module_health.values() if h.available),
            'total_count': len(self._module_health),
        }

    def is_available(self, module_name: str) -> bool:
        health = self._module_health.get(module_name)
        return health is not None and health.available

    def get_available_modules(self) -> List[str]:
        return [k for k, h in self._module_health.items() if h.available]

    def log_security_event(self, category: str, user_id: str, action: str,
                           resource: str, details: Dict[str, Any],
                           ip_address: str = '0.0.0.0', user_agent: str = ''):
        if self.forensic:
            from src.infrastructure.security.forensic_logging import LogCategory, LogLevel
            cat_map = {
                'auth': LogCategory.AUTH,
                'access': LogCategory.ACCESS,
                'admin': LogCategory.ADMIN,
                'security': LogCategory.SECURITY,
                'data': LogCategory.DATA,
            }
            self.forensic.log(
                level=LogLevel.INFO,
                category=cat_map.get(category, LogCategory.SYSTEM),
                user_id=user_id,
                session_id=details.get('session_id', ''),
                action=action,
                resource=resource,
                details=details,
                ip_address=ip_address,
                user_agent=user_agent,
            )

    def detect_and_respond(self, technique_id: str, user_id: str,
                           resource: str, ip_address: str,
                           evidence: Dict[str, Any]):
        if self.mitre:
            self.mitre.detect_incident(
                technique_id=technique_id,
                affected_user_id=user_id,
                affected_resource=resource,
                source_ip=ip_address,
                evidence=evidence,
            )

    def shutdown(self):
        """Graceful shutdown of all modules."""
        logger.info("Shutting down Zero-Trust Engine...")
        if self.admin_lockdown:
            from src.infrastructure.security.admin_lockdown import LockdownLevel
            self.admin_lockdown.set_lockdown_level(
                LockdownLevel.NORMAL,
                'system',
                'Engine shutdown',
            )
        if self.forensic:
            from src.infrastructure.security.forensic_logging import LogLevel, LogCategory
            self.forensic.log(
                LogLevel.INFO,
                LogCategory.SYSTEM,
                'system',
                '',
                'shutdown',
                'engine',
                {'reason': 'graceful_shutdown'},
            )
        self._initialized = False
        logger.info("Zero-Trust Engine shut down")


zerotrust = ZeroTrustEngine()
