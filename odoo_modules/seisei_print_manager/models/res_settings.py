# -*- coding: utf-8 -*-

from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    """
    Res Config Settings, inherit to add print manager settings
    """
    _inherit = 'res.config.settings'

    global_default_print_action = fields.Selection([
        ('download', 'Download'),
        ('print', 'Print'),
        ('download_after_print', 'Download Print'),
    ], string='Global Print Action', 
       default='download_after_print',
       config_parameter='seisei_print_manager.global_default_print_action',
       help='Default print action for all users if no mapping is found !')

    global_default_printer_id = fields.Many2one(
        comodel_name='seisei.printer',
        string='Global Default Printer',
        config_parameter='seisei_print_manager.global_default_printer_id',
        help='Default printer for all users if no mapping is found !'
    )

    global_print_copies = fields.Integer(
        string='Global Default Copies',
        default=1,
        config_parameter='seisei_print_manager.global_print_copies',
        help='Default number of copies for all users'
    )

    global_print_duplex = fields.Boolean(
        string='Global Default Duplex',
        default=False,
        config_parameter='seisei_print_manager.global_print_duplex',
        help='Default duplex setting for all users'
    )

    @api.model
    def get_print_policy(self):
        """
        Get the print policy from global settings
        """
        IrConfigParameter = self.env['ir.config_parameter'].sudo()
        
        action_type = IrConfigParameter.get_param('seisei_print_manager.global_default_print_action', 'download_after_print')
        printer_id = int(IrConfigParameter.get_param('seisei_print_manager.global_default_printer_id', 0) or 0)
        copies = int(IrConfigParameter.get_param('seisei_print_manager.global_print_copies', 1) or 1)
        duplex = IrConfigParameter.get_param('seisei_print_manager.global_print_duplex', 'False') == 'True'
        
        return {
            'action_type': action_type,
            'printer_id': printer_id if printer_id else None,
            'copies': copies,
            'duplex': duplex,
        }
