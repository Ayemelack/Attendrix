import json
import time
import logging
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class EventService:
    """Server-Sent Events service for real-time dashboard updates.
    
    This service manages the event stream for each connected admin.
    It polls the database for changes and pushes only delta updates.
    """

    def __init__(self, firebase_service, dashboard_service):
        self.fb = firebase_service
        self.dashboard = dashboard_service

    def generate_stream(self, institution_id: str, user_id: str):
        """Generator for SSE event stream.
        
        Yields SSE-formatted strings with real-time updates.
        Client reconnects automatically on disconnect.
        """
        last_activity_check = datetime.utcnow().isoformat()
        last_alert_check = datetime.utcnow().isoformat()
        last_session_check = datetime.utcnow().isoformat()
        last_checkin_check = datetime.utcnow().isoformat()
        sequence = 0

        def fmt_event(event_type: str, data: dict) -> str:
            nonlocal sequence
            sequence += 1
            payload = json.dumps(data, default=str)
            return f"id: {sequence}\nevent: {event_type}\ndata: {payload}\n\n"

        # Send initial connection event
        yield fmt_event('connected', {
            'status': 'connected',
            'timestamp': datetime.utcnow().isoformat(),
            'user_id': user_id,
            'institution_id': institution_id,
        })

        while True:
            try:
                now = datetime.utcnow().isoformat()

                # Check for new activity
                try:
                    activity = self.dashboard.get_activity_feed(
                        institution_id, limit=5
                    )
                    if activity:
                        newest = activity[0].get('created_at', '')
                        if newest > last_activity_check:
                            yield fmt_event('activity', {
                                'events': activity,
                                'timestamp': now,
                            })
                            last_activity_check = now
                except Exception as e:
                    logger.debug(f"Activity check error: {e}")

                # Check for new security alerts
                try:
                    alerts = self.dashboard.get_security_alerts(
                        institution_id, limit=3
                    )
                    if alerts:
                        newest = alerts[0].get('created_at', '')
                        if newest > last_alert_check:
                            yield fmt_event('security', {
                                'alerts': alerts,
                                'timestamp': now,
                            })
                            last_alert_check = now
                except Exception as e:
                    logger.debug(f"Alert check error: {e}")

                # Check for active session changes
                try:
                    session_data = self.dashboard.get_session_health(
                        institution_id, page=1, per_page=50
                    )
                    active_count = session_data.get('active_sessions', 0)
                    sessions = session_data.get('sessions', [])
                    if sessions:
                        newest = sessions[0].get('created_at', '')
                        if newest > last_session_check:
                            yield fmt_event('sessions', {
                                'active_sessions': active_count,
                                'total_sessions': session_data.get('total_sessions', 0),
                                'sessions': sessions[:5],
                                'timestamp': now,
                            })
                            last_session_check = now
                except Exception as e:
                    logger.debug(f"Session check error: {e}")

                # Check for new check-ins
                try:
                    checkins = self.dashboard.get_recent_checkins(
                        institution_id, since=last_checkin_check
                    )
                    if checkins:
                        yield fmt_event('checkin', {
                            'checkins': checkins,
                            'timestamp': now,
                        })
                        last_checkin_check = now
                except Exception as e:
                    logger.debug(f"Check-in check error: {e}")

                # Periodically push P2P sync status
                try:
                    p2p_data = self.dashboard.get_p2p_sync_status(institution_id) if self.dashboard else {}
                    p2p_ts = p2p_data.get('last_updated', '')
                    if p2p_ts and p2p_ts > last_p2p_check:
                        yield fmt_event('p2p', p2p_data)
                        last_p2p_check = now
                    elif not p2p_ts and sequence % 10 == 0:
                        yield fmt_event('p2p', p2p_data)
                        last_p2p_check = now
                except Exception as e:
                    logger.debug(f"P2P check error: {e}")

                # Periodic keepalive every 15s
                if sequence > 0 and sequence % 5 == 0:
                    yield fmt_event('keepalive', {
                        'timestamp': now,
                        'sequence': sequence,
                    })

                time.sleep(3)

            except GeneratorExit:
                logger.info(f"SSE client disconnected: {user_id}")
                break
            except Exception as e:
                logger.error(f"SSE stream error: {e}")
                try:
                    yield fmt_event('error', {
                        'message': 'Internal stream error',
                        'timestamp': datetime.utcnow().isoformat(),
                    })
                except GeneratorExit:
                    break
                time.sleep(5)

    def generate_student_stream(self, institution_id: str, user_id: str):
        """Generator for student SSE event stream.
        
        Lighter than the admin stream — pushes attendance confirmations,
        session updates, and notifications relevant to a single student.
        """
        last_notification_check = datetime.utcnow().isoformat()
        last_session_check = datetime.utcnow().isoformat()
        last_checkin_check = datetime.utcnow().isoformat()
        sequence = 0

        def fmt_event(event_type: str, data: dict) -> str:
            nonlocal sequence
            sequence += 1
            payload = json.dumps(data, default=str)
            return f"id: {sequence}\nevent: {event_type}\ndata: {payload}\n\n"

        yield fmt_event('connected', {
            'status': 'connected',
            'timestamp': datetime.utcnow().isoformat(),
            'user_id': user_id,
        })

        while True:
            try:
                now = datetime.utcnow().isoformat()

                # Check for new notifications
                try:
                    notifications = self.fb.query_documents(
                        'notifications',
                        filters=[{'field': 'user_id', 'value': user_id}],
                        limit=5,
                    )
                    if notifications:
                        newest = notifications[0].get('created_at', '')
                        if newest > last_notification_check:
                            yield fmt_event('notification', {
                                'notifications': notifications,
                                'timestamp': now,
                            })
                            last_notification_check = now
                except Exception as e:
                    logger.debug(f"Student notification check error: {e}")

                # Check for active session changes
                try:
                    sessions = self.fb.query_documents(
                        'attendance_sessions',
                        filters=[{'field': 'is_active', 'value': True}],
                        limit=10,
                    )
                    if sessions:
                        newest = sessions[0].get('created_at', '')
                        if newest > last_session_check:
                            yield fmt_event('sessions', {
                                'sessions': sessions[:5],
                                'timestamp': now,
                            })
                            last_session_check = now
                except Exception as e:
                    logger.debug(f"Student session check error: {e}")

                # Periodic keepalive every 15s
                if sequence > 0 and sequence % 5 == 0:
                    yield fmt_event('keepalive', {
                        'timestamp': now,
                        'sequence': sequence,
                    })

                time.sleep(3)

            except GeneratorExit:
                logger.info(f"Student SSE disconnected: {user_id}")
                break
            except Exception as e:
                logger.error(f"Student SSE stream error: {e}")
                try:
                    yield fmt_event('error', {
                        'message': 'Internal stream error',
                        'timestamp': datetime.utcnow().isoformat(),
                    })
                except GeneratorExit:
                    break
                time.sleep(5)
        """Quick heartbeat check — returns server-side network status."""
        try:
            network = self.dashboard.get_network_status(institution_id)
            return {
                'server_time': datetime.utcnow().isoformat(),
                'healthy': True,
                'nodes_online': sum(
                    1 for n in network.get('nodes', [])
                    if n.get('status') == 'healthy'
                ),
                'total_nodes': len(network.get('nodes', [])),
            }
        except Exception as e:
            return {
                'server_time': datetime.utcnow().isoformat(),
                'healthy': False,
                'error': str(e),
            }
