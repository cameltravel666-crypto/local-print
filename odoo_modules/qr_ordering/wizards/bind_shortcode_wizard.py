# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class QrTableBindShortcodeWizard(models.TransientModel):
    """Wizard for binding short code to QR table"""
    _name = 'qr.table.bind.shortcode.wizard'
    _description = _('Bind Short Code Wizard')

    table_id = fields.Many2one(
        'qr.table',
        string=_('Table'),
        required=True,
        readonly=True
    )

    short_code = fields.Char(
        string=_('Short Code'),
        size=10,
        required=True,
        help=_('Enter a short code (e.g., A01, B02). Only letters and numbers allowed.')
    )

    @api.constrains('short_code')
    def _check_short_code(self):
        for wizard in self:
            if wizard.short_code:
                # 只允许字母和数字
                if not wizard.short_code.replace(' ', '').isalnum():
                    raise ValidationError(_('Short code can only contain letters and numbers'))

                # 检查唯一性
                existing = self.env['qr.table'].search([
                    ('short_code', '=', wizard.short_code.upper()),
                    ('id', '!=', wizard.table_id.id)
                ])
                if existing:
                    raise ValidationError(
                        _('Short code "%s" is already used by table "%s"') % (
                            wizard.short_code, existing.name
                        )
                    )

    def action_bind(self):
        """Bind the short code to the table"""
        self.ensure_one()
        self.table_id.write({
            'short_code': self.short_code.upper().strip()
        })
        return {'type': 'ir.actions.act_window_close'}
