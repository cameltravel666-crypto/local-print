# -*- coding: utf-8 -*-
"""
Seisei Print Agent - Printer Manager
Handles local printer discovery, status monitoring, and print execution

Developed by Seisei
"""

import os
import sys
import json
import base64
import logging
import tempfile
import subprocess
import platform
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict
from pathlib import Path
from enum import Enum

logger = logging.getLogger(__name__)


class PrinterStatus(Enum):
    """Printer status enumeration"""
    IDLE = "idle"
    PRINTING = "printing"
    ERROR = "error"
    OFFLINE = "offline"
    UNKNOWN = "unknown"


@dataclass
class PrinterInfo:
    """Local printer information"""
    name: str
    system_name: str = ""
    is_default: bool = False
    status: str = "unknown"
    status_message: str = ""
    manufacturer: str = ""
    model: str = ""
    location: str = ""
    description: str = ""
    supported_formats: List[str] = field(default_factory=lambda: ["pdf", "txt"])
    capabilities: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        """Convert to dictionary for sync"""
        return asdict(self)


@dataclass
class PrintJob:
    """Print job information"""
    job_id: str
    printer_name: str
    document_data: bytes
    document_format: str = "pdf"
    copies: int = 1
    priority: int = 0
    paper_format: Dict = field(default_factory=dict)
    print_options: Dict = field(default_factory=dict)


