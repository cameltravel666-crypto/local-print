# -*- coding: utf-8 -*-

import logging
from odoo import models, fields, api, _

_logger = logging.getLogger(__name__)


class PosPrinter(models.Model):
    """
    Extends pos.printer to add Seisei Receipt Printer association
    """
    _inherit = 'pos.printer'

    # Add new printer type for Seisei
    printer_type = fields.Selection(
        selection_add=[('cloud_printer', 'Cloud Printer')],
        ondelete={'cloud_printer': 'set default'}
    )

    # Link to Seisei Printer
    seisei_printer_id = fields.Many2one(
        comodel_name='seisei.printer',
        string='Cloud Printer',
        help='Associate this POS printer with a Seisei Printer for remote printing'
    )

    @api.model
    def _load_pos_data_fields(self, config_id):
        """Add Seisei fields to POS data loading"""
        params = super()._load_pos_data_fields(config_id)
        params += ['seisei_printer_id']
        return params

    @api.onchange('printer_type')
    def _onchange_printer_type_seisei(self):
        """Clear Seisei printer when switching away from seisei type"""
        for rec in self:
            if rec.printer_type != 'cloud_printer':
                rec.seisei_printer_id = False

    def get_seisei_printer_config(self):
        """Get Seisei printer configuration for the controller"""
        self.ensure_one()
        if not self.seisei_printer_id:
            return None
        
        return {
            'printer_id': self.seisei_printer_id.id,
        }
