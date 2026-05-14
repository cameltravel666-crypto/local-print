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

# Global flag to track if QR order patch has been applied
_qr_order_patched = False


def ensure_qr_order_patched(env):
    """
    Ensure the QR order patch is applied.
    This function can be called from anywhere and will only apply the patch once.
    """
    global _qr_order_patched
    if not _qr_order_patched:
        _patch_qr_order_print(env)


def _patch_qr_order_print(env):
    """
    Patch qr.order model to use Seisei Print Manager for kitchen printing
    This is called after all modules are loaded
    """
    if 'qr.order' not in env:
        _logger.info("QR Ordering module not installed, skipping Seisei print patch")
        return

    _logger.info("Patching QR Ordering module for Seisei Print Manager integration")

    # Get the model class, not the recordset
    QrOrderClass = type(env['qr.order'])

    # Store original methods
    original_send_print_notification = QrOrderClass._send_print_notification
    original_send_print_notification_for_batch = QrOrderClass._send_print_notification_for_batch

    def patched_send_print_notification(self, pos_order):
        """
        Patched method to use Seisei Print Manager
        Routes order lines to different printers based on product categories
        """
        self.ensure_one()
        try:
            pos_config = pos_order.config_id
            if not pos_config:
                _logger.warning(f"No POS config for order {pos_order.name}")
                return

            # Check if Seisei kitchen printer is configured (single printer mode)
            if hasattr(pos_config, 'seisei_kitchen_printer_id') and pos_config.seisei_kitchen_printer_id:
                _create_seisei_kitchen_job(self, pos_config.seisei_kitchen_printer_id, pos_order, is_batch=False)
                _logger.info(f"Created Seisei kitchen print job for QR order {self.name}")
                return

            # Route to different printers based on product categories
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
                    # Filter lines by product categories for this printer
                    printer_category_ids = printer.product_categories_ids.ids if printer.product_categories_ids else []

                    if printer_category_ids:
                        # Filter QR order lines that match this printer's categories
                        filtered_lines = self.line_ids.filtered(
                            lambda l: l.product_id and l.product_id.pos_categ_ids and
                            any(cat.id in printer_category_ids for cat in l.product_id.pos_categ_ids)
                        )
                        if filtered_lines:
                            _create_seisei_kitchen_job(self, seisei_printer, pos_order, is_batch=False, qr_lines=filtered_lines)
                            printers_sent += 1
                            _logger.info(f"Routed {len(filtered_lines)} items to {seisei_printer.name} for QR order {self.name}")
                    else:
                        # No category filter, send all lines
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
        Routes order lines to different printers based on product categories
        """
        self.ensure_one()
        try:
            pos_config = pos_order.config_id
            if not pos_config:
                _logger.warning(f"No POS config for order {pos_order.name}")
                return

            # Check if Seisei kitchen printer is configured (single printer mode)
            if hasattr(pos_config, 'seisei_kitchen_printer_id') and pos_config.seisei_kitchen_printer_id:
                _create_seisei_kitchen_job(self, pos_config.seisei_kitchen_printer_id, pos_order, is_batch=True, qr_lines=qr_lines)
                _logger.info(f"Created Seisei batch kitchen print job for QR order {self.name}")
                return

            # Route to different printers based on product categories
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
                    # Filter lines by product categories for this printer
                    printer_category_ids = printer.product_categories_ids.ids if printer.product_categories_ids else []

                    if printer_category_ids:
                        # Filter QR order lines that match this printer's categories
                        filtered_lines = qr_lines.filtered(
                            lambda l: l.product_id and l.product_id.pos_categ_ids and
                            any(cat.id in printer_category_ids for cat in l.product_id.pos_categ_ids)
                        )
                        if filtered_lines:
                            _create_seisei_kitchen_job(self, seisei_printer, pos_order, is_batch=True, qr_lines=filtered_lines)
                            printers_sent += 1
                            _logger.info(f"Routed {len(filtered_lines)} batch items to {seisei_printer.name} for QR order {self.name}")
                    else:
                        # No category filter, send all lines
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

    # Monkey patch the methods on the class
    QrOrderClass._send_print_notification = patched_send_print_notification
    QrOrderClass._send_print_notification_for_batch = patched_send_print_notification_for_batch

    # Set the global flag
    global _qr_order_patched
    _qr_order_patched = True

    _logger.info("Successfully patched QR Ordering for Seisei Print Manager")


def _create_seisei_kitchen_job(qr_order, seisei_printer, pos_order, is_batch=False, qr_lines=None):
    """
    Create kitchen print job using image rendering (same as POS)
    Adds QR order marker to distinguish from regular orders
    """
    try:
        import subprocess
        import tempfile
        import os
        from PIL import Image

        table_name = qr_order.table_id.name if qr_order.table_id else ''
        lines_to_print = qr_lines if qr_lines else qr_order.line_ids

        # Generate image-based ESC/POS commands (same as POS)
        escpos_commands = _generate_image_escpos_commands(qr_order, pos_order, lines_to_print, is_batch)
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
        import traceback
        _logger.error(traceback.format_exc())
        return None


def _generate_image_escpos_commands(qr_order, pos_order, lines, is_batch=False):
    """
    Generate ESC/POS commands using image rendering (same as POS)
    1. Render HTML template
    2. Convert to image using wkhtmltoimage
    3. Convert image to ESC/POS bitmap commands
    """
    import subprocess
    import tempfile
    import os
    from PIL import Image

    # 1. Generate HTML content with QR order marker
    html_content = _render_kitchen_ticket_html(qr_order, pos_order, lines, is_batch)

    # 2. Convert HTML to image using wkhtmltoimage
    try:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False, encoding='utf-8') as html_file:
            html_file.write(html_content)
            html_path = html_file.name

        img_path = html_path.replace('.html', '.png')

        # wkhtmltoimage: 384 pixels width for 80mm thermal printer
        result = subprocess.run([
            'wkhtmltoimage',
            '--width', '384',
            '--quality', '100',
            '--disable-smart-width',
            html_path,
            img_path
        ], capture_output=True, timeout=30)

        if result.returncode != 0:
            _logger.error(f"wkhtmltoimage failed: {result.stderr.decode()}")
            # Fallback to text mode
            return _generate_escpos_commands(qr_order, pos_order, lines, is_batch)

        # 3. Read image and convert to ESC/POS bitmap commands
        with Image.open(img_path) as img:
            escpos_commands = _image_to_escpos(img)

        # Cleanup temp files
        os.unlink(html_path)
        os.unlink(img_path)

        return escpos_commands

    except Exception as e:
        _logger.error(f"Image rendering failed: {e}")
        # Fallback to text mode
        return _generate_escpos_commands(qr_order, pos_order, lines, is_batch)


def _render_kitchen_ticket_html(qr_order, pos_order, lines, is_batch=False):
    """
    Render kitchen ticket HTML (same format as POS OrderChangeReceipt)
    Adds QR order marker to distinguish from regular orders
    """
    from odoo import fields

    # Get data
    config_name = pos_order.config_id.name if pos_order.config_id else ''
    order_time = datetime.now().strftime('%H:%M')

    employee_name = 'QR点餐'  # Mark as QR order

    # Table number
    table_number = ''
    if qr_order.table_id and hasattr(qr_order.table_id, 'name'):
        table_number = qr_order.table_id.name
    if hasattr(qr_order, 'restaurant_table_id') and qr_order.restaurant_table_id:
        rt = qr_order.restaurant_table_id
        if hasattr(rt, 'table_number'):
            table_number = str(rt.table_number)

    # Tracking number
    tracking_number = ''
    if hasattr(pos_order, 'tracking_number') and pos_order.tracking_number:
        tracking_number = str(pos_order.tracking_number)

    # Product lines HTML
    lines_html = ''
    for line in lines:
        product = line.product_id
        product_name = product.name if product else getattr(line, 'product_name', 'Unknown')
        qty = int(line.qty)
        lines_html += '<div class="orderline">'
        lines_html += '<div class="line-content">'
        lines_html += '<span class="qty">' + str(qty) + '</span>'
        lines_html += '<span class="product-name">' + str(product_name) + '</span>'
        lines_html += '</div>'

        # Note
        if hasattr(line, 'note') and line.note:
            note_text = str(line.note).replace('\\n', ', ')
            lines_html += '<div class="note">' + note_text + '</div>'

        lines_html += '</div>'

    # Operation title - with QR marker
    if is_batch:
        op_title = "QR 加菜"
    else:
        op_title = "QR 点餐"

    # Table display
    table_display = ""
    if table_number:
        table_display = "桌号 " + table_number
    if tracking_number:
        if table_display:
            table_display += " # " + tracking_number
        else:
            table_display = "# " + tracking_number

    # Complete HTML
    html = """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: "Microsoft YaHei", "SimHei", "Noto Sans CJK SC", sans-serif; width: 384px; background: white; color: black; padding: 10px; }
        .qr-marker { text-align: center; font-size: 24px; font-weight: bold; padding: 8px; margin-bottom: 10px; border: 3px solid black; background: #f0f0f0; }
        .header { text-align: center; margin-bottom: 10px; }
        .title { font-size: 28px; font-weight: bold; margin-bottom: 5px; }
        .info { font-size: 14px; margin-bottom: 3px; }
        .table-info { font-size: 22px; font-weight: bold; margin: 10px 0; }
        .separator { border-top: 2px dashed black; margin: 10px 0; }
        .op-title { text-align: center; font-size: 20px; font-weight: bold; margin: 10px 0; padding: 5px; background: #333; color: white; }
        .orderline { margin: 8px 0; }
        .line-content { font-size: 20px; font-weight: bold; }
        .qty { margin-right: 15px; }
        .note { font-size: 14px; font-style: italic; margin-left: 30px; color: #333; }
    </style>
</head>
<body>
    <div class="qr-marker">""" + op_title + """</div>
    <div class="header">
        <div class="title">堂食</div>
        <div class="info">""" + config_name + " : " + order_time + """</div>
        <div class="info">来源: """ + employee_name + """</div>
        <div class="table-info">""" + table_display + """</div>
    </div>
    <div class="separator"></div>
    <div class="op-title">New</div>
    <div class="lines">
        """ + lines_html + """
    </div>
</body>
</html>"""

    return html


def _image_to_escpos(img):
    """
    Convert PIL Image to ESC/POS bitmap commands
    Uses GS v 0 command (same as POS frontend CloudPrinter)
    """
    # Convert to grayscale
    img = img.convert('L')

    # Floyd-Steinberg dithering to black and white
    img = img.convert('1')

    width, height = img.size
    pixels = list(img.getdata())

    # ESC/POS commands
    ESC = b'\x1b'
    GS = b'\x1d'

    commands = bytearray()

    # Initialize
    commands.extend(ESC + b'@')

    # Center alignment
    commands.extend(ESC + b'a\x01')

    # GS v 0 - Raster bit image
    # Format: GS v 0 m xL xH yL yH [data]
    # m = 0: normal mode
    bytes_per_line = (width + 7) // 8

    xL = bytes_per_line & 0xFF
    xH = (bytes_per_line >> 8) & 0xFF
    yL = height & 0xFF
    yH = (height >> 8) & 0xFF

    commands.extend(GS + b'v0\x00')
    commands.append(xL)
    commands.append(xH)
    commands.append(yL)
    commands.append(yH)

    # Convert pixel data
    for y in range(height):
        for x_byte in range(bytes_per_line):
            byte_val = 0
            for bit in range(8):
                x = x_byte * 8 + bit
                if x < width:
                    pixel_index = y * width + x
                    # PIL '1' mode: 0=black, 255=white
                    # ESC/POS: 1=print(black), 0=no print(white)
                    if pixels[pixel_index] == 0:  # black
                        byte_val |= (0x80 >> bit)
            commands.append(byte_val)

    # Feed 3 lines
    commands.extend(ESC + b'd\x03')

    # Partial cut
    commands.extend(GS + b'V\x01')

    return bytes(commands)


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
