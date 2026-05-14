# -*- coding: utf-8 -*-
"""
Seisei Print Agent - WebSocket Client
WebSocket Client for Odoo Bus Communication

Developed by Seisei
"""

import json
import ssl
import time
import logging
import threading
from typing import Callable, Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum

import certifi
import websocket

logger = logging.getLogger(__name__)


class ConnectionState(Enum):
    """WebSocket connection states"""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    ERROR = "error"


@dataclass
class WebSocketConfig:
    """WebSocket connection configuration"""
    url: str
    channels: List[str] = field(default_factory=list)
    cookies: Dict[str, str] = field(default_factory=dict)
    reconnect_interval: int = 5
    max_reconnect_attempts: int = -1  # -1 for infinite
    ping_interval: int = 30
    ping_timeout: int = 10


class OdooWebSocketClient:
    """
    WebSocket client for Odoo bus communication

    Handles:
    - Connection management with auto-reconnect
    - Channel subscription
    - Message routing to handlers
    - Heartbeat/ping management
    """

    def __init__(self, config: WebSocketConfig):
        self.config = config
        self._ws: Optional[websocket.WebSocketApp] = None
        self._thread: Optional[threading.Thread] = None
        self._state = ConnectionState.DISCONNECTED
        self._reconnect_count = 0
        self._should_reconnect = True
        self._last_notification_id = 0

        # Event handlers
        self._on_message_handlers: Dict[str, List[Callable]] = {}
        self._on_state_change: Optional[Callable[[ConnectionState], None]] = None
        self._on_error: Optional[Callable[[Exception], None]] = None

        # Thread safety
        self._lock = threading.Lock()

    @property
    def state(self) -> ConnectionState:
        """Get current connection state"""
        return self._state

    @state.setter
    def state(self, value: ConnectionState):
        """Set connection state and notify listeners"""
        if self._state != value:
            self._state = value
            logger.info(f"WebSocket state changed: {value.value}")
            if self._on_state_change:
                try:
                    self._on_state_change(value)
                except Exception as e:
                    logger.error(f"Error in state change handler: {e}")

    def on_state_change(self, handler: Callable[[ConnectionState], None]):
        """Register state change handler"""
        self._on_state_change = handler

    def on_error(self, handler: Callable[[Exception], None]):
        """Register error handler"""
        self._on_error = handler

    def on_message(self, message_type: str, handler: Callable[[Dict], None]):
        """
        Register message handler for specific message type

        Args:
            message_type: Type of message to handle (e.g., 'print_document')
            handler: Callback function receiving message data
        """
        if message_type not in self._on_message_handlers:
            self._on_message_handlers[message_type] = []
        self._on_message_handlers[message_type].append(handler)

    def connect(self):
        """Start WebSocket connection"""
        if self._state in [ConnectionState.CONNECTED, ConnectionState.CONNECTING]:
            logger.warning("Already connected or connecting")
            return

        self._should_reconnect = True
        self._start_connection()

    def disconnect(self):
        """Disconnect WebSocket"""
        self._should_reconnect = False
        if self._ws:
            self._ws.close()
        self.state = ConnectionState.DISCONNECTED

    def _start_connection(self):
        """Start WebSocket connection in background thread"""
        self.state = ConnectionState.CONNECTING

        # Build cookie header
        cookie_str = "; ".join([f"{k}={v}" for k, v in self.config.cookies.items()])

        self._ws = websocket.WebSocketApp(
            self.config.url,
            on_open=self._on_open,
            on_message=self._on_message,
            on_error=self._on_ws_error,
            on_close=self._on_close,
            cookie=cookie_str,
        )

        self._thread = threading.Thread(
            target=self._run_forever,
            daemon=True,
            name="WebSocketThread"
        )
        self._thread.start()

    def _run_forever(self):
        """Run WebSocket connection loop"""
        try:
            sslopt = {"ca_certs": certifi.where(), "cert_reqs": ssl.CERT_REQUIRED}
            self._ws.run_forever(
                ping_interval=self.config.ping_interval,
                ping_timeout=self.config.ping_timeout,
                sslopt=sslopt,
            )
        except Exception as e:
            logger.error(f"WebSocket run_forever error: {e}")
            self._handle_disconnect()

    def _on_open(self, ws):
        """Handle WebSocket connection opened"""
        logger.info("WebSocket connected")
        self._reconnect_count = 0
        self.state = ConnectionState.CONNECTED

        # Subscribe to channels
        self._subscribe_channels()

    def _subscribe_channels(self):
        """Subscribe to configured channels"""
        if not self.config.channels:
            logger.warning("No channels configured for subscription")
            return

        subscribe_msg = {
            "event_name": "subscribe",
            "data": {
                "channels": self.config.channels,
                "last": self._last_notification_id,
            }
        }

        self._send(subscribe_msg)
        logger.info(f"Subscribed to channels: {self.config.channels}")

    def _on_message(self, ws, message: str):
        """Handle incoming WebSocket message"""
        try:
            data = json.loads(message)
            logger.debug(f"Received message: {data}")

            # Handle different message formats
            if isinstance(data, list):
                # Bus notification format: [[channel, message, ...], ...]
                for notification in data:
                    self._process_notification(notification)
            elif isinstance(data, dict):
                # Direct message format
                self._process_message(data)

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse message: {e}")
        except Exception as e:
            logger.error(f"Error processing message: {e}")

    def _process_notification(self, notification):
        """Process bus notification"""
        # Odoo 18 format: {"id": xxx, "message": {"type": "xxx", "payload": {...}}}
        if isinstance(notification, dict):
            notif_id = notification.get('id', 0)
            if notif_id:
                self._last_notification_id = max(self._last_notification_id, notif_id)

            message = notification.get('message', {})
            if isinstance(message, dict):
                msg_type = message.get('type', 'unknown')
                payload = message.get('payload', message)
                logger.info(f"Notification id={notif_id}: type={msg_type}")
                self._dispatch_message(msg_type, payload)
            return

        # Legacy format: [id, channel, message_type, payload] or [channel, message_type, payload]
        if isinstance(notification, (list, tuple)):
            if len(notification) < 3:
                return

            if len(notification) >= 4 and isinstance(notification[0], int):
                notif_id, channel, msg_type, payload = notification[0], notification[1], notification[2], notification[3]
                self._last_notification_id = max(self._last_notification_id, notif_id)
            else:
                channel, msg_type, payload = notification[0], notification[1], notification[2]

            logger.info(f"Notification from {channel}: type={msg_type}")
            self._dispatch_message(msg_type, payload)

    def _process_message(self, data: Dict):
        """Process direct message"""
        # Odoo 18 format: {"id": xxx, "message": {"type": "xxx", "payload": {...}}}
        if 'message' in data and isinstance(data['message'], dict):
            message = data['message']
            msg_type = message.get('type', 'unknown')
            payload = message.get('payload', message)
        else:
            # Fallback format
            msg_type = data.get('type') or data.get('event_name', 'unknown')
            payload = data.get('data') or data.get('payload', data)

        self._dispatch_message(msg_type, payload)

    def _dispatch_message(self, msg_type: str, payload: Any):
        """Dispatch message to registered handlers"""
        handlers = self._on_message_handlers.get(msg_type, [])

        # Also check for wildcard handlers
        handlers.extend(self._on_message_handlers.get('*', []))

        if not handlers:
            logger.debug(f"No handler for message type: {msg_type}")
            return

        for handler in handlers:
            try:
                handler(payload)
            except Exception as e:
                logger.error(f"Error in message handler for {msg_type}: {e}")

    def _on_ws_error(self, ws, error):
        """Handle WebSocket error"""
        logger.error(f"WebSocket error: {error}")
        self.state = ConnectionState.ERROR

        if self._on_error:
            try:
                self._on_error(error)
            except Exception as e:
                logger.error(f"Error in error handler: {e}")

    def _on_close(self, ws, close_status_code, close_msg):
        """Handle WebSocket connection closed"""
        logger.info(f"WebSocket closed: {close_status_code} - {close_msg}")
        self._handle_disconnect()

    def _handle_disconnect(self):
        """Handle disconnection and attempt reconnect"""
        if not self._should_reconnect:
            self.state = ConnectionState.DISCONNECTED
            return

        max_attempts = self.config.max_reconnect_attempts
        if max_attempts >= 0 and self._reconnect_count >= max_attempts:
            logger.error(f"Max reconnect attempts ({max_attempts}) reached")
            self.state = ConnectionState.ERROR
            return

        self._reconnect_count += 1
        self.state = ConnectionState.RECONNECTING

        # Exponential backoff with max of 60 seconds
        delay = min(60, self.config.reconnect_interval * (2 ** (self._reconnect_count - 1)))
        logger.info(f"Reconnecting in {delay} seconds (attempt {self._reconnect_count})")

        time.sleep(delay)

        if self._should_reconnect:
            self._start_connection()

    def _send(self, data: Dict) -> bool:
        """Send message to WebSocket server"""
        if self._ws is None or self.state != ConnectionState.CONNECTED:
            logger.warning("Cannot send: not connected")
            return False

        try:
            message = json.dumps(data)
            self._ws.send(message)
            logger.debug(f"Sent message: {data}")
            return True
        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            return False

    def send_event(self, event_name: str, data: Dict) -> bool:
        """
        Send event to Odoo server

        Args:
            event_name: Event name (e.g., 'seisei_service_message')
            data: Event data

        Returns:
            bool: True if sent successfully
        """
        message = {
            "event_name": event_name,
            "data": data,
        }
        return self._send(message)

    def sync_printers(self, station_data: Dict) -> bool:
        """
        Sync printers with Odoo server

        Args:
            station_data: Station and printer information

        Returns:
            bool: True if sent successfully
        """
        return self.send_event("seisei_service_message", {
            "message_type": "sync_printers",
            "data": station_data,
        })

    def update_job_status(self, job_id: str, status: str, message: str = "",
                          printer_name: str = "", station_code: str = "") -> bool:
        """
        Update print job status on Odoo server

        Args:
            job_id: Job ID
            status: New status
            message: Status message
            printer_name: Printer name
            station_code: Station code

        Returns:
            bool: True if sent successfully
        """
        return self.send_event("seisei_service_message", {
            "message_type": "job_status_update",
            "data": {
                "job_id": job_id,
                "status": status,
                "message": message,
                "printer_name": printer_name,
                "station_code": station_code,
            }
        })
