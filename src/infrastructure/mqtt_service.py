import json
import os
import logging
import uuid
from datetime import datetime
from typing import Dict, Any, Optional, List, Callable

logger = logging.getLogger(__name__)

TOPIC_PREFIX = 'attendrix'
TOPICS = {
    'ATTENDANCE': f'{TOPIC_PREFIX}/attendance/{{session_id}}',
    'SESSION_LIFECYCLE': f'{TOPIC_PREFIX}/session/{{session_id}}',
    'NETWORK_STATUS': f'{TOPIC_PREFIX}/network/{{device_id}}',
    'NOTIFICATIONS': f'{TOPIC_PREFIX}/notifications/{{user_id}}',
    'SYSTEM_HEALTH': f'{TOPIC_PREFIX}/system/health',
}

_mock_messages: List[Dict[str, Any]] = []
_mock_subscriptions: Dict[str, int] = {}


class MqttService:
    def __init__(self):
        self.client = None
        self._connected = False
        self._initialized = False
        self._mock_mode = True
        self._broker_url = None
        self._client_id = None
        self._subscriptions: Dict[str, int] = {}
        self._message_handlers: Dict[str, Callable] = {}
        self._connect_time: Optional[datetime] = None
        self._messages_published = 0
        self._messages_received = 0

    @property
    def status(self) -> Dict[str, Any]:
        return {
            'initialized': self._initialized,
            'connected': self._connected,
            'mock_mode': self._mock_mode,
            'broker_url': self._broker_url,
            'client_id': self._client_id,
            'active_subscriptions': len(self._subscriptions),
            'messages_published': self._messages_published,
            'messages_received': self._messages_received,
            'connected_since': self._connect_time.isoformat() if self._connect_time else None,
        }

    def initialize(self, broker_url: Optional[str] = None, client_id: Optional[str] = None):
        if self._initialized:
            return

        self._client_id = client_id or f'attendrix-{uuid.uuid4().hex[:8]}'

        if os.environ.get('USE_MOCK_MQTT', 'true').lower() == 'true':
            logger.info("Using mock MQTT service for development")
            self._mock_mode = True
            self._initialized = True
            return

        self._mock_mode = False
        self._broker_url = broker_url or os.environ.get(
            'MQTT_BROKER_URL', 'mqtt://localhost:1883'
        )

        try:
            import paho.mqtt.client as mqtt

            self.client = mqtt.Client(
                client_id=self._client_id,
                protocol=mqtt.MQTTv311,
                callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            )

            self.client.on_connect = self._on_connect
            self.client.on_disconnect = self._on_disconnect
            self.client.on_message = self._on_message
            self.client.on_subscribe = self._on_subscribe

            username = os.environ.get('MQTT_USERNAME')
            password = os.environ.get('MQTT_PASSWORD')
            if username and password:
                self.client.username_pw_set(username, password)

            self.client.will_set(
                f'{TOPIC_PREFIX}/system/status/{self._client_id}',
                json.dumps({'status': 'offline', 'client_id': self._client_id}),
                qos=1,
                retain=True,
            )

            self._initialized = True
            logger.info(f"MQTT service initialized (broker={self._broker_url})")
        except ImportError:
            logger.warning("paho-mqtt not installed, falling back to mock mode")
            self._mock_mode = True
            self._initialized = True
        except Exception as e:
            logger.error(f"MQTT initialization failed: {e}")
            self._mock_mode = True
            self._initialized = True

    def _on_connect(self, client, userdata, flags, reason_code, properties=None):
        if reason_code == 0:
            self._connected = True
            self._connect_time = datetime.utcnow()
            logger.info(f"Connected to MQTT broker (client_id={self._client_id})")

            client.publish(
                f'{TOPIC_PREFIX}/system/status/{self._client_id}',
                json.dumps({'status': 'online', 'client_id': self._client_id}),
                qos=1, retain=True,
            )

            for topic, qos in self._subscriptions.items():
                client.subscribe(topic, qos=qos)
                logger.debug(f"Resubscribed to {topic} (QoS {qos})")
        else:
            logger.error(f"Failed to connect to MQTT broker (reason_code={reason_code})")

    def _on_disconnect(self, client, userdata, flags, reason_code, properties=None):
        self._connected = False
        logger.warning(f"Disconnected from MQTT broker (reason_code={reason_code})")
        if reason_code != 0:
            logger.info("Scheduling auto-reconnect...")

    def _on_message(self, client, userdata, msg):
        self._messages_received += 1
        try:
            payload = json.loads(msg.payload.decode())
            logger.debug(f"MQTT message received: {msg.topic} -> {payload}")

            for topic_filter, handler in self._message_handlers.items():
                if self._topic_matches(topic_filter, msg.topic):
                    try:
                        handler(msg.topic, payload)
                    except Exception as e:
                        logger.error(f"Handler error for {msg.topic}: {e}")
        except Exception as e:
            logger.warning(f"Failed to process message on {msg.topic}: {e}")

    def _on_subscribe(self, client, userdata, mid, reason_codes, properties):
        logger.debug(f"Subscribed successfully (mid={mid})")

    def connect(self, host: Optional[str] = None, port: Optional[int] = None):
        if self._mock_mode:
            self._connected = True
            self._connect_time = datetime.utcnow()
            logger.info("Mock MQTT: connected (simulated)")
            return True

        if not self._initialized:
            logger.error("MQTT not initialized")
            return False

        host = host or os.environ.get('MQTT_HOST', 'localhost')
        port = port or int(os.environ.get('MQTT_PORT', '1883'))

        try:
            self.client.connect(host, port, keepalive=60)
            self.client.loop_start()
            return True
        except Exception as e:
            logger.error(f"MQTT connection failed: {e}")
            return False

    def disconnect(self):
        if self._mock_mode:
            self._connected = False
            logger.info("Mock MQTT: disconnected (simulated)")
            return

        if self.client:
            try:
                self.client.publish(
                    f'{TOPIC_PREFIX}/system/status/{self._client_id}',
                    json.dumps({'status': 'offline', 'client_id': self._client_id}),
                    qos=1, retain=True,
                )
                self.client.loop_stop()
                self.client.disconnect()
            except Exception as e:
                logger.error(f"MQTT disconnect error: {e}")
        self._connected = False

    def publish(self, topic: str, payload: Dict[str, Any], qos: int = 1) -> bool:
        if self._mock_mode:
            message = {
                'topic': topic,
                'payload': payload,
                'qos': qos,
                'timestamp': datetime.utcnow().isoformat(),
                'mock': True,
            }
            _mock_messages.append(message)
            self._messages_published += 1
            logger.debug(f"Mock MQTT: published to {topic} (QoS {qos})")
            return True

        if not self._connected or not self.client:
            logger.warning(f"MQTT not connected, cannot publish to {topic}")
            return False

        try:
            result = self.client.publish(topic, json.dumps(payload), qos=qos)
            if result.rc == 0:
                self._messages_published += 1
                return True
            logger.warning(f"Publish failed (rc={result.rc})")
            return False
        except Exception as e:
            logger.error(f"Publish error: {e}")
            return False

    def subscribe(self, topic: str, qos: int = 1, handler: Optional[Callable] = None):
        if self._mock_mode:
            self._subscriptions[topic] = qos
            if handler:
                self._message_handlers[topic] = handler
            logger.debug(f"Mock MQTT: subscribed to {topic} (QoS {qos})")
            return True

        self._subscriptions[topic] = qos
        if handler:
            self._message_handlers[topic] = handler

        if self._connected and self.client:
            self.client.subscribe(topic, qos=qos)
        return True

    def unsubscribe(self, topic: str):
        self._subscriptions.pop(topic, None)
        self._message_handlers.pop(topic, None)
        if not self._mock_mode and self._connected and self.client:
            self.client.unsubscribe(topic)

    def get_messages(self, topic: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        if not self._mock_mode:
            return []
        messages = _mock_messages
        if topic:
            messages = [m for m in messages if m['topic'] == topic]
        return messages[-limit:]

    def clear_messages(self):
        if self._mock_mode:
            _mock_messages.clear()

    def _topic_matches(self, subscription: str, topic: str) -> bool:
        sub_parts = subscription.split('/')
        topic_parts = topic.split('/')
        if len(sub_parts) > len(topic_parts) and '#' not in sub_parts:
            return False
        for sp, tp in zip(sub_parts, topic_parts):
            if sp == '#':
                return True
            if sp == '+':
                continue
            if sp != tp:
                return False
        return len(sub_parts) == len(topic_parts)


mqtt_service = MqttService()
