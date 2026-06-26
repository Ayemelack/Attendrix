"""
PHASE 3C — ATTRIBUTE-BASED ACCESS CONTROL (ABAC)

Context-aware policy engine with:
- User attributes (role, department, clearance)
- Resource attributes (type, sensitivity, classification)
- Environmental attributes (time, location, network, risk score)
- Action attributes (operation, scope, method)
- Policy combination and conflict resolution
- Deny-by-default with explicit allow rules
- Cache-friendly policy evaluation
"""

import os
import re
import json
import time
import hashlib
import logging
from typing import Optional, Dict, Any, List, Tuple, Callable
from dataclasses import dataclass, field, asdict
from enum import Enum
from functools import wraps
from flask import session, request, jsonify

logger = logging.getLogger(__name__)


class Effect(Enum):
    DENY = 'deny'
    ALLOW = 'allow'


class ConditionOperator(Enum):
    EQUALS = 'equals'
    NOT_EQUALS = 'not_equals'
    IN = 'in'
    NOT_IN = 'not_in'
    CONTAINS = 'contains'
    GREATER_THAN = 'greater_than'
    LESS_THAN = 'less_than'
    MATCHES = 'matches'
    EXISTS = 'exists'
    NOT_EXISTS = 'not_exists'


@dataclass
class Condition:
    attribute: str
    operator: ConditionOperator
    value: Any

    def evaluate(self, context: Dict[str, Any]) -> bool:
        attr_value = self._resolve_attribute(self.attribute, context)

        if self.operator == ConditionOperator.EXISTS:
            return attr_value is not None
        if self.operator == ConditionOperator.NOT_EXISTS:
            return attr_value is None

        if attr_value is None:
            return False

        try:
            if self.operator == ConditionOperator.EQUALS:
                return attr_value == self.value
            elif self.operator == ConditionOperator.NOT_EQUALS:
                return attr_value != self.value
            elif self.operator == ConditionOperator.IN:
                return attr_value in self.value
            elif self.operator == ConditionOperator.NOT_IN:
                return attr_value not in self.value
            elif self.operator == ConditionOperator.CONTAINS:
                return self.value in attr_value if isinstance(attr_value, (list, str, dict)) else False
            elif self.operator == ConditionOperator.GREATER_THAN:
                return float(attr_value) > float(self.value)
            elif self.operator == ConditionOperator.LESS_THAN:
                return float(attr_value) < float(self.value)
            elif self.operator == ConditionOperator.MATCHES:
                return bool(re.match(str(self.value), str(attr_value)))
        except (TypeError, ValueError) as e:
            logger.warning(f"Condition evaluation error: {e}")
            return False

        return False

    def _resolve_attribute(self, attribute: str, context: Dict[str, Any]) -> Any:
        parts = attribute.split('.')
        current = context
        for part in parts:
            if isinstance(current, dict):
                current = current.get(part)
            else:
                return None
        return current


@dataclass
class PolicyRule:
    """Individual access control rule."""
    name: str
    description: str
    effect: Effect
    conditions: List[Condition]
    priority: int = 0
    enabled: bool = True
    version: int = 1


@dataclass
class Policy:
    """Named policy containing rules."""
    policy_id: str
    name: str
    description: str
    target_resource: str
    target_action: str
    rules: List[PolicyRule]
    enabled: bool = True
    version: int = 1


@dataclass
class AccessRequest:
    """Access request to evaluate against policies."""
    user_id: str
    role: str
    department: str
    clearance_level: int
    resource_type: str
    resource_id: str
    resource_sensitivity: str
    action: str
    method: str
    ip_address: str
    geolocation: Optional[Dict[str, Any]]
    time_of_day: int
    day_of_week: int
    device_trust_score: float
    session_risk_score: float
    user_auth_methods: List[str]


@dataclass
class AccessDecision:
    """Result of policy evaluation."""
    allowed: bool
    effect: Optional[Effect]
    policy_name: str
    rule_name: str
    reason: str
    evaluation_time_ms: float
    obligations: List[str] = field(default_factory=list)
    advice: List[str] = field(default_factory=list)


