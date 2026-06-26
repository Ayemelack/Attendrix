"""
NEW ACCOUNT ISOLATION MODULE
Attendrix distributed attendance system

Ensures new accounts start with zero data isolation - no inherited records,
statistics, or leaked data from other accounts/institutions.
"""

import logging
from typing import Dict, Any, Tuple, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class NewAccountPolicy:
    """Policy for new account data isolation."""
    # Visibility flags
    can_see_attendance_records: bool = False
    can_see_statistics: bool = False
    can_see_colleagues: bool = False
    can_see_classes: bool = False
    can_see_institution_data: bool = False
    can_create_content: bool = False
    
    # Action flags
    can_record_attendance: bool = False
    can_submit_leave: bool = False
    can_view_grades: bool = False
    can_send_messages: bool = False
    
    # Account maturation time (seconds)
    isolation_period_seconds: int = 86400  # 24 hours


class NewAccountIsolationManager:
    """Manages data isolation for new accounts."""

    def __init__(self):
        """Initialize new account isolation manager."""
        self.new_accounts: Dict[str, Dict[str, Any]] = {}  # {user_id: metadata}

    def register_new_account(
        self,
        user_id: str,
        institution_id: str,
        role: str,
    ) -> NewAccountPolicy:
        """
        Register new account with isolation policy.
        
        Args:
            user_id: New user ID
            institution_id: Institution
            role: User role (student, lecturer, admin)
            
        Returns:
            NewAccountPolicy for this account
        """
        import time

        # Create role-specific isolation policy
        policy = self._create_isolation_policy_for_role(role)

        metadata = {
            'user_id': user_id,
            'institution_id': institution_id,
            'role': role,
            'created_at': int(time.time()),
            'policy': policy,
        }

        self.new_accounts[user_id] = metadata

        logger.info(
            f'New account registered with isolation: user={user_id}, role={role}, isolation_period={policy.isolation_period_seconds}s',
            extra={'user_id': user_id, 'institution_id': institution_id}
        )

        return policy

    def get_account_isolation_policy(self, user_id: str) -> Optional[NewAccountPolicy]:
        """Get current isolation policy for account."""
        if user_id not in self.new_accounts:
            # Account not in new account registry (mature account)
            return None

        metadata = self.new_accounts[user_id]
        policy = metadata['policy']

        import time
        now = int(time.time())
        created_at = metadata['created_at']
        age_seconds = now - created_at

        # If isolation period expired, remove from isolation
        if age_seconds > policy.isolation_period_seconds:
            del self.new_accounts[user_id]
            logger.info(
                f'Account matured - isolation lifted: user={user_id}',
                extra={'age_seconds': age_seconds}
            )
            return None

        return policy

    def enforce_isolation_on_query(
        self,
        user_id: str,
        query_type: str,  # 'attendance', 'statistics', 'colleagues', etc.
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if query is allowed under isolation policy.
        
        Args:
            user_id: User ID
            query_type: Type of query being made
            
        Returns:
            (is_allowed, error_message)
        """
        policy = self.get_account_isolation_policy(user_id)

        if policy is None:
            # No isolation - allow query
            return True, None

        # Check policy for this query type
        allowed_map = {
            'attendance_records': policy.can_see_attendance_records,
            'statistics': policy.can_see_statistics,
            'colleagues': policy.can_see_colleagues,
            'classes': policy.can_see_classes,
            'institution_data': policy.can_see_institution_data,
            'content': policy.can_create_content,
        }

        is_allowed = allowed_map.get(query_type, False)

        if not is_allowed:
            logger.warning(
                f'Query blocked by new account isolation: user={user_id}, query={query_type}',
                extra={'user_id': user_id, 'query_type': query_type}
            )
            return False, f'This feature is not yet available for new accounts. Please try again later.'

        return True, None

    def enforce_isolation_on_action(
        self,
        user_id: str,
        action_type: str,  # 'record_attendance', 'submit_leave', etc.
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if action is allowed under isolation policy.
        
        Args:
            user_id: User ID
            action_type: Type of action
            
        Returns:
            (is_allowed, error_message)
        """
        policy = self.get_account_isolation_policy(user_id)

        if policy is None:
            # No isolation - allow action
            return True, None

        # Check policy for this action
        allowed_map = {
            'record_attendance': policy.can_record_attendance,
            'submit_leave': policy.can_submit_leave,
            'view_grades': policy.can_view_grades,
            'send_messages': policy.can_send_messages,
        }

        is_allowed = allowed_map.get(action_type, False)

        if not is_allowed:
            logger.warning(
                f'Action blocked by new account isolation: user={user_id}, action={action_type}',
                extra={'user_id': user_id, 'action_type': action_type}
            )
            return False, f'This action is not yet available for new accounts.'

        return True, None

    def get_isolated_dashboard_data(self, user_id: str, role: str) -> Dict[str, Any]:
        """
        Get safe dashboard data for isolated account.
        
        Returns empty/minimal data to avoid leaking information.
        """
        policy = self.get_account_isolation_policy(user_id)

        if policy is None:
            # No isolation - return full data
            return {}

        # Return minimal, safe dashboard
        if role == 'student':
            return {
                'attendance_records': [],
                'statistics': {
                    'present': 0,
                    'absent': 0,
                    'late': 0,
                    'average_attendance': 0.0,
                },
                'upcoming_classes': [],
                'messages': [],
                'notice': 'Your account is new. Some features will be available after 24 hours.',
            }

        elif role == 'lecturer':
            return {
                'classes': [],
                'attendance_sessions': [],
                'statistics': {
                    'total_students': 0,
                    'average_attendance': 0.0,
                },
                'notice': 'Your account is new. Some features will be available after 24 hours.',
            }

        elif role == 'admin':
            return {
                'institutions': [],
                'users': [],
                'audit_logs': [],
                'notice': 'Your account is new. Some features will be available after 24 hours.',
            }

        return {}

    def _create_isolation_policy_for_role(self, role: str) -> NewAccountPolicy:
        """Create appropriate isolation policy for role."""
        policy = NewAccountPolicy()

        if role == 'student':
            # Students can see minimal data
            policy.can_see_attendance_records = True  # Only own records
            policy.can_record_attendance = True  # Can record own attendance
            policy.can_view_grades = True
            # But cannot see colleagues, institution stats, etc.
            policy.can_see_colleagues = False
            policy.can_see_institution_data = False
            policy.can_see_statistics = False

        elif role == 'lecturer':
            # Lecturers can create content quickly
            policy.can_create_content = True
            policy.can_record_attendance = True
            policy.can_see_classes = True
            # But limited visibility of other data
            policy.can_see_colleagues = False
            policy.can_see_institution_data = False

        elif role == 'admin':
            # Admins have more access but still isolated during onboarding
            policy.can_see_institution_data = True
            policy.can_see_colleagues = True
            # But cannot modify critical settings until verified
            policy.can_create_content = False

        # All roles have default 24-hour isolation
        policy.isolation_period_seconds = 86400

        return policy
