# -*- coding: utf-8 -*-

import logging
from odoo import models, fields, api

_logger = logging.getLogger(__name__)


class PosConfig(models.Model):
    """
    Extends pos.config to add Seisei Cloud Print configuration
    """
    _inherit = 'pos.config'

    # Cloud Print mode - similar to is_posbox and other_devices
    use_seisei_cloud_print = fields.Boolean(
        string='Use Cloud Print',
        default=False,
        help='Enable Seisei Cloud Print for remote receipt printing via seisei_print_manager'
    )

    # Receipt printer for cloud print
    seisei_receipt_printer_id = fields.Many2one(
        comodel_name='seisei.printer',
        string='Cloud Receipt Printer',
        help='Select the Seisei printer for receipt printing'
    )

    @api.onchange('use_seisei_cloud_print')
    def _onchange_use_seisei_cloud_print(self):
        """Clear printer when disabling cloud print"""
        for config in self:
            if not config.use_seisei_cloud_print:
                config.seisei_receipt_printer_id = False
