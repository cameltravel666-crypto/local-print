#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test different bus subscription formats
"""

import sys
import json
import time
import logging
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

import websocket

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


def test_subscription(server_url, cookies, channels, database):
    """Test WebSocket subscription with specific channel format"""

    ws_url = f"wss://{server_url}/websocket"
    cookie_str = "; ".join([f"{k}={v}" for k, v in cookies.items()])

    messages = []
    connected = threading.Event()
    closed = threading.Event()

    def on_open(ws):
        print(f"  Connected!")
        connected.set()

        # Try subscribing
        # Odoo 18 format might need database prefix
        subscribe_msg = {
            "event_name": "subscribe",
            "data": {
                "channels": channels,
                "last": 0
            }
        }
        print(f"  Subscribing to: {channels}")
        ws.send(json.dumps(subscribe_msg))

    def on_message(ws, message):
        print(f"  Received: {message[:200]}...")
        messages.append(message)

    def on_error(ws, error):
        print(f"  Error: {error}")

    def on_close(ws, code, msg):
        print(f"  Closed: {code} - {msg}")
        closed.set()

    ws = websocket.WebSocketApp(
        ws_url,
        on_open=on_open,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close,
        cookie=cookie_str
    )

    # Run in background
    thread = threading.Thread(target=ws.run_forever, kwargs={'ping_interval': 30})
    thread.daemon = True
    thread.start()

    # Wait for connection
    connected.wait(timeout=10)
    if not connected.is_set():
        print("  Connection timeout!")
        return False, messages

    # Wait a bit for any immediate messages
    time.sleep(2)

    # Keep connection for the caller
    return ws, messages


def main():
    from core.odoo_client import OdooClient

    server = "demo.nagashiro.top"
    database = "test001"
    machine_id = "MAC001"

    print("\n" + "=" * 60)
    print("  Testing Bus Subscription Formats")
    print("=" * 60)

    # Authenticate first
    print("\nAuthenticating...")
    client = OdooClient(f"https://{server}", database)
    if not client.authenticate("test", "test"):
        print("Auth failed!")
        return

    cookies = client.get_cookies()
    print(f"Got session: {cookies.get('session_id', 'N/A')[:20]}...")

    # Test different channel formats
    channel_formats = [
        # Format 1: Simple string
        [f"ylhc_service.{machine_id}"],

        # Format 2: With database prefix
        [f"{database}:ylhc_service.{machine_id}"],

        # Format 3: Tuple format (model, res_id)
        [("ylhc.station", machine_id)],

        # Format 4: Dict format
        [{"name": f"ylhc_service.{machine_id}"}],
    ]

    for i, channels in enumerate(channel_formats):
        print(f"\n--- Test {i+1}: {channels} ---")
        try:
            ws, messages = test_subscription(server, cookies, channels, database)
            if ws:
                print(f"  Subscription sent, waiting 5s for response...")
                time.sleep(5)
                print(f"  Received {len(messages)} messages")
                if messages:
                    for m in messages[:3]:
                        print(f"    - {m[:100]}...")
                ws.close()
                time.sleep(1)
        except Exception as e:
            print(f"  Error: {e}")

    # Now trigger a job and listen
    print("\n\n--- Final Test: Subscribe and Trigger Job ---")

    # Use the simple format but let's see what the actual Odoo bus.bus contains
    print("\nChecking bus.bus for existing messages...")
    try:
        bus_messages = client.search_read(
            'bus.bus',
            domain=[('channel', 'ilike', 'ylhc')],
            fields=['id', 'channel', 'message', 'create_date'],
            limit=5,
            order='id desc'
        )
        if bus_messages:
            print("Recent bus messages:")
            for bm in bus_messages:
                print(f"  Channel: {bm['channel']}")
                print(f"  Message: {bm['message'][:100]}...")
                print(f"  Created: {bm['create_date']}")
                print()
        else:
            print("  No bus messages found with 'ylhc' in channel")
    except Exception as e:
        print(f"  Error reading bus.bus: {e}")

    client.logout()
    print("\nDone!")


if __name__ == "__main__":
    main()
