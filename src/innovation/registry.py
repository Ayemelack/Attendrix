"""Central service registry for Attendrix Innovation expansion modules.

Manages module lifecycle, event subscriptions, and cross-module communication.
All innovation modules register here and consume events from the existing system.
"""

import logging
from typing import Dict, Any, Callable, List, Optional
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class InnovationEvent(str, Enum):
    ATTENDANCE_MARKED = "attendance.marked"
    SESSION_CREATED = "session.created"
    SESSION_ENDED = "session.ended"
    USER_FLAGGED = "user.flagged"
    SYNC_COMPLETED = "sync.completed"
    ANOMALY_DETECTED = "anomaly.detected"
    CLASSROOM_UPDATED = "classroom.updated"
    RISK_THRESHOLD_CROSSED = "risk.threshold_crossed"
    INTERVENTION_TRIGGERED = "intervention.triggered"
    EMERGENCY_ACTIVATED = "emergency.activated"
    EMERGENCY_RESOLVED = "emergency.resolved"


class InnovationRegistry:
    """Central registry that coordinates all innovation modules."""

    def __init__(self):
        self._modules: Dict[str, Any] = {}
        self._subscriptions: Dict[str, List[Callable]] = {}
        self._event_log: List[Dict[str, Any]] = []
        self._initialized = False

    def register(self, name: str, module_instance: Any) -> None:
        self._modules[name] = module_instance
        logger.info(f"Innovation module registered: {name}")

    def get(self, name: str) -> Optional[Any]:
        return self._modules.get(name)

    def subscribe(self, event: InnovationEvent, handler: Callable) -> None:
        event_key = event.value if isinstance(event, InnovationEvent) else event
        if event_key not in self._subscriptions:
            self._subscriptions[event_key] = []
        self._subscriptions[event_key].append(handler)
        logger.info(f"Subscribed to {event_key}: {handler.__module__}.{handler.__name__}")

    def emit(self, event: InnovationEvent, data: Dict[str, Any]) -> None:
        event_key = event.value if isinstance(event, InnovationEvent) else event
        self._event_log.append({
            "event": event_key,
            "data": data,
            "timestamp": datetime.utcnow().isoformat()
        })
        if len(self._event_log) > 10000:
            self._event_log = self._event_log[-5000:]
        handlers = self._subscriptions.get(event_key, [])
        for handler in handlers:
            try:
                handler(data)
            except Exception as e:
                logger.error(f"Handler {handler.__name__} failed for {event_key}: {e}")

    def initialize_all(self, firebase_service=None, repositories: Dict[str, Any] = None) -> None:
        if self._initialized:
            return
        for name, module in self._modules.items():
            if hasattr(module, 'initialize'):
                try:
                    module.initialize(firebase_service=firebase_service, repositories=repositories)
                    logger.info(f"Initialized innovation module: {name}")
                except Exception as e:
                    logger.error(f"Failed to initialize {name}: {e}")
        self._initialized = True

    def get_status(self) -> Dict[str, Any]:
        return {
            "initialized": self._initialized,
            "modules": list(self._modules.keys()),
            "event_subscriptions": {
                k: len(v) for k, v in self._subscriptions.items()
            },
            "event_log_size": len(self._event_log)
        }

    def cleanup(self) -> None:
        for name, module in self._modules.items():
            if hasattr(module, 'cleanup'):
                try:
                    module.cleanup()
                except Exception as e:
                    logger.error(f"Cleanup failed for {name}: {e}")
        self._modules.clear()
        self._subscriptions.clear()
        self._event_log.clear()
        self._initialized = False


# Singleton instance
registry = InnovationRegistry()
