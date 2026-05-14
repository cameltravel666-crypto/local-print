# -*- coding: utf-8 -*-
"""
Seisei Print Manager - POS Config Extension
Add printer configuration to POS settings

Developed by Seisei
"""

import logging

from odoo import models, fields, api, _

_logger = logging.getLogger(__name__)


class PosConfig(models.Model):
    """
    Extend POS Config to add Seisei Print Manager settings
    """
    _inherit = 'pos.config'

    # Receipt Printer Settings
    seisei_receipt_printer_id = fields.Many2one(
        'seisei.printer',
        string='Receipt Printer',
        help='Printer for customer receipts'
    )

    seisei_receipt_template_id = fields.Many2one(
        'seisei.ticket.template',
        string='Receipt Template',
        domain=[('template_type', '=', 'pos_receipt')],
        help='Template for receipt printing'
    )

    # Kitchen Printer Settings
    seisei_kitchen_printer_id = fields.Many2one(
        'seisei.printer',
        string='Kitchen Printer',
        help='Printer for kitchen tickets'
    )

    seisei_kitchen_template_id = fields.Many2one(
        'seisei.ticket.template',
        string='Kitchen Template',
        domain=[('template_type', '=', 'kitchen_ticket')],
        help='Template for kitchen ticket printing'
    )

    # Auto Print Settings
    seisei_auto_print_receipt = fields.Boolean(
        string='Auto Print Receipt',
        default=False,
        help='Automatically print receipt when order is created'
    )

    seisei_print_on_payment = fields.Boolean(
        string='Print on Payment',
        default=True,
        help='Print receipt when payment is completed'
    )

    seisei_auto_print_kitchen = fields.Boolean(
        string='Auto Print Kitchen Ticket',
        default=False,
        help='Automatically print kitchen ticket when order is created'
    )

    seisei_print_copies = fields.Integer(
        string='Print Copies',
        default=1,
        help='Number of receipt copies to print'
    )

    # Cash Drawer Settings
    seisei_open_cash_drawer = fields.Boolean(
        string='Open Cash Drawer',
        default=True,
        help='Open cash drawer before printing receipt'
    )

    seisei_cash_drawer_pin = fields.Selection([
        ('0', 'Pin 2 (Default)'),
        ('1', 'Pin 5'),
    ], string='Cash Drawer Pin', default='0',
        help='Cash drawer connection pin on the printer')

    @api.onchange('seisei_receipt_printer_id')
    def _onchange_receipt_printer(self):
        """Set default template when printer is selected"""
        if self.seisei_receipt_printer_id and not self.seisei_receipt_template_id:
            default_template = self.env['seisei.ticket.template'].get_default_template('pos_receipt')
            if default_template:
                self.seisei_receipt_template_id = default_template

    @api.onchange('seisei_kitchen_printer_id')
    def _onchange_kitchen_printer(self):
        """Set default template when printer is selected"""
        if self.seisei_kitchen_printer_id and not self.seisei_kitchen_template_id:
            default_template = self.env['seisei.ticket.template'].get_default_template('kitchen_ticket')
            if default_template:
                self.seisei_kitchen_template_id = default_template
