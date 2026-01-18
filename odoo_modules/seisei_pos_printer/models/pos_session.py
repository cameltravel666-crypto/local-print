# -*- coding: utf-8 -*-

from odoo import models, api


class PosSession(models.Model):
    """
    Extends pos.session to add seisei.printer model loading for POS
    """
    _inherit = 'pos.session'

    @api.model
    def _load_pos_data_models(self, config_id):
        """Add seisei.printer to POS data models"""
        models = super()._load_pos_data_models(config_id)
        models.append('seisei.printer')
        return models
