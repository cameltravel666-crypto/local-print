# -*- coding: utf-8 -*-
"""
Seisei Print Manager - Ticket Template Model
Visual ticket template for POS receipts and kitchen tickets

Developed by Seisei
"""

import base64
import io
import json
import logging
from PIL import Image, ImageDraw, ImageFont

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

# ESC/POS command constants
ESC = 0x1B
GS = 0x1D
LF = 0x0A

# Font size mappings (width multiplier, height multiplier)
FONT_SIZE_MAP = {
    'small': (0, 0),      # Normal size
    'normal': (0, 0),     # Normal size
    'large': (1, 1),      # Double width and height
    'xlarge': (2, 2),     # Triple width and height
}

# Paper width in pixels (8 dots per mm)
PAPER_WIDTH_MAP = {
    58: 384,   # 58mm paper = 48mm print width = 384 pixels
    80: 576,   # 80mm paper = 72mm print width = 576 pixels
}


class TicketTemplate(models.Model):
    _name = 'seisei.ticket.template'
    _description = 'Ticket Template'
    _order = 'sequence, id'

    name = fields.Char('Template Name', required=True, translate=True)
    code = fields.Char('Template Code', required=True, index=True)
    sequence = fields.Integer('Sequence', default=10)

    template_type = fields.Selection([
        ('pos_receipt', 'POS Receipt'),
        ('kitchen_ticket', 'Kitchen Ticket'),
    ], string='Template Type', required=True, default='pos_receipt')

    # Canvas settings
    paper_width = fields.Selection([
        ('58', '58mm'),
        ('80', '80mm'),
    ], string='Paper Width', default='80', required=True)

    # Elements (One2many)
    element_ids = fields.One2many(
        'seisei.ticket.element', 'template_id',
        string='Elements', copy=True
    )
    element_count = fields.Integer(
        'Element Count', compute='_compute_element_count'
    )

    # Status
    active = fields.Boolean('Active', default=True)
    is_default = fields.Boolean('Default Template')

    # Preview
    preview_image = fields.Binary('Preview Image', attachment=True)
    preview_html = fields.Html('Preview HTML', compute='_compute_preview_html')

    # Description
    description = fields.Text('Description')

    # Audit fields
    create_uid = fields.Many2one('res.users', string='Created By', readonly=True)
    write_uid = fields.Many2one('res.users', string='Last Updated By', readonly=True)
    create_date = fields.Datetime('Created On', readonly=True)
    write_date = fields.Datetime('Last Updated On', readonly=True)

    _sql_constraints = [
        ('code_unique', 'UNIQUE(code)', 'Template code must be unique!'),
    ]

    @api.depends('element_ids')
    def _compute_element_count(self):
        for record in self:
            record.element_count = len(record.element_ids)

    @api.depends('element_ids', 'paper_width')
    def _compute_preview_html(self):
        """Generate HTML preview of the template"""
        for record in self:
            if not record.element_ids:
                record.preview_html = '<div class="text-muted text-center p-4">No elements</div>'
                continue

            width_px = PAPER_WIDTH_MAP.get(int(record.paper_width) if record.paper_width else 80, 576)
            html_parts = [
                f'<div class="ticket-preview" style="width:{width_px}px;background:#fff;'
                f'font-family:monospace;padding:10px;border:1px solid #ddd;">'
            ]

            for element in record.element_ids.sorted('sequence'):
                html_parts.append(element._render_preview_html())

            html_parts.append('</div>')
            record.preview_html = ''.join(html_parts)

    @api.constrains('is_default', 'template_type')
    def _check_default_template(self):
        """Ensure only one default template per type"""
        for record in self:
            if record.is_default:
                existing = self.search([
                    ('id', '!=', record.id),
                    ('is_default', '=', True),
                    ('template_type', '=', record.template_type),
                ])
                if existing:
                    raise ValidationError(_(
                        'There can only be one default template per type. '
                        'Please unset the default on "%s" first.'
                    ) % existing[0].name)

    def action_set_default(self):
        """Set this template as default for its type"""
        self.ensure_one()
        # Unset other defaults of same type
        self.search([
            ('id', '!=', self.id),
            ('template_type', '=', self.template_type),
            ('is_default', '=', True),
        ]).write({'is_default': False})
        self.is_default = True

    def action_open_editor(self):
        """Open the visual ticket editor"""
        self.ensure_one()
        return {
            'type': 'ir.actions.client',
            'tag': 'seisei_ticket_editor',
            'params': {
                'template_id': self.id,
            },
            'target': 'current',
            'name': _('Edit Template: %s') % self.name,
        }

    def action_preview(self):
        """Generate and show preview"""
        self.ensure_one()
        self._generate_preview()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'seisei.ticket.template',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
            'context': {'form_view_initial_mode': 'readonly'},
        }

    def action_duplicate(self):
        """Duplicate template"""
        self.ensure_one()
        new_template = self.copy({
            'name': _('%s (Copy)') % self.name,
            'code': '%s_copy' % self.code,
            'is_default': False,
        })
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'seisei.ticket.template',
            'res_id': new_template.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def _generate_preview(self, sample_data=None):
        """Generate preview image"""
        self.ensure_one()
        try:
            # Create image
            width = PAPER_WIDTH_MAP.get(int(self.paper_width) if self.paper_width else 80, 576)
            height = self._calculate_template_height()

            img = Image.new('RGB', (width, height), 'white')
            draw = ImageDraw.Draw(img)

            # Render elements
            y_offset = 0
            for element in self.element_ids.sorted('sequence'):
                y_offset = element._render_to_image(draw, y_offset, width, sample_data)

            # Convert to base64
            buffer = io.BytesIO()
            img.save(buffer, format='PNG')
            self.preview_image = base64.b64encode(buffer.getvalue())

        except Exception as e:
            _logger.error('Failed to generate preview: %s', e)

    def _calculate_template_height(self):
        """Calculate total height needed for template"""
        height = 50  # Base padding
        for element in self.element_ids:
            height += element.height or 30
        return max(height, 200)

    def render_to_escpos(self, data=None):
        """
        Render template to ESC/POS command sequence

        Args:
            data: Dictionary with dynamic data for template fields

        Returns:
            bytes: ESC/POS command sequence
        """
        self.ensure_one()
        data = data or {}
        commands = []

        # Initialize printer
        commands.extend([ESC, ord('@')])  # ESC @ - Initialize

        # Render each element
        for element in self.element_ids.sorted('sequence'):
            element_commands = element._render_to_escpos(data)
            if element_commands:
                commands.extend(element_commands)

        # Cut paper (partial cut)
        commands.extend([GS, ord('V'), 1])  # GS V 1 - Partial cut

        return bytes(commands)

    def render_to_image(self, data=None):
        """
        Render template to image (for preview or image-based printing)

        Args:
            data: Dictionary with dynamic data

        Returns:
            bytes: PNG image data
        """
        self.ensure_one()
        data = data or {}

        width = PAPER_WIDTH_MAP.get(int(self.paper_width) if self.paper_width else 80, 576)
        height = self._calculate_template_height()

        img = Image.new('RGB', (width, height), 'white')
        draw = ImageDraw.Draw(img)

        y_offset = 10
        for element in self.element_ids.sorted('sequence'):
            y_offset = element._render_to_image(draw, y_offset, width, data)

        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        return buffer.getvalue()

    @api.model
    def get_default_template(self, template_type):
        """Get default template for given type"""
        template = self.search([
            ('template_type', '=', template_type),
            ('is_default', '=', True),
            ('active', '=', True),
        ], limit=1)
        return template

    def get_elements_json(self):
        """Get elements as JSON for editor"""
        self.ensure_one()
        elements = []
        for el in self.element_ids.sorted('sequence'):
            elements.append({
                'id': el.id,
                'type': el.element_type,
                'sequence': el.sequence,
                'pos_x': el.pos_x,
                'pos_y': el.pos_y,
                'width': el.width,
                'height': el.height,
                'text_content': el.text_content,
                'font_size': el.font_size,
                'text_align': el.text_align,
                'is_bold': el.is_bold,
                'field_name': el.field_name,
                'image_data': el.image_data.decode() if el.image_data else None,
                'separator_style': el.separator_style,
                'barcode_type': el.barcode_type,
                'barcode_field': el.barcode_field,
            })
        return elements

    def save_elements_from_json(self, elements_data):
        """Save elements from JSON data (from editor)"""
        self.ensure_one()

        # Delete existing elements
        self.element_ids.unlink()

        # Create new elements
        for idx, el_data in enumerate(elements_data):
            vals = {
                'template_id': self.id,
                'sequence': el_data.get('sequence', idx * 10),
                'element_type': el_data.get('type'),
                'pos_x': el_data.get('pos_x', 0),
                'pos_y': el_data.get('pos_y', 0),
                'width': el_data.get('width'),
                'height': el_data.get('height'),
                'text_content': el_data.get('text_content'),
                'font_size': el_data.get('font_size', 'normal'),
                'text_align': el_data.get('text_align', 'left'),
                'is_bold': el_data.get('is_bold', False),
                'field_name': el_data.get('field_name'),
                'separator_style': el_data.get('separator_style', 'solid'),
                'barcode_type': el_data.get('barcode_type'),
                'barcode_field': el_data.get('barcode_field'),
            }

            # Handle image data
            if el_data.get('image_data'):
                vals['image_data'] = el_data['image_data'].encode()

            self.env['seisei.ticket.element'].create(vals)

        # Regenerate preview
        self._generate_preview()

        return True