class ABACEngine:
    """Attribute-Based Access Control engine."""

    def __init__(self, policy_store=None):
        self.policy_store = policy_store
        self._policies: Dict[str, Policy] = {}
        self._cache: Dict[str, Tuple[AccessDecision, float]] = {}
        self._cache_ttl = int(os.environ.get('ABAC_CACHE_TTL', '300'))
        self._load_default_policies()

    def _load_default_policies(self):
        self.add_policy(Policy(
            policy_id='super_admin_full_access',
            name='Super Admin Full Access',
            description='Super admins have unrestricted access to all resources',
            target_resource='*',
            target_action='*',
            rules=[
                PolicyRule(
                    name='super_admin_allow',
                    description='Allow all actions for super_admin role',
                    effect=Effect.ALLOW,
                    conditions=[
                        Condition('user.role', ConditionOperator.EQUALS, 'super_admin'),
                    ],
                    priority=100,
                ),
            ],
        ))

        self.add_policy(Policy(
            policy_id='institutional_admin_resource',
            name='Institutional Admin Resource Access',
            description='Institutional admins can manage resources within their institution',
            target_resource='*',
            target_action='*',
            rules=[
                PolicyRule(
                    name='institutional_admin_allow',
                    description='Allow admin actions within same institution',
                    effect=Effect.ALLOW,
                    conditions=[
                        Condition('user.role', ConditionOperator.EQUALS, 'institutional_admin'),
                        Condition('user.department', ConditionOperator.EQUALS, 'resource.department'),
                    ],
                    priority=90,
                ),
            ],
        ))

        self.add_policy(Policy(
            policy_id='instructor_teaching_access',
            name='Instructor Teaching Access',
            description='Instructors can manage their own courses and view student data',
            target_resource='course',
            target_action='*',
            rules=[
                PolicyRule(
                    name='instructor_own_course',
                    description='Instructor can manage their assigned courses',
                    effect=Effect.ALLOW,
                    conditions=[
                        Condition('user.role', ConditionOperator.IN, ['instructor', 'institutional_admin', 'super_admin']),
                        Condition('resource.owner_id', ConditionOperator.EQUALS, 'user.user_id'),
                    ],
                    priority=80,
                ),
                PolicyRule(
                    name='instructor_view_students',
                    description='Instructor can view students in their courses',
                    effect=Effect.ALLOW,
                    conditions=[
                        Condition('user.role', ConditionOperator.EQUALS, 'instructor'),
                        Condition('resource.owner_id', ConditionOperator.EQUALS, 'user.user_id'),
                        Condition('action', ConditionOperator.IN, ['read', 'list']),
                    ],
                    priority=70,
                ),
            ],
        ))

        self.add_policy(Policy(
            policy_id='attendee_self_access',
            name='Attendee Self Access',
            description='Attendees can only access their own data and attend courses',
            target_resource='attendance',
            target_action='*',
            rules=[
                PolicyRule(
                    name='attendee_own_attendance',
                    description='Attendee can view their own attendance records',
                    effect=Effect.ALLOW,
                    conditions=[
                        Condition('user.role', ConditionOperator.EQUALS, 'attendee'),
                        Condition('resource.user_id', ConditionOperator.EQUALS, 'user.user_id'),
                    ],
                    priority=60,
                ),
            ],
        ))

        self.add_policy(Policy(
            policy_id='time_based_restrictions',
            name='Time-Based Access Restrictions',
            description='Restrict sensitive operations to business hours',
            target_resource='sensitive',
            target_action='write',
            rules=[
                PolicyRule(
                    name='business_hours_only',
                    description='Sensitive write operations restricted to business hours',
                    effect=Effect.DENY,
                    conditions=[
                        Condition('user.role', ConditionOperator.NOT_IN, ['super_admin']),
                        Condition('environment.time_of_day', ConditionOperator.LESS_THAN, 8),
                        Condition('resource.sensitivity', ConditionOperator.EQUALS, 'high'),
                    ],
                    priority=50,
                ),
                PolicyRule(
                    name='weekend_restriction',
                    description='Sensitive operations restricted on weekends',
                    effect=Effect.DENY,
                    conditions=[
                        Condition('user.role', ConditionOperator.NOT_IN, ['super_admin']),
                        Condition('environment.day_of_week', ConditionOperator.IN, [6, 7]),
                        Condition('resource.sensitivity', ConditionOperator.EQUALS, 'high'),
                    ],
                    priority=50,
                ),
            ],
        ))

        self.add_policy(Policy(
            policy_id='high_risk_device_restrictions',
            name='High Risk Device Restrictions',
            description='Restrict access from untrusted or high-risk devices',
            target_resource='sensitive',
            target_action='*',
            rules=[
                PolicyRule(
                    name='low_trust_device_deny',
                    description='Deny sensitive operations from low-trust devices',
                    effect=Effect.DENY,
                    conditions=[
                        Condition('device.trust_score', ConditionOperator.LESS_THAN, 0.3),
                        Condition('resource.sensitivity', ConditionOperator.EQUALS, 'high'),
                    ],
                    priority=95,
                ),
                PolicyRule(
                    name='high_risk_session_deny',
                    description='Deny access from high-risk sessions',
                    effect=Effect.DENY,
                    conditions=[
                        Condition('session.risk_score', ConditionOperator.GREATER_THAN, 0.7),
                        Condition('resource.sensitivity', ConditionOperator.EQUALS, 'high'),
                    ],
                    priority=95,
                ),
            ],
        ))

        self.add_policy(Policy(
            policy_id='default_deny',
            name='Default Deny',
            description='Deny-all catch-all policy',
            target_resource='*',
            target_action='*',
            rules=[
                PolicyRule(
                    name='default_deny_rule',
                    description='Deny all actions by default',
                    effect=Effect.DENY,
                    conditions=[],
                    priority=0,
                ),
            ],
        ))

    def add_policy(self, policy: Policy):
        self._policies[policy.policy_id] = policy

    def remove_policy(self, policy_id: str):
        self._policies.pop(policy_id, None)
        self._invalidate_cache()

    def get_policy(self, policy_id: str) -> Optional[Policy]:
        return self._policies.get(policy_id)

    def list_policies(self) -> List[Dict[str, Any]]:
        return [asdict(p) for p in self._policies.values()]

    def evaluate(self, request: AccessRequest) -> AccessDecision:
        start = time.time()

        cache_key = self._cache_key(request)
        cached = self._cache.get(cache_key)
        if cached:
            decision, ts = cached
            if time.time() - ts < self._cache_ttl:
                return decision

        context = self._build_context(request)

        matching_policies = self._find_matching_policies(
            request.resource_type,
            request.action,
        )

        rules_evaluated = []
        for policy in sorted(matching_policies, key=lambda p: -p.version):
            for rule in sorted(policy.rules, key=lambda r: -r.priority):
                if not rule.enabled:
                    continue
                result = self._evaluate_rule(rule, context)
                rules_evaluated.append((policy, rule, result))
                if result:
                    decision = AccessDecision(
                        allowed=rule.effect == Effect.ALLOW,
                        effect=rule.effect,
                        policy_name=policy.name,
                        rule_name=rule.name,
                        reason=f"Rule '{rule.name}' in policy '{policy.name}' evaluated to {rule.effect.value}",
                        evaluation_time_ms=(time.time() - start) * 1000,
                    )
                    self._cache[cache_key] = (decision, time.time())
                    return decision

        decision = AccessDecision(
            allowed=False,
            effect=Effect.DENY,
            policy_name='default_deny',
            rule_name='default_deny_rule',
            reason='No matching allow rule found — default deny',
            evaluation_time_ms=(time.time() - start) * 1000,
        )
        self._cache[cache_key] = (decision, time.time())
        return decision

    def _evaluate_rule(self, rule: PolicyRule, context: Dict[str, Any]) -> bool:
        if not rule.conditions:
            return True
        return all(cond.evaluate(context) for cond in rule.conditions)

    def _find_matching_policies(self, resource_type: str, action: str) -> List[Policy]:
        matched = []
        for policy in self._policies.values():
            if not policy.enabled:
                continue
            if policy.target_resource == '*' or policy.target_resource == resource_type:
                if policy.target_action == '*' or policy.target_action == action:
                    matched.append(policy)
        return matched

    def _build_context(self, request: AccessRequest) -> Dict[str, Any]:
        return {
            'user': {
                'user_id': request.user_id,
                'role': request.role,
                'department': request.department,
                'clearance_level': request.clearance_level,
                'auth_methods': request.user_auth_methods,
            },
            'resource': {
                'type': request.resource_type,
                'id': request.resource_id,
                'sensitivity': request.resource_sensitivity,
            },
            'action': request.action,
            'method': request.method,
            'environment': {
                'ip_address': request.ip_address,
                'geolocation': request.geolocation or {},
                'time_of_day': request.time_of_day,
                'day_of_week': request.day_of_week,
            },
            'device': {
                'trust_score': request.device_trust_score,
            },
            'session': {
                'risk_score': request.session_risk_score,
            },
        }

    def _cache_key(self, request: AccessRequest) -> str:
        return hashlib.sha256(
            json.dumps(asdict(request), sort_keys=True, default=str).encode()
        ).hexdigest()

    def _invalidate_cache(self):
        self._cache.clear()

    def evaluate_access(
        self,
        user_id: str,
        role: str,
        department: str,
        clearance_level: int,
        resource_type: str,
        resource_id: str,
        resource_sensitivity: str,
        action: str,
        method: str = 'GET',
        ip_address: str = '0.0.0.0',
        geolocation: Optional[Dict[str, Any]] = None,
        device_trust_score: float = 0.5,
        session_risk_score: float = 0.0,
    ) -> AccessDecision:
        from datetime import datetime
        now = datetime.now()

        request = AccessRequest(
            user_id=user_id,
            role=role,
            department=department,
            clearance_level=clearance_level,
            resource_type=resource_type,
            resource_id=resource_id,
            resource_sensitivity=resource_sensitivity,
            action=action,
            method=method,
            ip_address=ip_address,
            geolocation=geolocation,
            time_of_day=now.hour,
            day_of_week=now.weekday(),
            device_trust_score=device_trust_score,
            session_risk_score=session_risk_score,
            user_auth_methods=['password'],
        )
        return self.evaluate(request)


