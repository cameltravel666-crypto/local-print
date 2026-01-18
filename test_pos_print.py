#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Seisei Print Agent - POS Receipt and Kitchen Ticket Print Test
Receives print jobs via WebSocket and outputs to PDF

Developed by Seisei
"""

import sys
import json
import time
import base64
import os
import threading
import logging
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent / "src"))

from core.odoo_client import OdooClient
from core.websocket_client import OdooWebSocketClient, WebSocketConfig, ConnectionState
from utils.escpos_parser import parse_escpos, raster_to_pdf, raster_to_png

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Output directory for PDFs
OUTPUT_DIR = Path(__file__).parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)


def escpos_to_text(escpos_data: bytes) -> str:
    """
    Convert ESC/POS commands to readable text
    This is a simplified parser that extracts text content
    """
    result = []
    i = 0
    current_line = ""

    while i < len(escpos_data):
        byte = escpos_data[i]

        # ESC commands (0x1B)
        if byte == 0x1B:
            if i + 1 < len(escpos_data):
                cmd = escpos_data[i + 1]
                if cmd == ord('@'):  # Initialize
                    i += 2
                    continue
                elif cmd == ord('a'):  # Alignment
                    i += 3
                    continue
                elif cmd == ord('!'):  # Print mode
                    i += 3
                    continue
                elif cmd == ord('d'):  # Print and feed n lines
                    if current_line:
                        result.append(current_line)
                        current_line = ""
                    i += 3
                    continue
                elif cmd == ord('v'):  # Raster image
                    # Skip image data
                    if i + 5 < len(escpos_data):
                        xL = escpos_data[i + 3]
                        xH = escpos_data[i + 4]
                        yL = escpos_data[i + 5]
                        yH = escpos_data[i + 6]
                        width = xL + xH * 256
                        height = yL + yH * 256
                        image_size = width * height
                        result.append(f"[IMAGE {width}x{height}]")
                        i += 7 + image_size
                        continue
            i += 1
            continue

        # GS commands (0x1D)
        elif byte == 0x1D:
            if i + 1 < len(escpos_data):
                cmd = escpos_data[i + 1]
                if cmd == ord('v'):  # Raster bit image
                    if i + 7 < len(escpos_data):
                        m = escpos_data[i + 2]
                        xL = escpos_data[i + 3]
                        xH = escpos_data[i + 4]
                        yL = escpos_data[i + 5]
                        yH = escpos_data[i + 6]
                        width = xL + xH * 256
                        height = yL + yH * 256
                        image_size = width * height
                        result.append(f"[RASTER IMAGE {width*8}x{height}]")
                        i += 7 + image_size
                        continue
            i += 1
            continue

        # Line feed
        elif byte == 0x0A:
            if current_line:
                result.append(current_line)
            else:
                result.append("")
            current_line = ""
            i += 1
            continue

        # Carriage return
        elif byte == 0x0D:
            i += 1
            continue

        # Printable characters
        elif 0x20 <= byte <= 0x7E:
            current_line += chr(byte)
            i += 1
            continue

        # Skip other control characters
        else:
            i += 1
            continue

    if current_line:
        result.append(current_line)

    return "\n".join(result)


def save_as_text_pdf(content: str, filename: str):
    """Save text content as a simple text file (PDF conversion requires reportlab)"""
    filepath = OUTPUT_DIR / f"{filename}.txt"
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"  Saved: {filepath}")
    return filepath


def save_raw_data(data: bytes, filename: str, ext: str = "bin"):
    """Save raw binary data"""
    filepath = OUTPUT_DIR / f"{filename}.{ext}"
    with open(filepath, 'wb') as f:
        f.write(data)
    print(f"  Saved raw: {filepath}")
    return filepath


def create_pdf_from_text(text_content: str, filename: str):
    """Create PDF from text content using macOS textutil or basic method"""
    txt_path = OUTPUT_DIR / f"{filename}.txt"
    pdf_path = OUTPUT_DIR / f"{filename}.pdf"

    # Save text first
    with open(txt_path, 'w', encoding='utf-8') as f:
        f.write(text_content)

    # Try to convert to PDF using cupsfilter or textutil
    import subprocess

    # Method 1: Using cupsfilter (if available)
    try:
        result = subprocess.run(
            ['cupsfilter', '-m', 'application/pdf', str(txt_path)],
            capture_output=True,
            timeout=30
        )
        if result.returncode == 0 and result.stdout:
            with open(pdf_path, 'wb') as f:
                f.write(result.stdout)
            print(f"  PDF created: {pdf_path}")
            return pdf_path
    except Exception as e:
        pass

    # Method 2: Using enscript + ps2pdf
    try:
        ps_path = OUTPUT_DIR / f"{filename}.ps"
        subprocess.run(['enscript', '-p', str(ps_path), str(txt_path)],
                      capture_output=True, timeout=30)
        subprocess.run(['ps2pdf', str(ps_path), str(pdf_path)],
                      capture_output=True, timeout=30)
        if pdf_path.exists():
            print(f"  PDF created: {pdf_path}")
            return pdf_path
    except Exception:
        pass

    print(f"  Text saved (PDF conversion not available): {txt_path}")
    return txt_path


def print_to_cups_pdf(filepath: Path, printer_name: str = None):
    """Print file to CUPS PDF printer or default printer"""
    import subprocess

    # Check for virtual PDF printer
    result = subprocess.run(['lpstat', '-e'], capture_output=True, text=True)
    printers = result.stdout.strip().split('\n') if result.stdout else []

    # Look for PDF printer
    pdf_printer = None
    for p in printers:
        if 'pdf' in p.lower():
            pdf_printer = p
            break

    if pdf_printer:
        print(f"  Printing to virtual PDF printer: {pdf_printer}")
        subprocess.run(['lp', '-d', pdf_printer, str(filepath)], capture_output=True)
    else:
        print(f"  No virtual PDF printer found. File saved at: {filepath}")


class POSPrintHandler:
    """Handler for POS print messages"""

    def __init__(self):
        self.jobs_received = 0
        self.jobs_processed = 0

    def handle_print_document(self, payload: dict):
        """Handle print_document message"""
        self.jobs_received += 1
        job_id = payload.get('id', 'unknown')
        printer_name = payload.get('printer_name', 'unknown')
        job_type = payload.get('type', 'unknown')

        print(f"\n{'='*60}")
        print(f"  RECEIVED PRINT JOB #{self.jobs_received}")
        print(f"{'='*60}")
        print(f"  Job ID: {job_id}")
        print(f"  Type: {job_type}")
        print(f"  Printer: {printer_name}")

        self._process_job(payload, job_id)

    def handle_pos_receipt(self, payload: dict):
        """Handle pos_receipt_print message (alias)"""
        self.handle_print_document(payload)

    def handle_kitchen_order(self, payload: dict):
        """Handle kitchen_order message"""
        self.jobs_received += 1
        job_id = payload.get('id', 'unknown')

        print(f"\n{'='*60}")
        print(f"  RECEIVED KITCHEN ORDER #{self.jobs_received}")
        print(f"{'='*60}")
        print(f"  Job ID: {job_id}")

        self._process_job(payload, job_id)

    def _process_job(self, payload: dict, job_id: str):
        """Process the print job"""
        metadata = payload.get('metadata', {})
        if isinstance(metadata, str):
            try:
                metadata = json.loads(metadata)
            except:
                metadata = {}

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"print_{timestamp}_{job_id[:8]}"

        # Check for ESC/POS commands
        if 'escpos_commands' in metadata:
            print(f"  Format: ESC/POS commands")
            try:
                escpos_data = base64.b64decode(metadata['escpos_commands'])
                print(f"  Data size: {len(escpos_data)} bytes")

                # Save raw ESC/POS data
                save_raw_data(escpos_data, f"{filename}_escpos", "bin")

                # Parse ESC/POS data using improved parser
                text_content, images = parse_escpos(escpos_data)

                # If we have images (raster data), create PDF from images
                if images:
                    print(f"  Found {len(images)} raster image(s)")
                    for i, img in enumerate(images):
                        print(f"    Image {i+1}: {img.width}x{img.height} pixels")

                    pdf_path = OUTPUT_DIR / f"{filename}.pdf"
                    if raster_to_pdf(images, str(pdf_path)):
                        print(f"  PDF created: {pdf_path}")
                        self.jobs_processed += 1
                    else:
                        print(f"  Failed to create PDF from images")

                # If we have text content, also save it
                elif text_content.strip():
                    print(f"\n  --- Extracted Text Content ---")
                    for line in text_content.split('\n')[:20]:
                        print(f"  | {line}")
                    if text_content.count('\n') > 20:
                        print(f"  | ... ({text_content.count(chr(10))} lines total)")
                    print(f"  --- End of Preview ---\n")

                    # Create PDF from text
                    create_pdf_from_text(text_content, filename)
                    self.jobs_processed += 1
                else:
                    print(f"  No printable content extracted")

            except Exception as e:
                print(f"  Error processing ESC/POS: {e}")
                import traceback
                traceback.print_exc()

        # Check for PDF content
        elif 'content' in payload or 'pdf_content' in payload or 'document' in payload:
            content = payload.get('content') or payload.get('pdf_content') or payload.get('document')
            if content:
                print(f"  Format: PDF/Document")
                try:
                    pdf_data = base64.b64decode(content)
                    if pdf_data[:4] == b'%PDF':
                        pdf_path = save_raw_data(pdf_data, filename, "pdf")
                        print(f"  PDF saved: {pdf_path}")
                        self.jobs_processed += 1
                    else:
                        save_raw_data(pdf_data, filename, "bin")
                except Exception as e:
                    print(f"  Error processing content: {e}")

        else:
            print(f"  No printable content found in payload")
            print(f"  Payload keys: {list(payload.keys())}")
            # Save payload for debugging
            with open(OUTPUT_DIR / f"{filename}_payload.json", 'w') as f:
                json.dump(payload, f, indent=2, default=str)


def main():
    server_url = "https://demo.nagashiro.top"
    database = "test001"
    username = "test"
    password = "test"
    machine_id = "MAC001"

    print("\n" + "=" * 60)
    print("  POS Receipt & Kitchen Ticket Print Test")
    print("=" * 60)
    print(f"  Output directory: {OUTPUT_DIR}")

    # Authenticate
    print("\n[1] Authenticating with Odoo...")
    client = OdooClient(server_url, database)
    if not client.authenticate(username, password):
        print("  FAILED: Authentication failed!")
        return 1
    print(f"  OK: Authenticated as uid {client.session.uid}")

    # Get station info
    print("\n[2] Getting station info...")
    stations = client.search_read('seisei.station', [('code', '=', machine_id)], ['id', 'name'])
    if not stations:
        print(f"  No station found with code {machine_id}")
        return 1
    print(f"  Station: {stations[0]['name']} (id: {stations[0]['id']})")

    # Setup WebSocket
    print("\n[3] Connecting WebSocket...")
    channel = f"seisei_service.{machine_id}"

    ws_config = WebSocketConfig(
        url="wss://demo.nagashiro.top/websocket",
        channels=[channel],
        cookies=client.get_cookies(),
        reconnect_interval=5,
        max_reconnect_attempts=3,
    )

    ws_client = OdooWebSocketClient(ws_config)
    handler = POSPrintHandler()

    # Register handlers for different message types
    ws_client.on_message("print_document", handler.handle_print_document)
    ws_client.on_message("pos_receipt_print", handler.handle_pos_receipt)
    ws_client.on_message("kitchen_order", handler.handle_kitchen_order)
    ws_client.on_message("printer_test", handler.handle_print_document)

    # Wildcard handler to see all messages
    def on_any_message(payload):
        msg_type = payload.get('type', 'unknown')
        print(f"  [DEBUG] Message type: {msg_type}")
    ws_client.on_message("*", on_any_message)

    connected = threading.Event()
    def on_state(state):
        if state == ConnectionState.CONNECTED:
            connected.set()
            print(f"  OK: Connected to channel: {channel}")
        elif state == ConnectionState.DISCONNECTED:
            print(f"  WebSocket disconnected")
        elif state == ConnectionState.ERROR:
            print(f"  WebSocket error")

    ws_client.on_state_change(on_state)
    ws_client.connect()

    # Wait for connection
    if not connected.wait(timeout=15):
        print("  FAILED: Connection timeout")
        return 1

    # Listen for messages
    print("\n[4] Listening for print jobs...")
    print("    - POS Receipt (pos_receipt_print)")
    print("    - Kitchen Ticket (kitchen_order)")
    print("    - Print Document (print_document)")
    print("\n" + "-" * 60)
    print("  Waiting for print jobs from Odoo POS...")
    print("  Press Ctrl+C to stop")
    print("-" * 60)

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\nStopping...")

    # Summary
    print("\n" + "=" * 60)
    print("  SUMMARY")
    print("=" * 60)
    print(f"  Jobs received: {handler.jobs_received}")
    print(f"  Jobs processed: {handler.jobs_processed}")
    print(f"  Output directory: {OUTPUT_DIR}")

    # Cleanup
    ws_client.disconnect()
    client.logout()

    return 0


if __name__ == "__main__":
    sys.exit(main())