class PrinterManager:
    """
    Manages local printers and print operations

    Supports:
    - Windows: win32print API
    - Linux: CUPS
    - macOS: CUPS/lp command
    """

    def __init__(self):
        self.system = platform.system().lower()
        self._printers: Dict[str, PrinterInfo] = {}
        self._ghostscript_path: Optional[str] = None
        self._sumatra_path: Optional[str] = None

        # Initialize platform-specific printer access
        self._init_platform()

    def _init_platform(self):
        """Initialize platform-specific printer access"""
        if self.system == 'windows':
            try:
                import win32print
                self._win32print = win32print
            except ImportError:
                logger.warning("win32print not available, limited printer support")
                self._win32print = None
        elif self.system in ['linux', 'darwin']:
            # Check for CUPS
            try:
                result = subprocess.run(['lpstat', '-v'], capture_output=True, timeout=5)
                self._cups_available = result.returncode == 0
            except Exception:
                self._cups_available = False
                logger.warning("CUPS not available")

    def set_ghostscript_path(self, path: str):
        """Set path to GhostScript executable"""
        if os.path.exists(path):
            self._ghostscript_path = path

    def set_sumatra_path(self, path: str):
        """Set path to SumatraPDF executable"""
        if os.path.exists(path):
            self._sumatra_path = path

    def discover_printers(self) -> List[PrinterInfo]:
        """
        Discover all available local printers

        Returns:
            List of PrinterInfo objects
        """
        self._printers.clear()

        if self.system == 'windows':
            printers = self._discover_windows_printers()
        elif self.system == 'darwin':
            printers = self._discover_macos_printers()
        else:
            printers = self._discover_linux_printers()

        for printer in printers:
            self._printers[printer.name] = printer

        logger.info(f"Discovered {len(printers)} printers")
        return printers

    def _discover_windows_printers(self) -> List[PrinterInfo]:
        """Discover printers on Windows"""
        printers = []

        if self._win32print:
            try:
                # Get default printer
                default_printer = self._win32print.GetDefaultPrinter()

                # Enumerate printers
                flags = 2  # PRINTER_ENUM_LOCAL
                level = 2
                printer_list = self._win32print.EnumPrinters(flags, None, level)

                for p in printer_list:
                    printer_name = p['pPrinterName']
                    printer = PrinterInfo(
                        name=printer_name,
                        system_name=printer_name,
                        is_default=(printer_name == default_printer),
                        status=self._parse_windows_status(p.get('Status', 0)),
                        location=p.get('pLocation', ''),
                        description=p.get('pComment', ''),
                    )
                    printers.append(printer)

            except Exception as e:
                logger.error(f"Error discovering Windows printers: {e}")

        return printers

    def _parse_windows_status(self, status_code: int) -> str:
        """Parse Windows printer status code"""
        if status_code == 0:
            return PrinterStatus.IDLE.value
        elif status_code & 0x00000001:  # PRINTER_STATUS_PAUSED
            return PrinterStatus.ERROR.value
        elif status_code & 0x00000002:  # PRINTER_STATUS_ERROR
            return PrinterStatus.ERROR.value
        elif status_code & 0x00000400:  # PRINTER_STATUS_OFFLINE
            return PrinterStatus.OFFLINE.value
        elif status_code & 0x00000800:  # PRINTER_STATUS_PRINTING
            return PrinterStatus.PRINTING.value
        return PrinterStatus.UNKNOWN.value

    def _discover_macos_printers(self) -> List[PrinterInfo]:
        """Discover printers on macOS"""
        printers = []

        try:
            # Get default printer
            result = subprocess.run(
                ['lpstat', '-d'],
                capture_output=True,
                text=True,
                timeout=10
            )
            default_printer = ""
            if result.returncode == 0 and result.stdout:
                # Format: "system default destination: PrinterName"
                # Or Chinese: "系统默认目标: PrinterName"
                parts = result.stdout.strip().split(':')
                if len(parts) >= 2:
                    default_printer = parts[1].strip()

            # List all printers using lpstat -e (simpler format, just names)
            result = subprocess.run(
                ['lpstat', '-e'],
                capture_output=True,
                text=True,
                timeout=10
            )

            printer_names = []
            if result.returncode == 0 and result.stdout:
                printer_names = [n.strip() for n in result.stdout.strip().split('\n') if n.strip()]

            # Get status for each printer
            result = subprocess.run(
                ['lpstat', '-p'],
                capture_output=True,
                text=True,
                timeout=10
            )

            status_lines = {}
            if result.returncode == 0:
                for line in result.stdout.strip().split('\n'):
                    # Handle both English and Chinese output
                    # English: "printer PrinterName is idle. ..."
                    # Chinese: "打印机PrinterName闲置，启用时间..."
                    for pname in printer_names:
                        if pname in line:
                            status_lines[pname] = line
                            break

            for printer_name in printer_names:
                status = PrinterStatus.IDLE.value
                line = status_lines.get(printer_name, '')

                # Check status keywords in both English and Chinese
                line_lower = line.lower()
                if 'disabled' in line_lower or '已停用' in line or '禁用' in line:
                    status = PrinterStatus.OFFLINE.value
                elif 'error' in line_lower or '错误' in line:
                    status = PrinterStatus.ERROR.value
                elif 'idle' in line_lower or '闲置' in line:
                    status = PrinterStatus.IDLE.value

                printer = PrinterInfo(
                    name=printer_name,
                    system_name=printer_name,
                    is_default=(printer_name == default_printer),
                    status=status,
                )
                printers.append(printer)

        except Exception as e:
            logger.error(f"Error discovering macOS printers: {e}")

        return printers

    def _discover_linux_printers(self) -> List[PrinterInfo]:
        """Discover printers on Linux"""
        # Similar to macOS, uses CUPS
        return self._discover_macos_printers()

    def get_printer(self, name: str) -> Optional[PrinterInfo]:
        """Get printer by name"""
        return self._printers.get(name)

    def get_all_printers(self) -> List[PrinterInfo]:
        """Get all discovered printers"""
        return list(self._printers.values())

    def get_default_printer(self) -> Optional[PrinterInfo]:
        """Get default printer"""
        for printer in self._printers.values():
            if printer.is_default:
                return printer
        return None

    def print_document(self, job: PrintJob) -> bool:
        """
        Print a document

        Args:
            job: PrintJob containing document data and settings

        Returns:
            bool: True if print job submitted successfully
        """
        printer = self.get_printer(job.printer_name)
        if not printer:
            logger.error(f"Printer not found: {job.printer_name}")
            return False

        if job.document_format.lower() in ['pdf', 'qweb-pdf']:
            return self._print_pdf(job, printer)
        elif job.document_format.lower() == 'txt':
            return self._print_text(job, printer)
        else:
            logger.error(f"Unsupported document format: {job.document_format}")
            return False

    def _print_pdf(self, job: PrintJob, printer: PrinterInfo) -> bool:
        """Print PDF document"""
        # Save PDF to temp file
        temp_file = None
        try:
            temp_file = tempfile.NamedTemporaryFile(
                suffix='.pdf',
                delete=False
            )
            temp_file.write(job.document_data)
            temp_file.close()

            if self.system == 'windows':
                return self._print_pdf_windows(temp_file.name, printer, job)
            else:
                return self._print_pdf_unix(temp_file.name, printer, job)

        except Exception as e:
            logger.error(f"Error printing PDF: {e}")
            return False
        finally:
            # Clean up temp file
            if temp_file and os.path.exists(temp_file.name):
                try:
                    os.unlink(temp_file.name)
                except Exception:
                    pass

    def _print_pdf_windows(self, pdf_path: str, printer: PrinterInfo,
                           job: PrintJob) -> bool:
        """Print PDF on Windows using SumatraPDF or GhostScript"""
        try:
            # Prefer SumatraPDF for better compatibility
            if self._sumatra_path and os.path.exists(self._sumatra_path):
                cmd = [
                    self._sumatra_path,
                    '-print-to', printer.system_name,
                    '-print-settings', f'{job.copies}x',
                    '-silent',
                    pdf_path
                ]
            elif self._ghostscript_path:
                # Use gsprint with GhostScript
                gsprint = os.path.join(os.path.dirname(self._ghostscript_path), 'gsprint.exe')
                if os.path.exists(gsprint):
                    cmd = [
                        gsprint,
                        '-printer', printer.system_name,
                        '-copies', str(job.copies),
                        pdf_path
                    ]
                else:
                    logger.error("Neither SumatraPDF nor gsprint available")
                    return False
            else:
                # Fallback: use system default association
                import win32api
                import win32print
                win32api.ShellExecute(
                    0, "print", pdf_path, f'/d:"{printer.system_name}"', ".", 0
                )
                return True

            result = subprocess.run(cmd, capture_output=True, timeout=120)
            return result.returncode == 0

        except Exception as e:
            logger.error(f"Error printing PDF on Windows: {e}")
            return False

    def _print_pdf_unix(self, pdf_path: str, printer: PrinterInfo,
                        job: PrintJob) -> bool:
        """Print PDF on Linux/macOS using lp command"""
        try:
            cmd = [
                'lp',
                '-d', printer.system_name,
                '-n', str(job.copies),
            ]

            # Add paper size if specified
            paper_format = job.paper_format
            if paper_format.get('format'):
                cmd.extend(['-o', f"media={paper_format['format']}"])

            # Add orientation if specified
            if paper_format.get('orientation') == 'Landscape':
                cmd.extend(['-o', 'landscape'])

            cmd.append(pdf_path)

            result = subprocess.run(cmd, capture_output=True, timeout=120)

            if result.returncode != 0:
                logger.error(f"lp command failed: {result.stderr.decode()}")
                return False

            return True

        except Exception as e:
            logger.error(f"Error printing PDF on Unix: {e}")
            return False

    def _print_text(self, job: PrintJob, printer: PrinterInfo) -> bool:
        """Print text document"""
        temp_file = None
        try:
            temp_file = tempfile.NamedTemporaryFile(
                suffix='.txt',
                delete=False,
                mode='wb'
            )
            temp_file.write(job.document_data)
            temp_file.close()

            if self.system == 'windows':
                # Use notepad for text printing on Windows
                cmd = ['notepad', '/p', temp_file.name]
            else:
                cmd = ['lp', '-d', printer.system_name, '-n', str(job.copies), temp_file.name]

            result = subprocess.run(cmd, capture_output=True, timeout=60)
            return result.returncode == 0

        except Exception as e:
            logger.error(f"Error printing text: {e}")
            return False
        finally:
            if temp_file and os.path.exists(temp_file.name):
                try:
                    os.unlink(temp_file.name)
                except Exception:
                    pass

    def print_test_page(self, printer_name: str) -> bool:
        """
        Print a test page

        Args:
            printer_name: Name of printer to test

        Returns:
            bool: True if test page printed successfully
        """
        printer = self.get_printer(printer_name)
        if not printer:
            logger.error(f"Printer not found: {printer_name}")
            return False

        # Create simple test page content
        test_content = f"""
        ================================
               PRINT TEST PAGE
        ================================

        Printer: {printer_name}
        Status: {printer.status}
        Time: {__import__('datetime').datetime.now().isoformat()}

        If you can read this, the printer
        is working correctly.

        ================================
        """

        job = PrintJob(
            job_id="test",
            printer_name=printer_name,
            document_data=test_content.encode('utf-8'),
            document_format='txt',
            copies=1,
        )

        return self._print_text(job, printer)

    def get_system_info(self) -> Dict:
        """Get system information for sync"""
        import socket
        import uuid as uuid_module

        return {
            'platform': platform.system(),
            'version': platform.version(),
            'architecture': platform.machine(),
            'hostname': socket.gethostname(),
            'python_version': platform.python_version(),
        }

    def get_network_info(self) -> Dict:
        """Get network information for sync"""
        import socket

        hostname = socket.gethostname()
        try:
            ip_address = socket.gethostbyname(hostname)
        except Exception:
            ip_address = "127.0.0.1"

        # Try to get MAC address
        mac_address = ""
        try:
            import uuid as uuid_module
            mac = uuid_module.getnode()
            mac_address = ':'.join(('%012x' % mac)[i:i+2] for i in range(0, 12, 2))
        except Exception:
            pass

        return {
            'hostname': hostname,
            'ip_address': ip_address,
            'mac_address': mac_address,
        }

    def build_sync_data(self, machine_name: str, machine_id: str,
                        location_tag: str = "", config_id: str = "") -> Dict:
        """
        Build printer sync data for Odoo

        Args:
            machine_name: Machine name
            machine_id: Machine ID
            location_tag: Location tag
            config_id: Server configuration ID

        Returns:
            Dict ready to be sent to Odoo
        """
        printers_data = []
        for printer in self.get_all_printers():
            printers_data.append(printer.to_dict())

        return {
            'machine_name': machine_name,
            'machine_id': machine_id,
            'location_tag': location_tag,
            'system_info': self.get_system_info(),
            'network_info': self.get_network_info(),
            'server_config': {
                'config_id': config_id,
            },
            'printers': printers_data,
            'sync_type': 'full',
        }
