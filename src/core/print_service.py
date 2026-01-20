# -*- coding: utf-8 -*-
"""
Seisei Print Agent - Print Service
Main service class that coordinates all components

Developed by Seisei
"""

import base64
import json
import logging
import threading
import time
from typing import Callable, Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum

from .odoo_client import OdooClient
from .websocket_client import OdooWebSocketClient, WebSocketConfig, ConnectionState
from .printer_manager import PrinterManager, PrintJob, PrinterInfo

logger = logging.getLogger(__name__)


class ServiceState(Enum):
    """Service state enumeration"""
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    ERROR = "error"


@dataclass
class ServerConnection:
    """Represents a connection to an Odoo server"""
    server_id: str
    server_name: str
    server_url: str
    database: str
    username: str
    password: str
    http_port: int
    websocket_port: int
    config_id: str = ""

    odoo_client: Optional[OdooClient] = None
    ws_client: Optional[OdooWebSocketClient] = None
    is_connected: bool = False


class PrintService:
    """
    Main print service class

    Manages:
    - Multiple server connections
    - Printer discovery and management
    - Print job processing
    - WebSocket communication
    """

    def __init__(self, machine_name: str, machine_id: str, location_tag: str = ""):
        self.machine_name = machine_name
        self.machine_id = machine_id
        self.location_tag = location_tag

        self.state = ServiceState.STOPPED
        self._connections: Dict[str, ServerConnection] = {}
        self._printer_manager = PrinterManager()

        # Sync settings
        self._sync_interval = 30  # seconds
        self._sync_thread: Optional[threading.Thread] = None
        self._should_run = False

        # Event callbacks
        self._on_state_change: Optional[Callable[[ServiceState], None]] = None
        self._on_connection_change: Optional[Callable[[str, bool], None]] = None
        self._on_job_received: Optional[Callable[[Dict], None]] = None
        self._on_job_completed: Optional[Callable[[str, bool, str], None]] = None
        self._on_log: Optional[Callable[[str, str], None]] = None

        # Track processed job IDs to prevent duplicate processing
        self._processed_jobs: set = set()

    @property
    def printer_manager(self) -> PrinterManager:
        """Get printer manager instance"""
        return self._printer_manager

    def set_sync_interval(self, interval: int):
        """Set printer sync interval in seconds"""
        self._sync_interval = max(10, interval)

    def on_state_change(self, callback: Callable[[ServiceState], None]):
        """Register state change callback"""
        self._on_state_change = callback

    def on_connection_change(self, callback: Callable[[str, bool], None]):
        """Register connection change callback (server_id, is_connected)"""
        self._on_connection_change = callback

    def on_job_received(self, callback: Callable[[Dict], None]):
        """Register job received callback"""
        self._on_job_received = callback

    def on_job_completed(self, callback: Callable[[str, bool, str], None]):
        """Register job completed callback (job_id, success, message)"""
        self._on_job_completed = callback

    def on_log(self, callback: Callable[[str, str], None]):
        """Register log callback (level, message)"""
        self._on_log = callback

    def _log(self, level: str, message: str):
        """Log message and notify callback"""
        getattr(logger, level.lower())(message)
        if self._on_log:
            try:
                self._on_log(level, message)
            except Exception:
                pass

    def _set_state(self, state: ServiceState):
        """Set service state and notify"""
        self.state = state
        if self._on_state_change:
            try:
                self._on_state_change(state)
            except Exception as e:
                logger.error(f"Error in state change callback: {e}")

    def add_server(self, server_id: str, server_name: str, server_url: str,
                   database: str, username: str, password: str,
                   http_port: int = 8069, websocket_port: int = 8072) -> bool:
        """
        Add a server configuration

        Returns:
            bool: True if added successfully
        """
        if server_id in self._connections:
            self._log("warning", f"Server {server_id} already exists")
            return False

        connection = ServerConnection(
            server_id=server_id,
            server_name=server_name,
            server_url=server_url,
            database=database,
            username=username,
            password=password,
            http_port=http_port,
            websocket_port=websocket_port,
            config_id=server_id,
        )

        self._connections[server_id] = connection
        self._log("info", f"Added server: {server_name}")
        return True

    def remove_server(self, server_id: str):
        """Remove a server configuration"""
        if server_id in self._connections:
            conn = self._connections[server_id]
            self._disconnect_server(conn)
            del self._connections[server_id]
            self._log("info", f"Removed server: {conn.server_name}")

    def start(self) -> bool:
        """
        Start the print service

        Returns:
            bool: True if started successfully
        """
        if self.state == ServiceState.RUNNING:
            self._log("warning", "Service already running")
            return True

        self._set_state(ServiceState.STARTING)
        self._should_run = True

        # Discover printers
        self._log("info", "Discovering printers...")
        printers = self._printer_manager.discover_printers()
        self._log("info", f"Found {len(printers)} printers")

        # Connect to all servers
        connected_count = 0
        for server_id, conn in self._connections.items():
            if self._connect_server(conn):
                connected_count += 1

        if connected_count == 0 and len(self._connections) > 0:
            self._log("error", "Failed to connect to any server")
            self._set_state(ServiceState.ERROR)
            return False

        # Start sync thread
        self._start_sync_thread()

        self._set_state(ServiceState.RUNNING)
        self._log("info", "Print service started")
        return True

    def stop(self):
        """Stop the print service"""
        if self.state == ServiceState.STOPPED:
            return

        self._set_state(ServiceState.STOPPING)
        self._should_run = False

        # Stop sync thread
        if self._sync_thread and self._sync_thread.is_alive():
            self._sync_thread.join(timeout=5)

        # Disconnect all servers
        for conn in self._connections.values():
            self._disconnect_server(conn)

        self._set_state(ServiceState.STOPPED)
        self._log("info", "Print service stopped")

    def _connect_server(self, conn: ServerConnection) -> bool:
        """Connect to a single server"""
        try:
            self._log("info", f"Connecting to {conn.server_name}...")

            # Create HTTP client and authenticate
            from urllib.parse import urlparse
            parsed_http = urlparse(conn.server_url)
            # For HTTPS with port 443 or HTTP with port 80, don't append port
            if (parsed_http.scheme == 'https' and conn.http_port == 443) or \
               (parsed_http.scheme == 'http' and conn.http_port == 80):
                http_url = conn.server_url
            else:
                http_url = f"{parsed_http.scheme}://{parsed_http.hostname}:{conn.http_port}"
            conn.odoo_client = OdooClient(http_url, conn.database)

            if not conn.odoo_client.authenticate(conn.username, conn.password):
                self._log("error", f"Authentication failed for {conn.server_name}")
                return False

            # Create WebSocket client - properly build URL
            from urllib.parse import urlparse
            parsed = urlparse(conn.server_url)
            ws_scheme = 'wss' if parsed.scheme == 'https' else 'ws'
            ws_host = parsed.hostname
            ws_url = f"{ws_scheme}://{ws_host}:{conn.websocket_port}/websocket"
            # Use configurable channel prefix from module settings
            try:
                from .. import DEFAULT_CHANNEL_PREFIX
            except ImportError:
                DEFAULT_CHANNEL_PREFIX = "seisei_service"
            channel = f"{DEFAULT_CHANNEL_PREFIX}.{self.machine_id}"

            ws_config = WebSocketConfig(
                url=ws_url,
                channels=[channel],
                cookies=conn.odoo_client.get_cookies(),
                reconnect_interval=5,
            )

            conn.ws_client = OdooWebSocketClient(ws_config)

            # Register message handlers
            conn.ws_client.on_message("print_document", lambda data: self._handle_print_job(conn, data))
            conn.ws_client.on_message("pos_receipt_print", lambda data: self._handle_print_job(conn, data))
            conn.ws_client.on_message("printer_test", lambda data: self._handle_test_print(conn, data))
            conn.ws_client.on_message("sync_printer_status", lambda data: self._handle_sync_request(conn, data))

            # Register state change handler
            conn.ws_client.on_state_change(
                lambda state: self._handle_ws_state_change(conn, state)
            )

            # Connect WebSocket (async - will trigger state change handler when connected)
            conn.ws_client.connect()
            # Note: is_connected will be set by _handle_ws_state_change when WebSocket connects
            # Initial sync will also be triggered by the state change handler

            self._log("info", f"Initiating connection to {conn.server_name}...")

            return True

        except Exception as e:
            self._log("error", f"Failed to connect to {conn.server_name}: {e}")
            return False

    def _disconnect_server(self, conn: ServerConnection):
        """Disconnect from a server"""
        if conn.ws_client:
            conn.ws_client.disconnect()
            conn.ws_client = None

        if conn.odoo_client:
            conn.odoo_client.logout()
            conn.odoo_client = None

        conn.is_connected = False

        if self._on_connection_change:
            try:
                self._on_connection_change(conn.server_id, False)
            except Exception:
                pass

    def _handle_ws_state_change(self, conn: ServerConnection, state: ConnectionState):
        """Handle WebSocket state change"""
        conn.is_connected = (state == ConnectionState.CONNECTED)

        if self._on_connection_change:
            try:
                self._on_connection_change(conn.server_id, conn.is_connected)
            except Exception:
                pass

        if state == ConnectionState.CONNECTED:
            # Sync printers after reconnection
            self._sync_printers(conn)

    def _handle_print_job(self, conn: ServerConnection, data: Dict):
        """Handle incoming print job - dispatch to worker thread to avoid blocking WebSocket"""
        job_id = data.get('id', 'unknown')
        printer_name = data.get('printer_name', '')

        self._log("info", f"Received print job: {job_id} for {printer_name}")

        if self._on_job_received:
            try:
                self._on_job_received(data)
            except Exception:
                pass

        # Execute print in separate thread to avoid blocking WebSocket
        thread = threading.Thread(
            target=self._execute_print_job,
            args=(conn, data),
            daemon=True,
            name=f"PrintJob-{job_id}"
        )
        thread.start()

    def _execute_print_job(self, conn: ServerConnection, data: Dict):
        """Execute print job in worker thread"""
        job_id = data.get('id', 'unknown')
        printer_name = data.get('printer_name', '')
        job_type = data.get('type', 'print_document')

        # Skip non-print job types (sync notifications, status updates, etc.)
        non_print_types = [
            'sync_result_notification',
            'sync_error_notification',
            'station_sync_error_notification',
            'printer_sync_notification',
            'update_job_status_notification',
        ]
        if job_type in non_print_types:
            self._log("debug", f"Skipping non-print job type: {job_type}")
            return

        # Prevent duplicate processing of same job
        if job_id in self._processed_jobs:
            self._log("debug", f"Skipping already processed job: {job_id}")
            return
        self._processed_jobs.add(job_id)
        # Clean up old job IDs (keep last 1000)
        if len(self._processed_jobs) > 1000:
            self._processed_jobs = set(list(self._processed_jobs)[-500:])

        try:
            # Handle test print job type
            if job_type == 'printer_test':
                self._log("info", f"Job {job_id}: Test print for {printer_name}")

                # Check if printer exists first
                printer = self._printer_manager.get_printer(printer_name)
                if not printer:
                    error_msg = f"Printer not found: {printer_name}"
                    self._log("error", f"Job {job_id}: {error_msg}")
                    self._report_job_status(conn, job_id, 'failed', error_msg, printer_name)
                    return

                success = self._printer_manager.print_test_page(printer_name)
                if success:
                    self._log("info", f"Job {job_id}: Test print successful")
                    self._report_job_status(conn, job_id, 'completed', 'Test print successful', printer_name)
                else:
                    self._log("error", f"Job {job_id}: Test print failed")
                    self._report_job_status(conn, job_id, 'failed', 'Test print failed', printer_name)
                return

            copies = data.get('copies', 1)
            metadata = data.get('metadata', {})

            # Extract document data - support both doc_data and escpos_commands
            doc_data = metadata.get('doc_data', '')
            escpos_commands = metadata.get('escpos_commands', '')
            doc_format = metadata.get('doc_format', 'pdf')
            paper_format = metadata.get('paper_format', {})

            # Determine document source
            if escpos_commands:
                # ESC/POS commands from POS receipt printing
                doc_data = escpos_commands
                doc_format = 'escpos'
                self._log("info", f"Job {job_id}: Using ESC/POS commands")

            if not doc_data:
                self._log("error", f"Job {job_id}: No document data")
                self._report_job_status(conn, job_id, 'failed', 'No document data', printer_name)
                return

            # Decode base64 document
            try:
                document_bytes = base64.b64decode(doc_data)
            except Exception as e:
                self._log("error", f"Job {job_id}: Failed to decode document: {e}")
                self._report_job_status(conn, job_id, 'failed', f'Decode error: {e}', printer_name)
                return

            # Create print job
            job = PrintJob(
                job_id=job_id,
                printer_name=printer_name,
                document_data=document_bytes,
                document_format=doc_format,
                copies=copies,
                paper_format=paper_format,
            )

            # Execute print (blocking, but in worker thread)
            success = self._printer_manager.print_document(job)

            if success:
                self._log("info", f"Job {job_id}: Printed successfully")
                self._report_job_status(conn, job_id, 'completed', 'Print completed', printer_name)
            else:
                self._log("error", f"Job {job_id}: Print failed")
                self._report_job_status(conn, job_id, 'failed', 'Print failed', printer_name)

            if self._on_job_completed:
                try:
                    self._on_job_completed(job_id, success, "Print completed" if success else "Print failed")
                except Exception:
                    pass

        except Exception as e:
            self._log("error", f"Error executing print job {job_id}: {e}")
            self._report_job_status(conn, job_id, 'failed', str(e), printer_name)

    def _handle_test_print(self, conn: ServerConnection, data: Dict):
        """Handle test print request - dispatch to worker thread"""
        job_id = data.get('id', 'unknown')
        printer_name = data.get('printer_name', '')

        self._log("info", f"Test print request for: {printer_name}")

        # Execute in separate thread to avoid blocking WebSocket
        thread = threading.Thread(
            target=self._execute_test_print,
            args=(conn, job_id, printer_name),
            daemon=True,
            name=f"TestPrint-{job_id}"
        )
        thread.start()

    def _execute_test_print(self, conn: ServerConnection, job_id: str, printer_name: str):
        """Execute test print in worker thread"""
        try:
            success = self._printer_manager.print_test_page(printer_name)

            if success:
                self._log("info", f"Test print successful: {printer_name}")
                self._report_job_status(conn, job_id, 'completed', 'Test print successful', printer_name)
            else:
                self._log("error", f"Test print failed: {printer_name}")
                self._report_job_status(conn, job_id, 'failed', 'Test print failed', printer_name)
        except Exception as e:
            self._log("error", f"Error in test print: {e}")
            self._report_job_status(conn, job_id, 'failed', str(e), printer_name)

    def _handle_sync_request(self, conn: ServerConnection, data: Dict):
        """Handle printer sync request"""
        self._log("info", "Received sync request")
        self._sync_printers(conn)

    def _report_job_status(self, conn: ServerConnection, job_id: str, status: str,
                           message: str, printer_name: str):
        """Report job status back to Odoo via HTTP API"""
        self._log("info", f"Reporting job status: {job_id} -> {status}")

        # Use HTTP API to update status (more reliable than WebSocket)
        if conn.odoo_client:
            try:
                # Find job by job_id and update
                jobs = conn.odoo_client.search_read(
                    'seisei.print.job',
                    [('job_id', '=', job_id)],
                    ['id'],
                    limit=1
                )
                if jobs:
                    result = conn.odoo_client.write(
                        'seisei.print.job',
                        [jobs[0]['id']],
                        {
                            'status': status,
                            'error_message': message if status == 'failed' else '',
                        }
                    )
                    self._log("info", f"Status updated via HTTP: {result}")
                else:
                    self._log("warning", f"Job not found in Odoo: {job_id}")
            except Exception as e:
                self._log("error", f"Failed to update status via HTTP: {e}")
                # Fallback to WebSocket
                if conn.ws_client and conn.is_connected:
                    conn.ws_client.update_job_status(
                        job_id=job_id,
                        status=status,
                        message=message,
                        printer_name=printer_name,
                        station_code=self.machine_id,
                    )
        else:
            self._log("error", "No Odoo client available for status update")

    def _sync_printers(self, conn: ServerConnection):
        """Sync printers with Odoo server"""
        if not conn.ws_client or not conn.is_connected:
            return

        try:
            # Refresh printer list
            self._printer_manager.discover_printers()

            # Build sync data
            sync_data = self._printer_manager.build_sync_data(
                machine_name=self.machine_name,
                machine_id=self.machine_id,
                location_tag=self.location_tag,
                config_id=conn.config_id,
            )

            # Send sync
            conn.ws_client.sync_printers(sync_data)
            self._log("info", f"Synced printers to {conn.server_name}")

        except Exception as e:
            self._log("error", f"Failed to sync printers: {e}")

    def _start_sync_thread(self):
        """Start periodic printer sync thread"""
        def sync_loop():
            while self._should_run:
                time.sleep(self._sync_interval)
                if not self._should_run:
                    break

                for conn in self._connections.values():
                    if conn.is_connected:
                        self._sync_printers(conn)

        self._sync_thread = threading.Thread(target=sync_loop, daemon=True, name="PrinterSyncThread")
        self._sync_thread.start()

    def get_connections(self) -> List[Dict]:
        """Get list of server connections with status"""
        result = []
        for conn in self._connections.values():
            result.append({
                'server_id': conn.server_id,
                'server_name': conn.server_name,
                'server_url': conn.server_url,
                'database': conn.database,
                'is_connected': conn.is_connected,
            })
        return result

    def get_printers(self) -> List[PrinterInfo]:
        """Get list of discovered printers"""
        return self._printer_manager.get_all_printers()

    def refresh_printers(self) -> List[PrinterInfo]:
        """Refresh printer list"""
        return self._printer_manager.discover_printers()

    def manual_sync(self):
        """Manually trigger printer sync to all connected servers"""
        for conn in self._connections.values():
            if conn.is_connected:
                self._sync_printers(conn)
