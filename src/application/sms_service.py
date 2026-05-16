import logging
import json
from typing import Dict, Any, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class SMSService:
    """SMS gateway service with mock/dev mode support.

    Supports Twilio, Africa's Talking, and a mock mode for development.
    """

    def __init__(self, firebase_service=None):
        self.fb = firebase_service
        self._provider = None
        self._config = {}

    def configure(self, provider: str = 'mock', **kwargs):
        self._provider = provider
        self._config = kwargs
        logger.info(f"SMS service configured: provider={provider}")

    def send_sms(self, to: str, message: str, priority: str = 'normal') -> Dict[str, Any]:
        result = {'to': to, 'message_preview': message[:60], 'status': 'pending', 'provider': self._provider or 'mock', 'timestamp': datetime.utcnow().isoformat()}
        try:
            if self._provider == 'twilio':
                return self._send_twilio(to, message, result)
            elif self._provider == 'africastalking':
                return self._send_africastalking(to, message, result)
            else:
                return self._send_mock(to, message, result)
        except Exception as e:
            logger.error(f"SMS send failed: {e}")
            result['status'] = 'failed'
            result['error'] = str(e)
            return result

    def _send_mock(self, to: str, message: str, result: Dict[str, Any]) -> Dict[str, Any]:
        logger.info(f"[MOCK SMS] To: {to} | Msg: {message[:80]}")
        result['status'] = 'sent'
        result['message_sid'] = f'mock_{datetime.utcnow().timestamp()}'
        result['cost'] = 0
        return result

    def _send_twilio(self, to: str, message: str, result: Dict[str, Any]) -> Dict[str, Any]:
        account_sid = self._config.get('account_sid', '')
        auth_token = self._config.get('auth_token', '')
        from_number = self._config.get('from_number', '')
        if not account_sid or not auth_token:
            return self._send_mock(to, message, result)
        try:
            from twilio.rest import Client
            client = Client(account_sid, auth_token)
            twilio_msg = client.messages.create(body=message, from_=from_number, to=to)
            result['status'] = 'sent'
            result['message_sid'] = twilio_msg.sid
            result['cost'] = float(twilio_msg.price or 0) if twilio_msg.price else 0
            return result
        except ImportError:
            logger.warning("Twilio not installed, falling back to mock")
            return self._send_mock(to, message, result)

    def _send_africastalking(self, to: str, message: str, result: Dict[str, Any]) -> Dict[str, Any]:
        api_key = self._config.get('api_key', '')
        username = self._config.get('username', '')
        if not api_key or not username:
            return self._send_mock(to, message, result)
        try:
            import requests
            resp = requests.post(
                'https://api.africastalking.com/version1/messaging',
                headers={'ApiKey': api_key, 'Accept': 'application/json'},
                data={'username': username, 'to': to, 'message': message, 'from': self._config.get('from_number', '')},
                timeout=15,
            )
            if resp.status_code == 200:
                result['status'] = 'sent'
                result['message_sid'] = resp.json().get('SMSMessageData', {}).get('Recipients', [{}])[0].get('messageId', '')
            else:
                result['status'] = 'failed'
                result['error'] = resp.text
            return result
        except ImportError:
            logger.warning("requests not available for AT SMS")
            return self._send_mock(to, message, result)
        except Exception as e:
            logger.error(f"Africa's Talking SMS error: {e}")
            return self._send_mock(to, message, result)

    def queue_sms(self, to: str, message: str, priority: str = 'normal') -> Dict[str, Any]:
        if not self.fb:
            return self.send_sms(to, message, priority)
        import uuid
        entry = {
            'id': str(uuid.uuid4()),
            'to': to,
            'message': message,
            'priority': priority,
            'status': 'queued',
            'created_at': datetime.utcnow().isoformat(),
            'sent_at': None,
        }
        self.fb.create_document('sms_queue', entry, entry['id'])
        logger.info(f"SMS queued: {entry['id']} -> {to}")
        return entry

    def process_queue(self, batch_size: int = 10) -> int:
        if not self.fb:
            return 0
        queued = self.fb.query_documents('sms_queue', filters=[{'field': 'status', 'value': 'queued'}])
        sent_count = 0
        for entry in queued[:batch_size]:
            result = self.send_sms(entry['to'], entry['message'])
            self.fb.update_document('sms_queue', entry['id'], {
                'status': result['status'],
                'sent_at': result.get('timestamp', datetime.utcnow().isoformat()),
                'message_sid': result.get('message_sid', ''),
            })
            if result['status'] == 'sent':
                sent_count += 1
        return sent_count

    def get_queue_stats(self) -> Dict[str, int]:
        if not self.fb:
            return {'queued': 0, 'sent': 0, 'failed': 0}
        all_sms = self.fb.query_documents('sms_queue')
        return {
            'queued': sum(1 for s in all_sms if s.get('status') == 'queued'),
            'sent': sum(1 for s in all_sms if s.get('status') == 'sent'),
            'failed': sum(1 for s in all_sms if s.get('status') == 'failed'),
            'total': len(all_sms),
        }
