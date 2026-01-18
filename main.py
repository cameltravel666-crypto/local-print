#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Local Print Agent
Main entry point
"""

import sys
import logging
import argparse
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))


def setup_logging(level: str = "INFO"):
    """Setup logging configuration"""
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Reduce noise from third-party libraries
    logging.getLogger("websocket").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)


def run_gui():
    """Run GUI application"""
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtCore import Qt
    from src.gui.main_window import MainWindow

    # Enable high DPI scaling
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("Local Print Agent")
    app.setOrganizationName("LocalPrintAgent")

    # Create and show main window
    window = MainWindow()
    window.show()

    sys.exit(app.exec())


def run_headless():
    """Run in headless mode (no GUI)"""
    import time
    import signal
    from src.core.print_service import PrintService, ServiceState
    from src.utils.config import get_config

    config = get_config()

    # Create service
    service = PrintService(
        machine_name=config.settings.machine_name or "Local Print Agent",
        machine_id=config.settings.machine_id,
        location_tag=config.settings.station_tag,
    )

    # Add servers
    for server_id, server in config.get_enabled_servers().items():
        service.add_server(
            server_id=server.server_id,
            server_name=server.server_name,
            server_url=server.server_url,
            database=server.database,
            username=server.username,
            password=server.password,
            http_port=server.http_port,
            websocket_port=server.websocket_port,
        )

    # Handle shutdown signal
    running = True

    def signal_handler(sig, frame):
        nonlocal running
        print("\nShutting down...")
        running = False

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Start service
    print("Starting print service...")
    if service.start():
        print("Print service started. Press Ctrl+C to stop.")

        # Keep running
        while running:
            time.sleep(1)

        service.stop()
        print("Print service stopped.")
    else:
        print("Failed to start print service.")
        sys.exit(1)


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Local Print Agent - Print proxy for Odoo"
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run in headless mode (no GUI)"
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Logging level"
    )

    args = parser.parse_args()

    setup_logging(args.log_level)

    if args.headless:
        run_headless()
    else:
        run_gui()


if __name__ == "__main__":
    main()
