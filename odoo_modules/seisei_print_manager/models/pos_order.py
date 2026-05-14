# -*- coding: utf-8 -*-
"""
Seisei Print Manager - POS Order Extension
Automatic receipt printing for POS orders

Developed by Seisei
"""

import base64
import json
import logging

from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class PosOrder(models.Model):
    """
    Extend POS Order to add automatic receipt printing
    """
    _inherit = 'pos.order'

    receipt_printed = fields.Boolean(
        string='Receipt Printed',
        default=False,
        help='Whether the receipt has been printed'
    )

    print_job_id = fields.Many2one(
        'seisei.print.job',
        string='Print Job',
        help='Associated print job for this order'
    )

    @api.model_create_multi
    def create(self, vals_list):
        """Override create to trigger automatic printing"""
        orders = super().create(vals_list)

        for order in orders:
            # Check if automatic printing is enabled for this POS config
            if order.config_id and order.config_id.seisei_auto_print_receipt:
                try:
                    order._print_receipt_to_agent()
                except Exception as e:
                    _logger.error("Failed to print receipt for order %s: %s", order.name, e)

        return orders

    def action_pos_order_paid(self):
        """Override paid action to trigger printing after payment"""
        result = super().action_pos_order_paid()

        for order in self:
            # Print receipt after payment if configured
            if order.config_id and order.config_id.seisei_print_on_payment:
                if not order.receipt_printed:
                    try:
                        order._print_receipt_to_agent()
                    except Exception as e:
                        _logger.error("Failed to print receipt for order %s: %s", order.name, e)

        return result

    def _print_receipt_to_agent(self):
        """
        Print receipt through Seisei Print Agent
        """
        self.ensure_one()

        config = self.config_id
        if not config:
            _logger.warning("No POS config for order %s, skipping print", self.name)
            return False

        # Get printer
        printer = config.seisei_receipt_printer_id
        if not printer:
            _logger.warning("No receipt printer configured for POS %s", config.name)
            return False

        # Check printer status
        if not printer.station_id or not printer.station_id.code:
            _logger.warning("Printer %s has no station, skipping print", printer.name)
            return False

        # Get ticket template
        template = config.seisei_receipt_template_id
        if not template:
            # Try to get default template
            template = self.env['seisei.ticket.template'].get_default_template('pos_receipt')

        if not template:
            _logger.warning("No receipt template configured for POS %s", config.name)
            return False

        # Prepare receipt data
        receipt_data = self._prepare_receipt_data()

        # Render to ESC/POS commands
        try:
            escpos_commands = template.render_to_escpos(receipt_data)

            # Prepend cash drawer open command if enabled
            if config.seisei_open_cash_drawer:
                cash_drawer_cmd = self._get_cash_drawer_command(config)
                escpos_commands = cash_drawer_cmd + escpos_commands

            escpos_base64 = base64.b64encode(escpos_commands).decode('utf-8')
        except Exception as e:
            _logger.error("Failed to render receipt template: %s", e)
            return False

        # Create print job
        print_job = self.env['seisei.print.job'].create({
            'name': _('POS Receipt - %s') % self.name,
            'type': 'pos_receipt_print',
            'printer_id': printer.id,
            'status': 'pending',
            'is_test': False,
            'metadata': json.dumps({
                'escpos_commands': escpos_base64,
                'doc_format': 'escpos',
                'order_id': self.id,
                'order_name': self.name,
                'pos_config': config.name,
            })
        })

        # Link job to order
        self.write({
            'print_job_id': print_job.id,
            'receipt_printed': True,
        })

        # Trigger print processing
        print_job.action_process()

        _logger.info("Receipt print job created for order %s: job %s", self.name, print_job.job_id)
        return True

    def _prepare_receipt_data(self):
        """
        Prepare data dictionary for receipt template rendering

        Returns nested structure to match template field paths like:
        - order.name
        - order.date_order
        - order.user_id.name
        - order.table_id.name
        """
        self.ensure_one()

        # Get company info
        company = self.company_id or self.env.company

        # Get order lines data (for line_items element)
        lines = []
        for line in self.lines:
            lines.append({
                'product_name': line.product_id.name,
                'qty': line.qty,
                'price_unit': line.price_unit,
                'discount': line.discount,
                'price': line.price_subtotal_incl,  # Used by _render_line_items_escpos
                'price_subtotal': line.price_subtotal,
                'price_subtotal_incl': line.price_subtotal_incl,
            })

        # Get payment info
        payment_method_names = []
        for payment in self.payment_ids:
            payment_method_names.append(payment.payment_method_id.name)

        # Build nested receipt data structure to match template field paths
        receipt_data = {
            # Company info (for header)
            'company': {
                'name': company.name,
                'address': company.partner_id.contact_address or '',
                'phone': company.phone or '',
                'email': company.email or '',
                'vat': company.vat or '',
            },

            # Order info - nested structure for order.* field paths
            'order': {
                'name': self.name,
                'pos_reference': self.pos_reference or self.name,
                'date_order': self.date_order,  # Keep as datetime for formatting
                'note': self.note or '',

                # Nested relations
                'user_id': {
                    'name': self.employee_id.name if self.employee_id else (
                        self.user_id.name if self.user_id else ''
                    ),
                },
                'table_id': {
                    # Odoo 18 uses table_number instead of name for restaurant.table
                    'name': (
                        self.table_id.table_number if hasattr(self, 'table_id') and self.table_id and hasattr(self.table_id, 'table_number')
                        else (self.table_id.display_name if hasattr(self, 'table_id') and self.table_id else '')
                    ),
                },
                'partner_id': {
                    'name': self.partner_id.name if self.partner_id else _('Guest'),
                    'address': self.partner_id.contact_address if self.partner_id else '',
                },
                'config_id': {
                    'name': self.config_id.name if self.config_id else '',
                },
                'fiscal_position_id': {
                    'name': self.fiscal_position_id.name if self.fiscal_position_id else '',
                },
                'payment_ids': {
                    'payment_method_id': {
                        'name': ', '.join(payment_method_names) if payment_method_names else '',
                    },
                },

                # Totals
                'amount_total': self.amount_total,
                'amount_tax': self.amount_tax,
                'amount_untaxed': self.amount_total - self.amount_tax,
                'amount_paid': self.amount_paid,
                'amount_return': self.amount_return,
            },

            # Lines for line_items element (flat structure expected by _render_line_items_escpos)
            'lines': lines,
            'line_count': len(lines),
        }

        return receipt_data

    def action_print_receipt(self):
        """
        Manual action to print/reprint receipt
        """
        self.ensure_one()

        if not self.config_id:
            raise UserError(_('No POS configuration found for this order.'))

        if not self.config_id.seisei_receipt_printer_id:
            raise UserError(_('No receipt printer configured for this POS.'))

        # Reset printed flag to allow reprint
        self.receipt_printed = False

        success = self._print_receipt_to_agent()

        if success:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'message': _('Receipt sent to printer'),
                    'type': 'success',
                    'sticky': False,
                }
            }
        else:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'message': _('Failed to print receipt'),
                    'type': 'warning',
                    'sticky': False,
                }
            }

    def _get_cash_drawer_command(self, config=None):
        """
        Generate ESC/POS command to open cash drawer

        ESC p m t1 t2
        - m: drawer pin (0=pin2, 1=pin5)
        - t1: on time (25 = 50ms)
        - t2: off time (250 = 500ms)

        Returns:
            bytes: ESC/POS cash drawer open command
        """
        ESC = b'\x1b'

        # Get pin from config (default to pin 0)
        pin = 0
        if config and hasattr(config, 'seisei_cash_drawer_pin') and config.seisei_cash_drawer_pin:
            pin = int(config.seisei_cash_drawer_pin)

        # ESC p m t1 t2 - Open cash drawer
        # t1=25 (50ms on), t2=250 (500ms off) - standard timing
        cash_drawer_cmd = ESC + b'p' + bytes([pin, 25, 250])

        return cash_drawer_cmd
