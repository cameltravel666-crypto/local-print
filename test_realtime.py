#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Real-time test - Subscribe and immediately trigger job
"""

import sys
import json
import time
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

import websocket
from core.odoo_client import OdooClient


def main():
    server = "demo.nagashiro.top"
    database = "test001"
    machine_id = "MAC001"

    print("\n" + "=" * 60)
    print("  Real-time Communication Test")
    print("=" * 60)

    # Authenticate
    print("\n[1] Authenticating...")
    client = OdooClient(f"https://{server}", database)
    if not client.authenticate("test", "test"):
        print("  Auth failed!")
        return 1

    cookies = client.get_cookies()
    cookie_str = "; ".join([f"{k}={v}" for k, v in cookies.items()])
    print(f"  OK: Session established")

    # Get station and printer
    stations = client.search_read('ylhc.station', [('code', '=', machine_id)], ['id'])
    if not stations:
        print("  No station found!")
        return 1
    station_id = stations[0]['id']

    printers = client.search_read('ylhc.printer', [('station_id', '=', station_id)], ['id', 'name'])
    if not printers:
        print("  No printer found, creating one...")
        printer_id = client.create('ylhc.printer', {
            'name': 'TestPrinter',
            'station_id': station_id,
            'status': 'idle'
        })
    else:
        printer_id = printers[0]['id']
    print(f"  Using printer id: {printer_id}")

    # Setup WebSocket
    print("\n[2] Connecting WebSocket...")
    ws_url = f"wss://{server}/websocket"

    all_messages = []
    connected = threading.Event()

    def on_open(ws):
        print("  WebSocket connected!")
        connected.set()

        # Subscribe to ALL possible channel formats
        channels = [
            f"ylhc_service.{machine_id}",
            f"{database}:ylhc_service.{machine_id}",
            # Also subscribe to generic channels to see what's being sent
            f"res.partner",
            f"bus.bus/im_status",
        ]

        subscribe_msg = {
            "event_name": "subscribe",
            "data": {
                "channels": channels,
                "last": 0
            }
        }
        print(f"  Subscribing to channels...")
        ws.send(json.dumps(subscribe_msg))

    def on_message(ws, message):
        try:
            data = json.loads(message)
            all_messages.append(data)

            # Print only non-im_status messages
            if isinstance(data, list):
                for item in data:
                    msg_type = item.get('message', {}).get('type', '')
                    if 'im_status' not in msg_type:
                        print(f"\n  >>> MESSAGE: {json.dumps(item, indent=2)[:300]}")
            else:
                msg_type = data.get('type', data.get('message', {}).get('type', ''))
                if 'im_status' not in msg_type:
                    print(f"\n  >>> MESSAGE: {json.dumps(data, indent=2)[:300]}")

        except Exception as e:
            print(f"  Parse error: {e}")

    def on_error(ws, error):
        print(f"  WS Error: {error}")

    def on_close(ws, code, msg):
        print(f"  WS Closed: {code}")

    ws = websocket.WebSocketApp(
        ws_url,
        on_open=on_open,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close,
        cookie=cookie_str
    )

    # Run WebSocket in background
    ws_thread = threading.Thread(target=ws.run_forever, kwargs={'ping_interval': 30})
    ws_thread.daemon = True
    ws_thread.start()

    # Wait for connection
    if not connected.wait(timeout=10):
        print("  Connection timeout!")
        return 1

    time.sleep(2)

    # Create and trigger job
    print("\n[3] Creating and triggering print job...")
    job_id = client.create('ylhc.print.job', {
        'name': f'RT-Test-{time.strftime("%H%M%S")}',
        'type': 'printer_test',
        'printer_id': printer_id,
        'status': 'pending',
        'is_test': True,
    })
    print(f"  Created job: {job_id}")

    print("  Triggering job processing...")
    client.call('ylhc.print.job', 'action_process', [[job_id]])
    print("  Job triggered!")

    # Also try calling run_job directly
    print("  Calling run_job...")
    try:
        client.call('ylhc.print.job', 'run_job', [[job_id]])
    except Exception as e:
        print(f"  run_job error (may be expected): {e}")

    # Wait and collect messages
    print("\n[4] Listening for 15 seconds...")
    for i in range(15):
        time.sleep(1)
        if i % 5 == 4:
            print(f"  ... {i+1}s elapsed, {len(all_messages)} messages total")

    # Check job status
    print("\n[5] Final job status...")
    job = client.search_read('ylhc.print.job', [('id', '=', job_id)],
                             ['status', 'channel_name', 'error_message', 'job_data'])
    if job:
        print(f"  Status: {job[0]['status']}")
        print(f"  Channel: {job[0].get('channel_name', 'N/A')}")
        if job[0].get('error_message'):
            print(f"  Error: {job[0]['error_message']}")

    # Filter for ylhc messages
    print("\n[6] Message Analysis...")
    ylhc_messages = []
    for msg in all_messages:
        if isinstance(msg, list):
            for item in msg:
                msg_str = json.dumps(item)
                if 'ylhc' in msg_str.lower() or 'printer' in msg_str.lower():
                    ylhc_messages.append(item)
        else:
            msg_str = json.dumps(msg)
            if 'ylhc' in msg_str.lower() or 'printer' in msg_str.lower():
                ylhc_messages.append(msg)

    print(f"  Total messages: {len(all_messages)}")
    print(f"  YLHC/Printer related: {len(ylhc_messages)}")

    if ylhc_messages:
        print("\n  YLHC Messages found:")
        for m in ylhc_messages[:5]:
            print(f"    {json.dumps(m, indent=2)[:200]}")

    # Cleanup
    ws.close()
    client.logout()

    print("\n" + "=" * 60)
    success = len(ylhc_messages) > 0
    print(f"  Result: {'SUCCESS' if success else 'NO YLHC MESSAGES'}")
    print("=" * 60)

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
