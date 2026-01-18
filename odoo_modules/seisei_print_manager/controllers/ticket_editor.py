# -*- coding: utf-8 -*-
"""
Seisei Print Manager - Ticket Editor Controller
API endpoints for the visual ticket editor

Developed by Seisei
"""

import base64
import json
import logging

from odoo import http, _
from odoo.http import request
from odoo.exceptions import AccessError, ValidationError

_logger = logging.getLogger(__name__)


class TicketEditorController(http.Controller):
    """Controller for ticket template editor operations"""

    @http.route('/seisei/ticket/template/<int:template_id>/load', type='json', auth='user')
    def load_template(self, template_id):
        """
        Load template data for editor

        Args:
            template_id: Template ID

        Returns:
            dict: Template data including elements
        """
        try:
            template = request.env['seisei.ticket.template'].browse(template_id)
            if not template.exists():
                return {'success': False, 'error': _('Template not found')}

            return {
                'success': True,
                'template': {
                    'id': template.id,
                    'name': template.name,
                    'code': template.code,
                    'template_type': template.template_type,
                    'paper_width': template.paper_width,
                    'elements': template.get_elements_json(),
                }
            }
        except AccessError:
            return {'success': False, 'error': _('Access denied')}
        except Exception as e:
            _logger.error('Failed to load template %s: %s', template_id, e)
            return {'success': False, 'error': str(e)}

    @http.route('/seisei/ticket/template/<int:template_id>/save', type='json', auth='user')
    def save_template(self, template_id, elements, **kwargs):
        """
        Save template elements from editor

        Args:
            template_id: Template ID
            elements: List of element data dictionaries

        Returns:
            dict: Result with success status
        """
        try:
            template = request.env['seisei.ticket.template'].browse(template_id)
            if not template.exists():
                return {'success': False, 'error': _('Template not found')}

            # Update template properties if provided
            update_vals = {}
            if 'name' in kwargs:
                update_vals['name'] = kwargs['name']
            if 'paper_width' in kwargs:
                update_vals['paper_width'] = kwargs['paper_width']

            if update_vals:
                template.write(update_vals)

            # Save elements
            template.save_elements_from_json(elements)

            return {
                'success': True,
                'message': _('Template saved successfully'),
                'template_id': template.id,
            }
        except ValidationError as e:
            return {'success': False, 'error': str(e)}
        except AccessError:
            return {'success': False, 'error': _('Access denied')}
        except Exception as e:
            _logger.error('Failed to save template %s: %s', template_id, e)
            return {'success': False, 'error': str(e)}

    @http.route('/seisei/ticket/template/<int:template_id>/preview', type='json', auth='user')
    def preview_template(self, template_id, sample_data=None):
        """
        Generate preview of template

        Args:
            template_id: Template ID
            sample_data: Optional sample data for dynamic fields

        Returns:
            dict: Preview image as base64
        """
        try:
            template = request.env['seisei.ticket.template'].browse(template_id)
            if not template.exists():
                return {'success': False, 'error': _('Template not found')}

            # Parse sample data if provided
            data = {}
            if sample_data:
                if isinstance(sample_data, str):
                    data = json.loads(sample_data)
                else:
                    data = sample_data

            # Generate preview image
            image_data = template.render_to_image(data)
            preview_base64 = base64.b64encode(image_data).decode()

            return {
                'success': True,
                'preview': preview_base64,
                'content_type': 'image/png',
            }
        except Exception as e:
            _logger.error('Failed to generate preview for template %s: %s', template_id, e)
            return {'success': False, 'error': str(e)}

    @http.route('/seisei/ticket/template/<int:template_id>/render', type='json', auth='user')
    def render_template(self, template_id, data=None):
        """
        Render template to ESC/POS commands

        Args:
            template_id: Template ID
            data: Data for dynamic fields

        Returns:
            dict: ESC/POS commands as base64
        """
        try:
            template = request.env['seisei.ticket.template'].browse(template_id)
            if not template.exists():
                return {'success': False, 'error': _('Template not found')}

            # Parse data
            render_data = {}
            if data:
                if isinstance(data, str):
                    render_data = json.loads(data)
                else:
                    render_data = data

            # Render to ESC/POS
            escpos_bytes = template.render_to_escpos(render_data)
            escpos_base64 = base64.b64encode(escpos_bytes).decode()

            return {
                'success': True,
                'escpos': escpos_base64,
            }
        except Exception as e:
            _logger.error('Failed to render template %s: %s', template_id, e)
            return {'success': False, 'error': str(e)}

    @http.route('/seisei/ticket/template/create', type='json', auth='user')
    def create_template(self, name, code, template_type, paper_width=80):
        """
        Create a new template

        Args:
            name: Template name
            code: Template code (unique)
            template_type: 'pos_receipt' or 'kitchen_ticket'
            paper_width: Paper width in mm (58 or 80)

        Returns:
            dict: Created template data
        """
        try:
            template = request.env['seisei.ticket.template'].create({
                'name': name,
                'code': code,
                'template_type': template_type,
                'paper_width': paper_width,
            })

            return {
                'success': True,
                'template_id': template.id,
                'message': _('Template created successfully'),
            }
        except ValidationError as e:
            return {'success': False, 'error': str(e)}
        except Exception as e:
            _logger.error('Failed to create template: %s', e)
            return {'success': False, 'error': str(e)}

    @http.route('/seisei/ticket/template/<int:template_id>/duplicate', type='json', auth='user')
    def duplicate_template(self, template_id):
        """
        Duplicate a template

        Args:
            template_id: Source template ID

        Returns:
            dict: New template data
        """
        try:
            template = request.env['seisei.ticket.template'].browse(template_id)
            if not template.exists():
                return {'success': False, 'error': _('Template not found')}

            new_template = template.copy({
                'name': _('%s (Copy)') % template.name,
                'code': '%s_copy_%s' % (template.code, template.id),
                'is_default': False,
            })

            return {
                'success': True,
                'template_id': new_template.id,
                'message': _('Template duplicated successfully'),
            }
        except Exception as e:
            _logger.error('Failed to duplicate template %s: %s', template_id, e)
            return {'success': False, 'error': str(e)}

    @http.route('/seisei/ticket/template/list', type='json', auth='user')
    def list_templates(self, template_type=None, active_only=True):
        """
        List available templates

        Args:
            template_type: Filter by type (optional)
            active_only: Only return active templates

        Returns:
            dict: List of templates
        """
        try:
            domain = []
            if template_type:
                domain.append(('template_type', '=', template_type))
            if active_only:
                domain.append(('active', '=', True))

            templates = request.env['seisei.ticket.template'].search(domain)

            return {
                'success': True,
                'templates': [{
                    'id': t.id,
                    'name': t.name,
                    'code': t.code,
                    'template_type': t.template_type,
                    'paper_width': t.paper_width,
                    'is_default': t.is_default,
                    'element_count': t.element_count,
                } for t in templates],
            }
        except Exception as e:
            _logger.error('Failed to list templates: %s', e)
            return {'success': False, 'error': str(e)}

    @http.route('/seisei/ticket/element/types', type='json', auth='user')
    def get_element_types(self):
        """
        Get available element types for the toolbox

        Returns:
            dict: List of element types with metadata
        """
        return {
            'success': True,
            'element_types': [
                {
                    'type': 'text',
                    'label': _('Text'),
                    'icon': 'fa-font',
                    'description': _('Static or formatted text'),
                    'default_height': 30,
                },
                {
                    'type': 'dynamic_field',
                    'label': _('Dynamic Field'),
                    'icon': 'fa-code',
                    'description': _('Field value from data'),
                    'default_height': 30,
                },
                {
                    'type': 'image',
                    'label': _('Image/Logo'),
                    'icon': 'fa-image',
                    'description': _('Logo or image'),
                    'default_height': 80,
                },
                {
                    'type': 'separator',
                    'label': _('Separator'),
                    'icon': 'fa-minus',
                    'description': _('Horizontal line'),
                    'default_height': 20,
                },
                {
                    'type': 'barcode',
                    'label': _('Barcode'),
                    'icon': 'fa-barcode',
                    'description': _('Barcode (Code128, EAN, etc.)'),
                    'default_height': 60,
                },
                {
                    'type': 'qrcode',
                    'label': _('QR Code'),
                    'icon': 'fa-qrcode',
                    'description': _('QR Code'),
                    'default_height': 100,
                },
                {
                    'type': 'line_items',
                    'label': _('Line Items'),
                    'icon': 'fa-list',
                    'description': _('Product line items loop'),
                    'default_height': 100,
                },
            ],
        }

    @http.route('/seisei/ticket/upload/image', type='http', auth='user', methods=['POST'], csrf=False)
    def upload_image(self, **kwargs):
        """
        Upload image for template element

        Returns:
            JSON response with image data
        """
        try:
            file = kwargs.get('file')
            if not file:
                return request.make_json_response({
                    'success': False,
                    'error': _('No file uploaded'),
                })

            # Read and encode image
            image_data = file.read()
            image_base64 = base64.b64encode(image_data).decode()

            return request.make_json_response({
                'success': True,
                'image_data': image_base64,
                'filename': file.filename,
            })
        except Exception as e:
            _logger.error('Failed to upload image: %s', e)
            return request.make_json_response({
                'success': False,
                'error': str(e),
            })
