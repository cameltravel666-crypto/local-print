#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Check Odoo data - verify if Station and Printers were created
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from core.odoo_client import OdooClient

def main():
    # Connect to Odoo
    client = OdooClient("https://demo.nagashiro.top", "test001")

    print("Authenticating...")
    if not client.authenticate("test", "test"):
        print("Authentication failed!")
        return

    print(f"Authenticated as uid: {client.session.uid}\n")

    # Check Stations
    print("=" * 50)
    print("Checking Stations (ylhc.station)")
    print("=" * 50)
    try:
        stations = client.search_read(
            'ylhc.station',
            domain=[],
            fields=['name', 'code', 'location', 'is_active', 'printer_count', 'last_sync_time']
        )
        if stations:
            for s in stations:
                print(f"  - {s['name']} (code: {s['code']})")
                print(f"    Location: {s.get('location', 'N/A')}")
                print(f"    Active: {s['is_active']}, Printers: {s['printer_count']}")
                print(f"    Last Sync: {s.get('last_sync_time', 'Never')}")
                print()
        else:
            print("  No stations found!")
    except Exception as e:
        print(f"  Error: {e}")

    # Check Printers
    print("=" * 50)
    print("Checking Printers (ylhc.printer)")
    print("=" * 50)
    try:
        printers = client.search_read(
            'ylhc.printer',
            domain=[],
            fields=['name', 'station_id', 'status', 'is_default', 'service_sync']
        )
        if printers:
            for p in printers:
                station_name = p['station_id'][1] if p.get('station_id') else 'None'
                print(f"  - {p['name']} @ {station_name}")
                print(f"    Status: {p['status']}, Default: {p['is_default']}")
                print()
        else:
            print("  No printers found!")
    except Exception as e:
        print(f"  Error: {e}")

    # Check recent Print Jobs
    print("=" * 50)
    print("Checking Recent Print Jobs (ylhc.print.job)")
    print("=" * 50)
    try:
        jobs = client.search_read(
            'ylhc.print.job',
            domain=[],
            fields=['name', 'type', 'status', 'printer_name', 'station_code', 'create_date'],
            limit=10,
            order='create_date desc'
        )
        if jobs:
            for j in jobs:
                print(f"  - {j['name']}")
                print(f"    Type: {j['type']}, Status: {j['status']}")
                print(f"    Printer: {j.get('printer_name', 'N/A')}, Station: {j.get('station_code', 'N/A')}")
                print(f"    Created: {j['create_date']}")
                print()
        else:
            print("  No print jobs found!")
    except Exception as e:
        print(f"  Error: {e}")

    client.logout()
    print("\nDone!")


if __name__ == "__main__":
    main()
