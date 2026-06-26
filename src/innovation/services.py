"""Innovation services integration — ties all modules into the existing system.

Provides a factory function that initializes all innovation modules and
connects them to the existing Firebase/repository infrastructure. This is
the single entry point for wiring new capabilities into Attendrix.
"""

import logging
from typing import Dict, Any, Optional

from .registry import registry
from .risk_engine import AcademicRiskEngine
from .participation import ParticipationIntelligence
from .classroom import SmartClassroomIntelligence
from .invisible_validation import InvisibleValidation
from .digital_twin import InstitutionalDigitalTwin
from .trust_chain import TrustChain
from .intervention import SmartIntervention
from .admin_automation import AdminAutomation
from .security_emergency import SecurityEmergency
from .infrastructure_net import InfrastructureNet
from .reputation import ReputationSystem
from .ecosystem import EcosystemIntegration

logger = logging.getLogger(__name__)


class InnovationEngine:
    """Master coordinator for all innovation modules.

    Usage:
        engine = InnovationEngine()
        engine.initialize(firebase_service=firebase, repositories=repos)
        engine.risk_engine.predict_dropout_risk(...)
    """

    def __init__(self):
        self.risk_engine: Optional[AcademicRiskEngine] = None
        self.participation: Optional[ParticipationIntelligence] = None
        self.classroom: Optional[SmartClassroomIntelligence] = None
        self.validation: Optional[InvisibleValidation] = None
        self.digital_twin: Optional[InstitutionalDigitalTwin] = None
        self.trust_chain: Optional[TrustChain] = None
        self.intervention: Optional[SmartIntervention] = None
        self.admin_automation: Optional[AdminAutomation] = None
        self.security: Optional[SecurityEmergency] = None
        self.infrastructure: Optional[InfrastructureNet] = None
        self.reputation: Optional[ReputationSystem] = None
        self.ecosystem: Optional[EcosystemIntegration] = None
        self._initialized = False

    def initialize(self, firebase_service=None,
                   repositories: Dict[str, Any] = None) -> None:
        """Initialize all innovation modules."""
        if self._initialized:
            return

        self.risk_engine = AcademicRiskEngine()
        self.participation = ParticipationIntelligence()
        self.classroom = SmartClassroomIntelligence()
        self.validation = InvisibleValidation()
        self.digital_twin = InstitutionalDigitalTwin()
        self.trust_chain = TrustChain()
        self.intervention = SmartIntervention()
        self.admin_automation = AdminAutomation()
        self.security = SecurityEmergency()
        self.infrastructure = InfrastructureNet()
        self.reputation = ReputationSystem()
        self.ecosystem = EcosystemIntegration()

        modules = [
            ("risk_engine", self.risk_engine),
            ("participation", self.participation),
            ("classroom", self.classroom),
            ("validation", self.validation),
            ("digital_twin", self.digital_twin),
            ("trust_chain", self.trust_chain),
            ("intervention", self.intervention),
            ("admin_automation", self.admin_automation),
            ("security", self.security),
            ("infrastructure", self.infrastructure),
            ("reputation", self.reputation),
            ("ecosystem", self.ecosystem),
        ]

        for name, module in modules:
            registry.register(name, module)

        registry.initialize_all(
            firebase_service=firebase_service,
            repositories=repositories
        )

        self._initialized = True
        logger.info("InnovationEngine fully initialized with 12 modules")

    def get_registry_status(self) -> Dict[str, Any]:
        """Get status of the innovation registry."""
        return registry.get_status()

    def cleanup(self) -> None:
        """Clean up all modules."""
        registry.cleanup()
        self._initialized = False
        logger.info("InnovationEngine cleaned up")


def create_innovation_engine(firebase_service=None,
                              repositories: Dict[str, Any] = None) -> InnovationEngine:
    """Factory function to create and initialize the innovation engine."""
    engine = InnovationEngine()
    engine.initialize(
        firebase_service=firebase_service,
        repositories=repositories
    )
    return engine