abac_engine = ABACEngine()


def require_access(
    resource_type: str,
    action: str,
    resource_sensitivity: str = 'low',
    resource_id_param: str = None,
):
    """Decorator for ABAC-enforced route access."""
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            user_id = session.get('user_id')
            if not user_id:
                return jsonify({'error': 'Authentication required'}), 401

            user = auth_service.get_user_by_id(user_id)
            if not user:
                return jsonify({'error': 'User not found'}), 404

            resource_id = kwargs.get(resource_id_param) if resource_id_param else None

            decision = abac_engine.evaluate_access(
                user_id=user_id,
                role=user.get('role', 'attendee'),
                department=user.get('department', ''),
                clearance_level=user.get('clearance_level', 0),
                resource_type=resource_type,
                resource_id=resource_id or 'unknown',
                resource_sensitivity=resource_sensitivity,
                action=action,
                method=request.method,
                ip_address=request.remote_addr or '0.0.0.0',
            )

            if not decision.allowed:
                logger.warning(
                    f"ABAC denied: user {user_id} role {user.get('role')} "
                    f"action {action} on {resource_type}/{resource_id}"
                )
                return jsonify({
                    'error': 'Access denied by policy',
                    'reason': decision.reason,
                    'policy': decision.policy_name,
                }), 403

            return f(*args, **kwargs)
        return wrapper
    return decorator
