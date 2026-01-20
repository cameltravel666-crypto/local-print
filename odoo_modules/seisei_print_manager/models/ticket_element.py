# -*- coding: utf-8 -*-
"""
Seisei Print Manager - Ticket Element Model
Individual elements within a ticket template

Developed by Seisei
"""

import base64
import io
import logging
import re

from PIL import Image, ImageDraw, ImageFont

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

# ESC/POS command constants
ESC = 0x1B
GS = 0x1D
LF = 0x0A
HT = 0x09

# Text alignment commands
ALIGN_LEFT = [ESC, ord('a'), 0]
ALIGN_CENTER = [ESC, ord('a'), 1]
ALIGN_RIGHT = [ESC, ord('a'), 2]

# Font size (width, height)
FONT_NORMAL = [GS, ord('!'), 0x00]
FONT_DOUBLE_WIDTH = [GS, ord('!'), 0x10]
FONT_DOUBLE_HEIGHT = [GS, ord('!'), 0x01]
FONT_DOUBLE = [GS, ord('!'), 0x11]
FONT_TRIPLE = [GS, ord('!'), 0x22]

# Bold
BOLD_ON = [ESC, ord('E'), 1]
BOLD_OFF = [ESC, ord('E'), 0]


class TicketElement(models.Model):
    _name = 'seisei.ticket.element'
    _description = 'Ticket Element'
    _order = 'sequence, id'

    template_id = fields.Many2one(
        'seisei.ticket.template', string='Template',
        required=True, ondelete='cascade', index=True
    )
    sequence = fields.Integer('Order', default=10)

    element_type = fields.Selection([
        ('text', 'Text'),
        ('image', 'Image/Logo'),
        ('separator', 'Separator Line'),
        ('barcode', 'Barcode'),
        ('qrcode', 'QR Code'),
        ('dynamic_field', 'Dynamic Field'),
        ('line_items', 'Line Items'),
    ], string='Element Type', required=True, default='text')

    # Position and size
    pos_x = fields.Integer('X Position', default=0)
    pos_y = fields.Integer('Y Position', default=0)
    width = fields.Integer('Width (px)')
    height = fields.Integer('Height (px)', default=30)

    # Text properties
    text_content = fields.Text('Text Content')
    font_size = fields.Selection([
        ('small', 'Small'),
        ('normal', 'Normal'),
        ('large', 'Large'),
        ('xlarge', 'Extra Large'),
    ], string='Font Size', default='normal')
    text_align = fields.Selection([
        ('left', 'Left'),
        ('center', 'Center'),
        ('right', 'Right'),
    ], string='Text Alignment', default='left')
    is_bold = fields.Boolean('Bold', default=False)

    # Image properties
    image_data = fields.Binary('Image', attachment=True)
    image_filename = fields.Char('Image Filename')

    # Dynamic field properties
    field_name = fields.Char(
        'Field Name',
        help='Field path like order.name, partner_id.name, line.product_id.name'
    )
    field_format = fields.Char(
        'Format',
        help='Python format string, e.g., "%.2f" for numbers'
    )

    # Separator properties
    separator_style = fields.Selection([
        ('solid', 'Solid Line ────────'),
        ('dashed', 'Dashed Line - - - -'),
        ('double', 'Double Line ════════'),
        ('dotted', 'Dotted Line ........'),
    ], string='Separator Style', default='solid')
    separator_char = fields.Char('Custom Character', default='-')

    # Barcode/QR Code properties
    barcode_type = fields.Selection([
        ('code128', 'Code 128'),
        ('code39', 'Code 39'),
        ('ean13', 'EAN-13'),
        ('ean8', 'EAN-8'),
        ('upca', 'UPC-A'),
        ('qr', 'QR Code'),
    ], string='Barcode Type', default='code128')
    barcode_field = fields.Char(
        'Barcode Data Field',
        help='Field containing barcode data, e.g., order.name'
    )
    barcode_width = fields.Integer('Barcode Width', default=2)
    barcode_height = fields.Integer('Barcode Height (px)', default=50)

    # Line items properties (for dynamic product lists)
    line_model = fields.Char(
        'Line Model',
        help='Model containing line items, e.g., pos.order.line'
    )
    line_fields = fields.Text(
        'Line Fields',
        help='JSON array of fields to display, e.g., ["product_id.name", "qty", "price_subtotal"]'
    )

    @api.constrains('element_type', 'text_content', 'field_name', 'image_data')
    def _check_element_content(self):
        """Validate element has required content"""
        for record in self:
            if record.element_type == 'text' and not record.text_content:
                # Text can be empty for placeholder
                pass
            elif record.element_type == 'dynamic_field' and not record.field_name:
                raise ValidationError(_('Dynamic field must have a field name.'))
            elif record.element_type == 'image' and not record.image_data:
                # Allow empty for placeholder
                pass

    def _render_preview_html(self):
        """Render element as HTML for preview"""
        self.ensure_one()

        if self.element_type == 'text':
            style = self._get_text_style_html()
            content = self.text_content or ''
            return f'<div style="{style}">{content}</div>'

        elif self.element_type == 'dynamic_field':
            style = self._get_text_style_html()
            label = self.text_content or ''
            field_display = '{%s}' % (self.field_name or 'field')
            return f'<div style="{style}"><span>{label}</span><span style="color:#007bff;">{field_display}</span></div>'

        elif self.element_type == 'separator':
            char = self._get_separator_char()
            line = char * 48  # Approximate width
            return f'<div style="text-align:center;font-family:monospace;">{line}</div>'

        elif self.element_type == 'image':
            if self.image_data:
                return (
                    f'<div style="text-align:center;">'
                    f'<img src="data:image/png;base64,{self.image_data.decode()}" '
                    f'style="max-width:100%;height:{self.height or 60}px;"/>'
                    f'</div>'
                )
            return '<div style="text-align:center;color:#999;">[Image Placeholder]</div>'

        elif self.element_type in ('barcode', 'qrcode'):
            code_type = 'QR' if self.element_type == 'qrcode' else self.barcode_type.upper()
            field = self.barcode_field or 'data'
            return (
                f'<div style="text-align:center;border:1px dashed #999;'
                f'padding:10px;margin:5px 0;">'
                f'[{code_type}: {{{field}}}]</div>'
            )

        elif self.element_type == 'line_items':
            return (
                '<div style="border:1px dashed #17a2b8;padding:10px;margin:5px 0;">'
                '<div style="color:#17a2b8;">Line Items Loop:</div>'
                '<div style="font-size:12px;color:#666;">Product Name | Qty | Price</div>'
                '</div>'
            )

        return '<div>[Unknown Element]</div>'

    def _get_text_style_html(self):
        """Get CSS style for text element"""
        styles = ['font-family:monospace']

        # Font size
        size_map = {
            'small': '12px',
            'normal': '14px',
            'large': '18px',
            'xlarge': '24px',
        }
        styles.append(f"font-size:{size_map.get(self.font_size, '14px')}")

        # Alignment
        styles.append(f"text-align:{self.text_align or 'left'}")

        # Bold
        if self.is_bold:
            styles.append('font-weight:bold')

        return ';'.join(styles)

    def _get_separator_char(self):
        """Get character for separator line"""
        char_map = {
            'solid': '─',
            'dashed': '-',
            'double': '═',
            'dotted': '·',
        }
        return char_map.get(self.separator_style, '-')

    def _render_to_escpos(self, data=None):
        """
        Render element to ESC/POS commands

        Args:
            data: Dictionary with dynamic data

        Returns:
            list: ESC/POS command bytes
        """
        self.ensure_one()
        data = data or {}
        commands = []

        if self.element_type == 'text':
            commands.extend(self._render_text_escpos(self.text_content or ''))

        elif self.element_type == 'dynamic_field':
            value = self._get_field_value(data, self.field_name)
            if self.field_format and value is not None:
                try:
                    # Handle datetime formatting with strftime
                    from datetime import datetime
                    if hasattr(value, 'strftime'):
                        value = value.strftime(self.field_format)
                    else:
                        value = self.field_format % value
                except Exception:
                    value = str(value)
            # Prepend text_content (label) if exists
            label = self.text_content or ''
            text = label + (str(value) if value else '')
            commands.extend(self._render_text_escpos(text))

        elif self.element_type == 'separator':
            commands.extend(self._render_separator_escpos())

        elif self.element_type == 'image':
            commands.extend(self._render_image_escpos())

        elif self.element_type in ('barcode', 'qrcode'):
            barcode_data = self._get_field_value(data, self.barcode_field) or ''
            commands.extend(self._render_barcode_escpos(str(barcode_data)))

        elif self.element_type == 'line_items':
            commands.extend(self._render_line_items_escpos(data))

        return commands

    def _render_text_escpos(self, text):
        """Render text to ESC/POS commands"""
        commands = []

        # Set alignment
        if self.text_align == 'center':
            commands.extend(ALIGN_CENTER)
        elif self.text_align == 'right':
            commands.extend(ALIGN_RIGHT)
        else:
            commands.extend(ALIGN_LEFT)

        # Set font size
        if self.font_size == 'large':
            commands.extend(FONT_DOUBLE)
        elif self.font_size == 'xlarge':
            commands.extend(FONT_TRIPLE)
        else:
            commands.extend(FONT_NORMAL)

        # Set bold
        if self.is_bold:
            commands.extend(BOLD_ON)

        # Add text (encode to bytes)
        try:
            text_bytes = text.encode('gb2312', errors='replace')
        except Exception:
            text_bytes = text.encode('utf-8', errors='replace')
        commands.extend(text_bytes)

        # Line feed
        commands.append(LF)

        # Reset bold
        if self.is_bold:
            commands.extend(BOLD_OFF)

        # Reset font size
        commands.extend(FONT_NORMAL)

        return commands

    def _render_separator_escpos(self):
        """Render separator line to ESC/POS commands"""
        commands = []

        # Center alignment for separator
        commands.extend(ALIGN_CENTER)

        # Get separator character and create line
        char = self._get_separator_char()
        # 32 chars for 58mm, 48 chars for 80mm paper
        paper_width = self.template_id.paper_width or '80'
        line_width = 32 if paper_width == '58' else 48
        line = char * line_width

        try:
            line_bytes = line.encode('gb2312', errors='replace')
        except Exception:
            line_bytes = line.encode('utf-8', errors='replace')
        commands.extend(line_bytes)
        commands.append(LF)

        # Reset alignment
        commands.extend(ALIGN_LEFT)

        return commands

    def _render_image_escpos(self):
        """Render image to ESC/POS raster format"""
        commands = []

        if not self.image_data:
            return commands

        try:
            # Decode and process image
            image_bytes = base64.b64decode(self.image_data)
            img = Image.open(io.BytesIO(image_bytes))

            # Convert to 1-bit black and white
            img = img.convert('L')  # Grayscale
            img = img.point(lambda x: 0 if x < 128 else 255, '1')  # Binary

            # Resize to fit paper width
            paper_width = self.template_id.paper_width or 80
            max_width = 384 if paper_width == 58 else 576

            if img.width > max_width:
                ratio = max_width / img.width
                new_height = int(img.height * ratio)
                img = img.resize((max_width, new_height), Image.LANCZOS)

            # Convert to ESC/POS raster format (GS v 0)
            width_bytes = (img.width + 7) // 8
            height = img.height

            # GS v 0 command: 1D 76 30 m xL xH yL yH d1...dk
            commands.extend([GS, ord('v'), 0x30, 0])  # m=0 (normal mode)
            commands.extend([
                width_bytes & 0xFF,
                (width_bytes >> 8) & 0xFF,
                height & 0xFF,
                (height >> 8) & 0xFF,
            ])

            # Convert image data to bytes
            pixels = img.load()
            for y in range(height):
                for x_byte in range(width_bytes):
                    byte_val = 0
                    for bit in range(8):
                        x = x_byte * 8 + bit
                        if x < img.width:
                            # ESC/POS: 1 = black, 0 = white (inverted from PIL)
                            if pixels[x, y] == 0:  # Black pixel
                                byte_val |= (0x80 >> bit)
                    commands.append(byte_val)

        except Exception as e:
            _logger.error('Failed to render image: %s', e)

        return commands

    def _render_barcode_escpos(self, data):
        """Render barcode to ESC/POS commands"""
        commands = []

        if not data:
            return commands

        # Center barcode
        commands.extend(ALIGN_CENTER)

        if self.barcode_type == 'qr' or self.element_type == 'qrcode':
            # QR Code commands
            # Set QR code size
            commands.extend([GS, ord('('), ord('k'), 3, 0, 0x31, 0x43, 4])

            # Set error correction level (L)
            commands.extend([GS, ord('('), ord('k'), 3, 0, 0x31, 0x45, 0x30])

            # Store data
            data_bytes = data.encode('utf-8')
            data_len = len(data_bytes) + 3
            commands.extend([
                GS, ord('('), ord('k'),
                data_len & 0xFF, (data_len >> 8) & 0xFF,
                0x31, 0x50, 0x30
            ])
            commands.extend(data_bytes)

            # Print QR code
            commands.extend([GS, ord('('), ord('k'), 3, 0, 0x31, 0x51, 0x30])

        else:
            # Standard barcode
            barcode_type_map = {
                'code128': 73,
                'code39': 69,
                'ean13': 67,
                'ean8': 68,
                'upca': 65,
            }
            barcode_num = barcode_type_map.get(self.barcode_type, 73)

            # Set barcode height
            height = self.barcode_height or 50
            commands.extend([GS, ord('h'), min(height, 255)])

            # Set barcode width
            width = self.barcode_width or 2
            commands.extend([GS, ord('w'), min(width, 6)])

            # Print barcode
            data_bytes = data.encode('ascii', errors='ignore')
            commands.extend([GS, ord('k'), barcode_num, len(data_bytes)])
            commands.extend(data_bytes)

        commands.append(LF)
        commands.extend(ALIGN_LEFT)

        return commands

    def _render_line_items_escpos(self, data):
        """Render line items loop to ESC/POS commands"""
        commands = []

        lines = data.get('lines', [])
        if not lines:
            return commands

        for line in lines:
            # Simple format: Product Name    Qty x Price
            name = line.get('product_name', '')[:20]
            qty = line.get('qty', 1)
            price = line.get('price', 0)

            text = f"{name:<20} {qty:>3} x {price:>8.2f}"
            commands.extend(self._render_text_escpos(text))

        return commands

    def _get_field_value(self, data, field_path):
        """Get value from data using dot notation field path"""
        if not field_path or not data:
            return None

        parts = field_path.split('.')
        value = data

        for part in parts:
            if isinstance(value, dict):
                value = value.get(part)
            elif hasattr(value, part):
                value = getattr(value, part)
            else:
                return None

            if value is None:
                return None

        return value

    def _render_to_image(self, draw, y_offset, canvas_width, data=None):
        """
        Render element to PIL Image

        Args:
            draw: PIL ImageDraw object
            y_offset: Current Y position
            canvas_width: Canvas width in pixels
            data: Dynamic data dictionary

        Returns:
            int: New Y offset after this element
        """
        self.ensure_one()
        data = data or {}

        try:
            # Try to load a font
            try:
                font_size_map = {
                    'small': 12,
                    'normal': 16,
                    'large': 24,
                    'xlarge': 32,
                }
                font_size = font_size_map.get(self.font_size, 16)
                font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", font_size)
            except Exception:
                font = ImageFont.load_default()

            if self.element_type == 'text':
                text = self.text_content or ''
                self._draw_text(draw, text, y_offset, canvas_width, font)
                return y_offset + (self.height or 30)

            elif self.element_type == 'dynamic_field':
                value = self._get_field_value(data, self.field_name)
                # Handle datetime formatting
                if self.field_format and value is not None:
                    try:
                        if hasattr(value, 'strftime'):
                            value = value.strftime(self.field_format)
                        else:
                            value = self.field_format % value
                    except Exception:
                        value = str(value)
                # Prepend label if exists
                label = self.text_content or ''
                text = label + (str(value) if value else '{%s}' % self.field_name)
                self._draw_text(draw, text, y_offset, canvas_width, font)
                return y_offset + (self.height or 30)

            elif self.element_type == 'separator':
                char = self._get_separator_char()
                line = char * 48
                draw.text((10, y_offset), line, fill='black', font=font)
                return y_offset + 20

            elif self.element_type == 'image':
                if self.image_data:
                    try:
                        img_bytes = base64.b64decode(self.image_data)
                        img = Image.open(io.BytesIO(img_bytes))
                        # Resize if needed
                        if img.width > canvas_width - 20:
                            ratio = (canvas_width - 20) / img.width
                            img = img.resize(
                                (int(img.width * ratio), int(img.height * ratio)),
                                Image.LANCZOS
                            )
                        # TODO: Paste image (requires proper handling)
                        return y_offset + img.height + 10
                    except Exception:
                        pass
                return y_offset + (self.height or 60)

            elif self.element_type in ('barcode', 'qrcode'):
                # Draw placeholder for barcode
                draw.rectangle(
                    [(50, y_offset), (canvas_width - 50, y_offset + 50)],
                    outline='black'
                )
                code_type = 'QR' if self.element_type == 'qrcode' else 'BARCODE'
                draw.text((100, y_offset + 15), f'[{code_type}]', fill='black', font=font)
                return y_offset + 60

        except Exception as e:
            _logger.error('Failed to render element to image: %s', e)

        return y_offset + (self.height or 30)

    def _draw_text(self, draw, text, y_offset, canvas_width, font):
        """Draw text with alignment"""
        # Get text size
        try:
            bbox = draw.textbbox((0, 0), text, font=font)
            text_width = bbox[2] - bbox[0]
        except Exception:
            text_width = len(text) * 10

        # Calculate x position based on alignment
        if self.text_align == 'center':
            x = (canvas_width - text_width) // 2
        elif self.text_align == 'right':
            x = canvas_width - text_width - 10
        else:
            x = 10

        draw.text((x, y_offset), text, fill='black', font=font)
