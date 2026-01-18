# -*- coding: utf-8 -*-

from odoo import models, api


class SeiseiPrinter(models.Model):
    """
    Extends seisei.printer for POS data loading
    """
    _name = 'seisei.printer'
    _inherit = ['seisei.printer', 'pos.load.mixin']

    @api.model
    def _load_pos_data_domain(self, data):
        """Load printers configured for this POS config"""
        config_data = data.get('pos.config', {}).get('data', [{}])[0]
        printer_ids = []
        
        # Get receipt printer if configured
        if config_data.get('seisei_receipt_printer_id'):
            printer_ids.append(config_data['seisei_receipt_printer_id'])
        
        # Get kitchen printers if any
        printer_data = data.get('pos.printer', {}).get('data', [])
        for printer in printer_data:
            if printer.get('seisei_printer_id'):
                printer_ids.append(printer['seisei_printer_id'])
        
        if printer_ids:
            return [('id', 'in', printer_ids)]
        return False  # Return False to skip loading when no printers configured

    @api.model
    def _load_pos_data_fields(self, config_id):
        """Fields to load for POS"""
        return ['id', 'name', 'display_name', 'station_id', 'status']
