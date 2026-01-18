# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import json


class PrintPolicySelectorWizard(models.TransientModel):
    """
    Wizard for selecting print policy when multiple policies are available
    Uses context to get policies instead of creating temporary data
    """
    _name = 'seisei.print.policy.selector.wizard'
    _description = 'Print Policy Selector Wizard'

    report_id = fields.Many2one(
        comodel_name='ir.actions.report',
        string='Report',
        readonly=True
    )
    
    report_name = fields.Char(
        string='Report Name',
        related='report_id.name',
        readonly=True
    )
    
    policy_ids = fields.One2many(
        comodel_name='seisei.print.policy.selector.line',
        inverse_name='wizard_id',
        string='Available Policies'
    )

    @api.model
    def default_get(self, fields_list):
        """
        Override default_get to create policy lines from context
        This avoids creating temporary records in the database
        """
        res = super().default_get(fields_list)
        
        # Get policies from context
        policies = self.env.context.get('policies', [])
        
        if policies and 'policy_ids' in fields_list:
            policy_lines = []
            for idx, policy in enumerate(policies):
                mapping_id = policy.get('id') if policy.get('id') else None
                policy_lines.append((0, 0, {
                    'sequence': idx * 10,
                    'name': policy.get('name', _('Unnamed Policy')),
                    'mapping_id': mapping_id,
                    'printer_id': policy.get('printer_id'),
                    'action_type': policy.get('action', 'download'),
                    'copies': policy.get('copies', 1),
                    'duplex': policy.get('duplex', False),
                    'color_mode': policy.get('print_color_mode', 'auto'),
                    'is_selected': idx == 0,  # Select first policy by default
                }))
            res['policy_ids'] = policy_lines
        
        return res

    def action_confirm(self):
        """
        Confirm selection and save
        FormViewDialog will handle the result through onRecordSaved callback
        """
        self.ensure_one()
        
        if not self.selected_policy_id:
            raise UserError(_('Please select a print policy'))
        
        # close the wizard
        return {'type': 'ir.actions.act_window_close'}


class PrintPolicySelectorLine(models.TransientModel):
    """
    Policy selector line - represents one available policy
    """
    _name = 'seisei.print.policy.selector.line'
    _description = 'Print Policy Selector Line'
    _order = 'sequence, id'
    _rec_name = 'display_name'

    wizard_id = fields.Many2one(
        comodel_name='seisei.print.policy.selector.wizard',
        string='Wizard',
        required=True,
        ondelete='cascade'
    )
    
    sequence = fields.Integer(
        string='Sequence',
        default=10
    )
    
    name = fields.Char(
        string='Policy Name',
        required=True
    )
    
    mapping_id = fields.Many2one(
        comodel_name='seisei.report.mapping',
        string='Mapping',
        help='Related mapping record (if any)'
    )
    
    printer_id = fields.Many2one(
        comodel_name='seisei.printer',
        string='Printer'
    )
    
    printer_name = fields.Char(
        string='Printer Name',
        related='printer_id.name'
    )
    
    action_type = fields.Selection(
        selection=[
            ('download', 'Download'),
            ('print', 'Print'),
            ('download_after_print', 'Download and Print'),
            ('user_setting_first', 'User Setting First')
        ],
        string='Action',
        required=True
    )
    
    copies = fields.Integer(
        string='Copies',
        default=1
    )
    
    duplex = fields.Boolean(
        string='Duplex',
        default=False
    )
    
    color_mode = fields.Selection([
        ('auto', 'Auto'),
        ('color', 'Color'),
        ('grayscale', 'Grayscale')
    ], string='Color Mode', default='auto')
    
    is_selected = fields.Boolean(
        string='Selected',
        default=False,
        help='Whether this policy is selected'
    )
    
    description = fields.Char(
        string='Description',
        compute='_compute_description',
        store=True
    )
    
    display_name = fields.Char(
        string='Display Name',
        compute='_compute_display_name',
        store=True
    )
    
    @api.depends('name', 'printer_name', 'action_type', 'copies')
    def _compute_display_name(self):
        """
        Compute display name for selector
        """
        for line in self:
            parts = [line.name or _('Unnamed')]
            
            if line.printer_name:
                parts.append('→ %s' % line.printer_name)
            
            # Action type
            action_labels = {
                'download': _('Download'),
                'print': _('Print'),
                'download_after_print': _('Download & Print'),
                'user_setting_first': _('User Setting First')
            }
            action_label = action_labels.get(line.action_type, line.action_type)
            parts.append('[%s]' % action_label)
            
            if line.copies and line.copies > 1:
                parts.append('(%s份)' % line.copies)
            
            line.display_name = ' '.join(parts)
    
    @api.depends('printer_name', 'action_type', 'copies', 'duplex')
    def _compute_description(self):
        """
        Compute description for display
        """
        for line in self:
            parts = []
            
            # Action type
            action_labels = {
                'download': _('Download'),
                'print': _('Print'),
                'download_after_print': _('Download & Print'),
                'user_setting_first': _('User Setting First')
            }
            parts.append(action_labels.get(line.action_type, line.action_type))
            
            # Printer
            if line.printer_name:
                parts.append(_('Printer: %s') % line.printer_name)
            
            # Copies
            if line.copies and line.copies > 1:
                parts.append(_('%s copies') % line.copies)
            
            line.description = ' • '.join(parts)
