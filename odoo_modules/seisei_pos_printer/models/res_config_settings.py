# -*- coding: utf-8 -*-

from odoo import api, fields, models

import logging

_logger = logging.getLogger(__name__)


class ResConfigSettings(models.TransientModel):
    """
    Extends res.config.settings to add Seisei Cloud Print configuration
    """
    _inherit = 'res.config.settings'

    pos_use_seisei_cloud_print = fields.Boolean(
        string='Use Cloud Print',
        related='pos_config_id.use_seisei_cloud_print',
        store=True,
        readonly=False,
        help='Enable Seisei Cloud Print for remote receipt printing'
    )

    pos_seisei_receipt_printer_id = fields.Many2one(
        comodel_name='seisei.printer',
        string='Cloud Receipt Printer',
        related='pos_config_id.seisei_receipt_printer_id',
        store=True,
        readonly=False,
        help='Select the Seisei printer for receipt printing'
    )
