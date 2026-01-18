#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Trigger a test POS print job in Odoo
This simulates what the POS frontend does when printing a receipt
"""

import sys
import json
import base64
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from core.odoo_client import OdooClient


def create_sample_escpos():
    """Create sample ESC/POS commands for a receipt"""
    commands = bytearray()

    # Initialize printer
    commands.extend(b'\x1B\x40')  # ESC @

    # Center alignment
    commands.extend(b'\x1B\x61\x01')  # ESC a 1

    # Title
    commands.extend(b'\x1B\x21\x30')  # Double width + height
    commands.extend("TEST RECEIPT\n".encode('utf-8'))
    commands.extend(b'\x1B\x21\x00')  # Normal

    # Separator
    commands.extend(b'\x1B\x61\x00')  # Left align
    commands.extend(("=" * 32 + "\n").encode('utf-8'))

    # Order details
    commands.extend(f"Date: {time.strftime('%Y-%m-%d %H:%M:%S')}\n".encode('utf-8'))
    commands.extend("Order: TEST-001\n".encode('utf-8'))
    commands.extend(("-" * 32 + "\n").encode('utf-8'))

    # Items
    items = [
        ("Coffee Latte", "1", "25.00"),
        ("Croissant", "2", "18.00"),
        ("Orange Juice", "1", "15.00"),
    ]

    for name, qty, price in items:
        line = f"{name:<20} x{qty:>2} {price:>7}\n"
        commands.extend(line.encode('utf-8'))

    # Total
    commands.extend(("-" * 32 + "\n").encode('utf-8'))
    commands.extend(b'\x1B\x21\x10')  # Double height
    commands.extend("TOTAL:              CNY 58.00\n".encode('utf-8'))
    commands.extend(b'\x1B\x21\x00')  # Normal

    # Footer
    commands.extend(("=" * 32 + "\n").encode('utf-8'))
    commands.extend(b'\x1B\x61\x01')  # Center
    commands.extend("Thank you for your order!\n".encode('utf-8'))
    commands.extend("www.example.com\n".encode('utf-8'))

    # Feed and cut
    commands.extend(b'\x1B\x64\x05')  # Feed 5 lines
    commands.extend(b'\x1D\x56\x00')  # Full cut

    return bytes(commands)


def create_kitchen_ticket_escpos():
    """Create sample ESC/POS commands for a kitchen ticket"""
    commands = bytearray()

    # Initialize
    commands.extend(b'\x1B\x40')

    # Large font for kitchen
    commands.extend(b'\x1B\x21\x30')  # Double width + height

    # Header
    commands.extend(b'\x1B\x61\x01')  # Center
    commands.extend("KITCHEN ORDER\n".encode('utf-8'))
    commands.extend(b'\x1B\x61\x00')  # Left

    commands.extend(b'\x1B\x21\x00')  # Normal
    commands.extend(("=" * 32 + "\n").encode('utf-8'))

    # Order info
    commands.extend(f"Time: {time.strftime('%H:%M:%S')}\n".encode('utf-8'))
    commands.extend("Table: A5\n".encode('utf-8'))
    commands.extend("Order: K-001\n".encode('utf-8'))
    commands.extend(("-" * 32 + "\n").encode('utf-8'))

    # Items with large font
    commands.extend(b'\x1B\x21\x10')  # Double height
    items = [
        ("1x Beef Steak", "Medium"),
        ("2x French Fries", "No salt"),
        ("1x Caesar Salad", ""),
    ]

    for item, note in items:
        commands.extend(f"{item}\n".encode('utf-8'))
        if note:
            commands.extend(b'\x1B\x21\x00')
            commands.extend(f"   Note: {note}\n".encode('utf-8'))
            commands.extend(b'\x1B\x21\x10')

    commands.extend(b'\x1B\x21\x00')
    commands.extend(("=" * 32 + "\n").encode('utf-8'))

    # Feed and cut
    commands.extend(b'\x1B\x64\x05')
    commands.extend(b'\x1D\x56\x00')

    return bytes(commands)


def main():
    server_url = "https://demo.nagashiro.top"
    database = "test001"
    username = "test"
    password = "test"
    machine_id = "MAC001"

    print("\n" + "=" * 60)
    print("  Trigger Test POS Print Job")
    print("=" * 60)

    # Choose test type
    print("\nSelect test type:")
    print("  1. POS Receipt")
    print("  2. Kitchen Ticket")
    print("  3. Both")

    choice = input("\nEnter choice (1-3) [1]: ").strip() or "1"

    # Authenticate
    print("\n[1] Authenticating...")
    client = OdooClient(server_url, database)
    if not client.authenticate(username, password):
        print("  FAILED!")
        return 1
    print(f"  OK: uid {client.session.uid}")

    # Get station and printer
    print("\n[2] Getting printer...")
    stations = client.search_read('ylhc.station', [('code', '=', machine_id)], ['id'])
    if not stations:
        print(f"  No station found with code {machine_id}")
        return 1

    printers = client.search_read('ylhc.printer',
        [('station_id', '=', stations[0]['id'])],
        ['id', 'name'])
    if not printers:
        print("  No printer found, using TestPrinter")
        printer_id = None
        printer_name = "TestPrinter"
    else:
        printer_id = printers[0]['id']
        printer_name = printers[0]['name']
    print(f"  Using printer: {printer_name}")

    # Create test jobs
    jobs_created = []

    if choice in ['1', '3']:
        print("\n[3] Creating POS Receipt job...")
        escpos_data = create_sample_escpos()
        metadata = {
            "source": "test_script",
            "action": "print_receipt",
            "escpos_commands": base64.b64encode(escpos_data).decode('utf-8')
        }

        job_data = {
            'name': f'Test POS Receipt - {time.strftime("%H:%M:%S")}',
            'type': 'pos_receipt_print',
            'printer_id': printer_id,
            'status': 'pending',
            'metadata': json.dumps(metadata),
            'format': 'txt',  # ESC/POS data is in metadata
        }

        job_id = client.create('ylhc.print.job', job_data)
        print(f"  Created job: {job_id}")
        jobs_created.append(('receipt', job_id))

    if choice in ['2', '3']:
        print("\n[4] Creating Kitchen Ticket job...")
        escpos_data = create_kitchen_ticket_escpos()
        metadata = {
            "source": "test_script",
            "print_type": "kitchen_ticket",
            "escpos_commands": base64.b64encode(escpos_data).decode('utf-8')
        }

        job_data = {
            'name': f'Test Kitchen Ticket - {time.strftime("%H:%M:%S")}',
            'type': 'pos_receipt_print',
            'printer_id': printer_id,
            'status': 'pending',
            'metadata': json.dumps(metadata),
            'format': 'txt',  # ESC/POS data is in metadata
        }

        job_id = client.create('ylhc.print.job', job_data)
        print(f"  Created job: {job_id}")
        jobs_created.append(('kitchen', job_id))

    # Trigger processing
    print("\n[5] Triggering job processing...")
    for job_type, job_id in jobs_created:
        try:
            client.call('ylhc.print.job', 'action_process', [[job_id]])
            print(f"  Triggered {job_type} job: {job_id}")
        except Exception as e:
            print(f"  Error triggering {job_type}: {e}")

    # Check status
    print("\n[6] Checking job status...")
    time.sleep(2)
    for job_type, job_id in jobs_created:
        job = client.search_read('ylhc.print.job', [('id', '=', job_id)],
                                ['name', 'status', 'error_message'])
        if job:
            print(f"  {job_type}: {job[0]['status']}")
            if job[0].get('error_message'):
                print(f"    Error: {job[0]['error_message']}")

    client.logout()

    print("\n" + "=" * 60)
    print("  Jobs created and triggered!")
    print("  If test_pos_print.py is running, it should receive these jobs.")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
