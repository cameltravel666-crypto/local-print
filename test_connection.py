#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Connection Test Script
Tests communication with Odoo server
"""

import sys
import json
import time
import logging
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from core.odoo_client import OdooClient
from core.websocket_client import OdooWebSocketClient, WebSocketConfig, ConnectionState
from core.printer_manager import PrinterManager

# Setup logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_http_connection(server_url: str, database: str, username: str, password: str) -> bool:
    """Test HTTP connection and authentication"""
    print("\n" + "="*50)
    print("Step 1: Testing HTTP Connection")
    print("="*50)

    client = OdooClient(server_url, database)

    print(f"  Server URL: {server_url}")
    print(f"  Database: {database}")
    print(f"  Username: {username}")
    print(f"  Authenticating...")

    if client.authenticate(username, password):
        print(f"  [OK] Authentication successful!")
        print(f"  Session ID: {client.get_session_id()[:20]}...")
        print(f"  User ID: {client.session.uid}")
        return client
    else:
        print(f"  [FAILED] Authentication failed!")
        return None


def test_websocket_connection(server_url: str, ws_port: int, cookies: dict, machine_id: str) -> bool:
    """Test WebSocket connection"""
    print("\n" + "="*50)
    print("Step 2: Testing WebSocket Connection")
    print("="*50)

    # Build WebSocket URL properly
    from urllib.parse import urlparse
    parsed = urlparse(server_url)
    ws_scheme = 'wss' if parsed.scheme == 'https' else 'ws'
    ws_host = parsed.hostname

    # Use provided ws_port, or default based on scheme
    if ws_port:
        ws_url = f"{ws_scheme}://{ws_host}:{ws_port}/websocket"
    else:
        ws_url = f"{ws_scheme}://{ws_host}/websocket"

    channel = f"ylhc_service.{machine_id}"

    print(f"  WebSocket URL: {ws_url}")
    print(f"  Channel: {channel}")

    config = WebSocketConfig(
        url=ws_url,
        channels=[channel],
        cookies=cookies,
        reconnect_interval=5,
        max_reconnect_attempts=1,
    )

    ws_client = OdooWebSocketClient(config)

    # Track connection state
    connected_event = {"connected": False, "error": None}

    def on_state_change(state):
        print(f"  WebSocket state: {state.value}")
        if state == ConnectionState.CONNECTED:
            connected_event["connected"] = True
        elif state == ConnectionState.ERROR:
            connected_event["error"] = "Connection error"

    def on_message(data):
        print(f"  Received message: {json.dumps(data, indent=2)[:200]}...")

    ws_client.on_state_change(on_state_change)
    ws_client.on_message("*", on_message)

    print("  Connecting...")
    ws_client.connect()

    # Wait for connection
    timeout = 10
    start = time.time()
    while not connected_event["connected"] and not connected_event["error"]:
        if time.time() - start > timeout:
            connected_event["error"] = "Connection timeout"
            break
        time.sleep(0.5)

    if connected_event["connected"]:
        print("  [OK] WebSocket connected!")
        return ws_client
    else:
        print(f"  [FAILED] {connected_event['error']}")
        ws_client.disconnect()
        return None


def test_printer_sync(ws_client: OdooWebSocketClient, machine_name: str, machine_id: str):
    """Test printer synchronization"""
    print("\n" + "="*50)
    print("Step 3: Testing Printer Sync")
    print("="*50)

    # Discover local printers
    printer_manager = PrinterManager()
    printers = printer_manager.discover_printers()

    print(f"  Found {len(printers)} local printers:")
    for p in printers:
        default_mark = " (default)" if p.is_default else ""
        print(f"    - {p.name}{default_mark}")

    # Build sync data
    sync_data = printer_manager.build_sync_data(
        machine_name=machine_name,
        machine_id=machine_id,
        location_tag="Test Location",
        config_id=machine_id,
    )

    print(f"\n  Sending sync data to Odoo...")
    print(f"  Machine Name: {machine_name}")
    print(f"  Machine ID: {machine_id}")

    success = ws_client.sync_printers(sync_data)

    if success:
        print("  [OK] Sync data sent!")
        print("  Check Odoo to verify the station and printers were created.")
        return True
    else:
        print("  [FAILED] Failed to send sync data")
        return False


def test_message_receive(ws_client: OdooWebSocketClient, duration: int = 30):
    """Test receiving messages from Odoo"""
    print("\n" + "="*50)
    print(f"Step 4: Listening for Messages ({duration}s)")
    print("="*50)
    print("  Waiting for messages from Odoo...")
    print("  Try printing a test page from Odoo to test the connection.")
    print("  Press Ctrl+C to stop.\n")

    messages_received = []

    def on_print_document(data):
        print(f"\n  [RECEIVED] Print Document:")
        print(f"    Job ID: {data.get('id', 'N/A')}")
        print(f"    Printer: {data.get('printer_name', 'N/A')}")
        print(f"    Type: {data.get('type', 'N/A')}")
        messages_received.append(data)

    def on_printer_test(data):
        print(f"\n  [RECEIVED] Printer Test:")
        print(f"    Job ID: {data.get('id', 'N/A')}")
        print(f"    Printer: {data.get('printer_name', 'N/A')}")
        messages_received.append(data)

    def on_any_message(data):
        msg_type = data.get('type', 'unknown') if isinstance(data, dict) else 'raw'
        print(f"\n  [RECEIVED] Message (type: {msg_type})")

    ws_client.on_message("print_document", on_print_document)
    ws_client.on_message("printer_test", on_printer_test)

    try:
        time.sleep(duration)
    except KeyboardInterrupt:
        print("\n  Stopped by user.")

    print(f"\n  Total messages received: {len(messages_received)}")
    return len(messages_received) > 0


def main():
    parser = argparse.ArgumentParser(description="Test Odoo connection")
    parser.add_argument("--url", required=True, help="Odoo server URL (e.g., http://localhost:8069)")
    parser.add_argument("--database", required=True, help="Database name")
    parser.add_argument("--username", required=True, help="Username")
    parser.add_argument("--password", required=True, help="Password")
    parser.add_argument("--ws-port", type=int, default=8072, help="WebSocket port (default: 8072)")
    parser.add_argument("--machine-name", default="Test-Machine", help="Machine name")
    parser.add_argument("--machine-id", default="TEST001", help="Machine ID")
    parser.add_argument("--listen", type=int, default=30, help="Listen duration in seconds")

    args = parser.parse_args()

    print("\n" + "="*50)
    print("  Local Print Agent - Connection Test")
    print("="*50)

    # Step 1: Test HTTP
    odoo_client = test_http_connection(
        args.url, args.database, args.username, args.password
    )
    if not odoo_client:
        print("\n[FAILED] HTTP connection failed. Cannot proceed.")
        return 1

    # Step 2: Test WebSocket
    ws_client = test_websocket_connection(
        args.url, args.ws_port, odoo_client.get_cookies(), args.machine_id
    )
    if not ws_client:
        print("\n[FAILED] WebSocket connection failed. Cannot proceed.")
        return 1

    # Step 3: Test Printer Sync
    test_printer_sync(ws_client, args.machine_name, args.machine_id)

    # Step 4: Listen for messages
    test_message_receive(ws_client, args.listen)

    # Cleanup
    ws_client.disconnect()
    odoo_client.logout()

    print("\n" + "="*50)
    print("  Test Complete!")
    print("="*50)

    return 0


if __name__ == "__main__":
    sys.exit(main())
