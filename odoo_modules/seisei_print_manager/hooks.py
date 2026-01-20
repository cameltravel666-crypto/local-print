# -*- coding: utf-8 -*-
"""
Seisei Print Manager - Post Init Hooks
Patches QR Ordering module to use Seisei Print Manager

Developed by Seisei
"""

import base64
import json
import logging
from datetime import datetime

_logger = logging.getLogger(__name__)


def _patch_qr_order_print(env):
    """
    Patch qr.order model to use Seisei Print Manager for kitchen printing
    This is called after all modules are loaded
    """
    if 'qr.order' not in env:
        _logger.info("QR Ordering module not installed, skipping Seisei print patch")
        return

    _logger.info("Patching QR Ordering module for Seisei Print Manager integration")

    QrOrder = env['qr.order']

    # Store original methods
    original_send_print_notification = QrOrder._send_print_notification
    original_send_print_notification_for_batch = QrOrder._send_print_notification_for_batch

    def patched_send_print_notification(self, pos_order):
        """
        Patched method to use Seisei Print Manager
        """
        self.ensure_one()
        try:
            pos_config = pos_order.config_id
            if not pos_config:
                _logger.warning(f"No POS config for order {pos_order.name}")
                return

            # Check if Seisei kitchen printer is configured
            if hasattr(pos_config, 'seisei_kitchen_printer_id') and pos_config.seisei_kitchen_printer_id:
                _create_seisei_kitchen_job(self, pos_config.seisei_kitchen_printer_id, pos_order, is_batch=False)
                _logger.info(f"Created Seisei kitchen print job for QR order {self.name}")
                return

            # Try pos.printer with seisei_printer_id
            printers_sent = 0
            for printer in pos_config.printer_ids:
                seisei_printer = None
                if hasattr(printer, 'seisei_printer_id') and printer.seisei_printer_id:
                    seisei_printer = printer.seisei_printer_id
                elif hasattr(printer, 'printer_type') and printer.printer_type == 'cloud_printer':
                    seisei_printer = self.env['seisei.printer'].sudo().search([
                        ('name', '=', printer.name),
                        ('active', '=', True),
                    ], limit=1)

                if seisei_printer:
                    _create_seisei_kitchen_job(self, seisei_printer, pos_order, is_batch=False)
                    printers_sent += 1

            if printers_sent == 0:
                # Fallback to original method
                original_send_print_notification(self, pos_order)
            else:
                _logger.info(f"Sent Seisei print jobs to {printers_sent} printer(s) for QR order {self.name}")

        except Exception as e:
            _logger.error(f"Failed to send Seisei print notification: {e}")
            try:
                original_send_print_notification(self, pos_order)
            except Exception as e2:
                _logger.error(f"Original method also failed: {e2}")

    def patched_send_print_notification_for_batch(self, pos_order, qr_lines):
        """
        Patched method for batch/addition orders
        """
        self.ensure_one()
        try:
            pos_config = pos_order.config_id
            if not pos_config:
                _logger.warning(f"No POS config for order {pos_order.name}")
                return

            # Check if Seisei kitchen printer is configured
            if hasattr(pos_config, 'seisei_kitchen_printer_id') and pos_config.seisei_kitchen_printer_id:
                _create_seisei_kitchen_job(self, pos_config.seisei_kitchen_printer_id, pos_order, is_batch=True, qr_lines=qr_lines)
                _logger.info(f"Created Seisei batch kitchen print job for QR order {self.name}")
                return

            # Try pos.printer with seisei_printer_id
            printers_sent = 0
            for printer in pos_config.printer_ids:
                seisei_printer = None
                if hasattr(printer, 'seisei_printer_id') and printer.seisei_printer_id:
                    seisei_printer = printer.seisei_printer_id
                elif hasattr(printer, 'printer_type') and printer.printer_type == 'cloud_printer':
                    seisei_printer = self.env['seisei.printer'].sudo().search([
                        ('name', '=', printer.name),
                        ('active', '=', True),
                    ], limit=1)

                if seisei_printer:
                    _create_seisei_kitchen_job(self, seisei_printer, pos_order, is_batch=True, qr_lines=qr_lines)
                    printers_sent += 1

            if printers_sent == 0:
                original_send_print_notification_for_batch(self, pos_order, qr_lines)
            else:
                _logger.info(f"Sent Seisei batch print jobs to {printers_sent} printer(s) for QR order {self.name}")

        except Exception as e:
            _logger.error(f"Failed to send Seisei batch print notification: {e}")
            try:
                original_send_print_notification_for_batch(self, pos_order, qr_lines)
            except Exception as e2:
                _logger.error(f"Original method also failed: {e2}")

    # Monkey patch the methods
    QrOrder._send_print_notification = patched_send_print_notification
    QrOrder._send_print_notification_for_batch = patched_send_print_notification_for_batch

    _logger.info("Successfully patched QR Ordering for Seisei Print Manager")


