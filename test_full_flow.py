#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Seisei Print Agent - Full Flow Test
Creates printer, triggers test, listens for message

Developed by Seisei
"""

import sys
import json
import time
import logging
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from core.odoo_client import OdooClient
from core.websocket_client import OdooWebSocketClient, WebSocketConfig, ConnectionState

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    server_url = "https://demo.nagashiro.top"
    database = "test001"
    username = "test"
    password = "test"
    machine_id = "MAC001"

    print("\n" + "=" * 60)
    print("  Full Flow Test - Odoo Print Agent Communication")
    print("=" * 60)

    # Step 1: Authenticate
    print("\n[Step 1] Authenticating with Odoo...")
    client = OdooClient(server_url, database)
    if not client.authenticate(username, password):
        print("  FAILED: Authentication failed!")
        return 1
    print(f"  OK: Authenticated as uid {client.session.uid}")

    # Step 2: Get or create station
    print("\n[Step 2] Getting station...")
    stations = client.search_read(
        'ylhc.station',
        domain=[('code', '=', machine_id)],
        fields=['id', 'name', 'code']
    )

    if stations:
        station_id = stations[0]['id']
        print(f"  OK: Found station: {stations[0]['name']} (id: {station_id})")
    else:
        print("  Creating new station...")
        station_id = client.create('ylhc.station', {
            'name': 'Test Station',
            'code': machine_id,
            'location': 'Test Location',
            'is_active': True
        })
        print(f"  OK: Created station id: {station_id}")

    # Step 3: Get or create test printer
    print("\n[Step 3] Getting/creating test printer...")
    printers = client.search_read(
        'ylhc.printer',
        domain=[('station_id', '=', station_id), ('name', '=', 'TestPrinter')],
        fields=['id', 'name']
    )

    if printers:
        printer_id = printers[0]['id']
        print(f"  OK: Found printer: {printers[0]['name']} (id: {printer_id})")
    else:
        print("  Creating new test printer...")
        printer_id = client.create('ylhc.printer', {
            'name': 'TestPrinter',
            'system_name': 'Test Printer',
            'station_id': station_id,
            'status': 'idle',
            'is_default': False,
            'service_sync': True
        })
        print(f"  OK: Created printer id: {printer_id}")

    # Step 4: Connect WebSocket
    print("\n[Step 4] Connecting WebSocket...")
    channel = f"ylhc_service.{machine_id}"

    ws_config = WebSocketConfig(
        url="wss://demo.nagashiro.top:443/websocket",
        channels=[channel],
        cookies=client.get_cookies(),
        reconnect_interval=5,
        max_reconnect_attempts=3,
    )

    ws_client = OdooWebSocketClient(ws_config)

    message_received = {"count": 0, "data": None}

    def on_message(data):
        message_received["count"] += 1
        message_received["data"] = data
        print(f"\n  >>> RECEIVED MESSAGE <<<")
        print(f"  Type: {data.get('type', 'N/A')}")
        print(f"  Job ID: {data.get('id', 'N/A')}")
        print(f"  Printer: {data.get('printer_name', 'N/A')}")
        if 'metadata' in data:
            print(f"  Has metadata: Yes (doc_format: {data['metadata'].get('doc_format', 'N/A')})")

    ws_client.on_message("printer_test", on_message)
    ws_client.on_message("print_document", on_message)
    ws_client.on_message("*", lambda d: logger.debug(f"Raw message: {d}"))

    connected = {"value": False}
    def on_state(state):
        if state == ConnectionState.CONNECTED:
            connected["value"] = True
            print(f"  OK: WebSocket connected to channel: {channel}")

    ws_client.on_state_change(on_state)
    ws_client.connect()

    # Wait for connection
    for _ in range(20):
        if connected["value"]:
            break
        time.sleep(0.5)

    if not connected["value"]:
        print("  FAILED: WebSocket connection timeout")
        return 1

    # Step 5: Create test print job
    print("\n[Step 5] Creating test print job in Odoo...")
    time.sleep(1)  # Small delay to ensure connection is stable

    try:
        job_id = client.create('ylhc.print.job', {
            'name': f'Agent Test - {time.strftime("%H:%M:%S")}',
            'type': 'printer_test',
            'printer_id': printer_id,
            'status': 'pending',
            'is_test': True,
        })
        print(f"  OK: Created job id: {job_id}")

        # Trigger job processing
        print("\n[Step 6] Triggering job processing...")
        client.call('ylhc.print.job', 'action_process', [[job_id]])
        print("  OK: Job triggered!")

    except Exception as e:
        print(f"  ERROR: {e}")
        ws_client.disconnect()
        return 1

    # Step 7: Wait for message
    print("\n[Step 7] Waiting for message (30 seconds)...")
    print("  Listening on channel:", channel)

    start_time = time.time()
    while time.time() - start_time < 30:
        if message_received["count"] > 0:
            break
        time.sleep(1)
        remaining = int(30 - (time.time() - start_time))
        if remaining % 5 == 0 and remaining > 0:
            print(f"  ... waiting ({remaining}s remaining)")

    # Results
    print("\n" + "=" * 60)
    print("  TEST RESULTS")
    print("=" * 60)

    if message_received["count"] > 0:
        print(f"  [SUCCESS] Received {message_received['count']} message(s)!")
        print(f"  Communication between Odoo and Local Agent is WORKING!")
    else:
        print("  [NO MESSAGE] Did not receive message within 30 seconds")
        print("  This could mean:")
        print("    - The bus notification system is not configured correctly")
        print("    - The job processing didn't trigger a WebSocket message")
        print("    - There might be a channel name mismatch")

        # Check job status
        print("\n  Checking job status...")
        job = client.search_read(
            'ylhc.print.job',
            domain=[('id', '=', job_id)],
            fields=['name', 'status', 'channel_name', 'error_message']
        )
        if job:
            print(f"    Job status: {job[0]['status']}")
            print(f"    Channel: {job[0].get('channel_name', 'N/A')}")
            if job[0].get('error_message'):
                print(f"    Error: {job[0]['error_message']}")

    # Cleanup
    ws_client.disconnect()
    client.logout()

    print("\n" + "=" * 60)
    print("  Test Complete!")
    print("=" * 60)

    return 0 if message_received["count"] > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
