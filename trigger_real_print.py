#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Trigger Real Print Jobs from Odoo
Uses actual ESC/POS data from existing print jobs
"""

import sys
import json
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from core.odoo_client import OdooClient


def main():
    server_url = "https://demo.nagashiro.top"
    database = "test001"
    username = "test"
    password = "test"
    machine_id = "MAC001"

    print("\n" + "=" * 60)
    print("  Trigger Real Print Jobs (Using Actual Templates)")
    print("=" * 60)

    # Authenticate
    print("\n[1] Authenticating...")
    client = OdooClient(server_url, database)
    if not client.authenticate(username, password):
        print("  FAILED!")
        return 1
    print(f"  OK: uid {client.session.uid}")

    # Get station and printer for our test machine
    print("\n[2] Getting test station and printer...")
    stations = client.search_read('seisei.station', [('code', '=', machine_id)], ['id', 'name'])
    if not stations:
        print(f"  No station found with code {machine_id}")
        return 1
    station_id = stations[0]['id']
    print(f"  Station: {stations[0]['name']} (id: {station_id})")

    printers = client.search_read('seisei.printer',
        [('station_id', '=', station_id)],
        ['id', 'name'])
    if not printers:
        print("  No printer found")
        return 1
    printer_id = printers[0]['id']
    printer_name = printers[0]['name']
    print(f"  Printer: {printer_name} (id: {printer_id})")

    # Find real print jobs to copy
    print("\n[3] Finding real print jobs to use as templates...")

    # Find a real POS receipt
    pos_jobs = client.search_read('seisei.print.job',
        [('type', '=', 'pos_receipt_print'), ('metadata', 'ilike', 'pos_frontend')],
        ['name', 'metadata'],
        limit=1, order='id desc')

    # Find a real kitchen ticket
    kitchen_jobs = client.search_read('seisei.print.job',
        [('name', 'ilike', '厨房')],
        ['name', 'metadata'],
        limit=1, order='id desc')

    print(f"  Found {len(pos_jobs)} POS receipt template(s)")
    print(f"  Found {len(kitchen_jobs)} kitchen ticket template(s)")

    # Choose what to send
    print("\nSelect job type to trigger:")
    print("  1. POS Receipt (real template)")
    print("  2. Kitchen Ticket (real template)")
    print("  3. Both")

    choice = input("\nEnter choice (1-3) [3]: ").strip() or "3"

    jobs_created = []

    if choice in ['1', '3'] and pos_jobs:
        print("\n[4] Creating POS Receipt job...")
        original = pos_jobs[0]
        print(f"  Using template from: {original['name']}")

        job_data = {
            'name': f'Real POS Receipt - {time.strftime("%H:%M:%S")}',
            'type': 'pos_receipt_print',
            'printer_id': printer_id,
            'status': 'pending',
            'metadata': original['metadata'],  # Use real metadata
            'format': 'txt',
        }

        job_id = client.create('seisei.print.job', job_data)
        print(f"  Created job: {job_id}")
        jobs_created.append(('POS Receipt', job_id))

    if choice in ['2', '3'] and kitchen_jobs:
        print("\n[5] Creating Kitchen Ticket job...")
        original = kitchen_jobs[0]
        print(f"  Using template from: {original['name']}")

        job_data = {
            'name': f'Real Kitchen Ticket - {time.strftime("%H:%M:%S")}',
            'type': 'pos_receipt_print',
            'printer_id': printer_id,
            'status': 'pending',
            'metadata': original['metadata'],  # Use real metadata
            'format': 'txt',
        }

        job_id = client.create('seisei.print.job', job_data)
        print(f"  Created job: {job_id}")
        jobs_created.append(('Kitchen Ticket', job_id))

    if not jobs_created:
        print("\n  No jobs created (no templates available)")
        client.logout()
        return 1

    # Trigger processing
    print("\n[6] Triggering job processing...")
    for job_type, job_id in jobs_created:
        try:
            client.call('seisei.print.job', 'action_process', [[job_id]])
            print(f"  Triggered {job_type}: {job_id}")
        except Exception as e:
            print(f"  Error triggering {job_type}: {e}")

    # Wait and check status
    print("\n[7] Checking job status...")
    time.sleep(3)
    for job_type, job_id in jobs_created:
        job = client.search_read('seisei.print.job', [('id', '=', job_id)],
                                ['name', 'status', 'error_message'])
        if job:
            status = job[0]['status']
            print(f"  {job_type}: {status}")
            if job[0].get('error_message'):
                print(f"    Error: {job[0]['error_message']}")

    client.logout()

    print("\n" + "=" * 60)
    print("  Jobs triggered!")
    print("  Run test_pos_print.py to receive and process them.")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