def _create_seisei_kitchen_job(qr_order, seisei_printer, pos_order, is_batch=False, qr_lines=None):
    """
    Create kitchen print job using Seisei Print Manager
    """
    try:
        table_name = qr_order.table_id.name if qr_order.table_id else ''
        lines_to_print = qr_lines if qr_lines else qr_order.line_ids

        # Generate ESC/POS commands
        escpos_commands = _generate_escpos_commands(qr_order, pos_order, lines_to_print, is_batch)
        escpos_base64 = base64.b64encode(escpos_commands).decode('utf-8')

        # Build job name
        if is_batch:
            job_name = 'QR 加菜单 - %s - %s' % (table_name, qr_order.name)
        else:
            job_name = 'QR 厨房单 - %s - %s' % (table_name, qr_order.name)

        # Create print job
        job_vals = {
            'name': job_name,
            'printer_id': seisei_printer.id,
            'type': 'pos_receipt_print',
            'is_test': False,
            'metadata': json.dumps({
                'escpos_commands': escpos_base64,
                'doc_format': 'escpos',
                'qr_order_id': qr_order.id,
                'qr_order_name': qr_order.name,
                'pos_order_id': pos_order.id,
                'pos_order_name': pos_order.name,
                'table_name': table_name,
                'is_batch': is_batch,
            }),
        }

        job = qr_order.env['seisei.print.job'].sudo().create(job_vals)
        job.action_process()

        _logger.info(f"Created Seisei kitchen print job {job.job_id} for QR order {qr_order.name}")
        return job

    except Exception as e:
        _logger.error(f"Failed to create Seisei kitchen print job: {e}")
        return None


def _generate_escpos_commands(qr_order, pos_order, lines, is_batch=False):
    """
    Generate ESC/POS commands for kitchen ticket
    """
    # ESC/POS command constants
    ESC = b'\x1b'
    GS = b'\x1d'

    INIT = ESC + b'@'
    CN_MODE = ESC + b'R\x0f'
    ALIGN_CENTER = ESC + b'a\x01'
    ALIGN_LEFT = ESC + b'a\x00'
    BOLD_ON = ESC + b'E\x01'
    BOLD_OFF = ESC + b'E\x00'
    DOUBLE_SIZE = GS + b'!\x30'
    DOUBLE_HEIGHT = GS + b'!\x10'
    NORMAL_SIZE = GS + b'!\x00'
    FEED_LINES = ESC + b'd\x03'
    PARTIAL_CUT = GS + b'V\x01'

    commands = bytearray()

    # Initialize
    commands.extend(INIT)
    commands.extend(CN_MODE)

    # Header
    commands.extend(ALIGN_CENTER)
    commands.extend(DOUBLE_SIZE)
    commands.extend(BOLD_ON)

    header = "*** QR 加菜单 ***" if is_batch else "*** QR 厨房单 ***"
    try:
        commands.extend(header.encode('gb2312'))
    except:
        commands.extend(header.encode('utf-8'))
    commands.extend(b'\n')

    commands.extend(NORMAL_SIZE)
    commands.extend(BOLD_OFF)

    # Table and time
    commands.extend(DOUBLE_HEIGHT)
    commands.extend(BOLD_ON)

    table_name = qr_order.table_id.name if qr_order.table_id else 'N/A'
    time_str = datetime.now().strftime('%H:%M')

    table_line = f"桌号: {table_name}    {time_str}"
    try:
        commands.extend(table_line.encode('gb2312'))
    except:
        commands.extend(table_line.encode('utf-8'))
    commands.extend(b'\n')

    commands.extend(NORMAL_SIZE)
    commands.extend(BOLD_OFF)

    # Order number
    commands.extend(ALIGN_LEFT)
    order_line = f"订单: {qr_order.name}"
    try:
        commands.extend(order_line.encode('gb2312'))
    except:
        commands.extend(order_line.encode('utf-8'))
    commands.extend(b'\n')

    # Separator
    commands.extend(b'=' * 32 + b'\n')

    # Order lines
    commands.extend(DOUBLE_HEIGHT)
    commands.extend(BOLD_ON)

    for line in lines:
        product_name = line.product_id.name if line.product_id else getattr(line, 'product_name', 'Unknown')
        qty = int(line.qty)

        item_line = f"{qty}x {product_name}"
        try:
            commands.extend(item_line.encode('gb2312'))
        except:
            commands.extend(item_line.encode('utf-8'))
        commands.extend(b'\n')

        # Note
        if hasattr(line, 'note') and line.note:
            commands.extend(NORMAL_SIZE)
            note_line = f"   [{line.note}]"
            try:
                commands.extend(note_line.encode('gb2312'))
            except:
                commands.extend(note_line.encode('utf-8'))
            commands.extend(b'\n')
            commands.extend(DOUBLE_HEIGHT)

    commands.extend(NORMAL_SIZE)
    commands.extend(BOLD_OFF)

    # Separator
    commands.extend(b'=' * 32 + b'\n')

    # Footer
    commands.extend(ALIGN_CENTER)
    footer = "扫码点餐"
    try:
        commands.extend(footer.encode('gb2312'))
    except:
        commands.extend(footer.encode('utf-8'))
    commands.extend(b'\n')

    # Feed and cut
    commands.extend(FEED_LINES)
    commands.extend(PARTIAL_CUT)

    return bytes(commands)


def post_init_hook(env):
    """
    Post init hook - called after module installation
    """
    _patch_qr_order_print(env)


def post_load():
    """
    Post load hook - called when module is loaded
    """
    pass
