# -*- coding: utf-8 -*-

import logging
import json

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools.safe_eval import safe_eval

_logger = logging.getLogger(__name__)


class ReportMapping(models.Model):
    """
    Report mapping model
    """
    _name = 'seisei.report.mapping'
    _description = 'Report Printer Mapping'
    _rec_name = 'display_name'
    _order = 'priority desc, sequence, report_name'

    name = fields.Char(
        string='Name',
        help='Name of the mapping configuration'
    )
    
    display_name = fields.Char(
        string='Display Name',
        compute='_compute_display_name',
        store=True
    )
    
    sequence = fields.Integer(
        string='Sequence',
        default=10,
        help='Display order'
    )

    report_id = fields.Many2one(
        comodel_name='ir.actions.report',
        string='Report',
        help='Report record'
    )
    
    report_name = fields.Char(
        string='Report Name',
        related='report_id.report_name',
        help='Odoo report technical name, e.g. sale.order'
    )
    
    printer_id = fields.Many2one(
        comodel_name='seisei.printer',
        string='Printer',
        help='Selected printer or get the default printer of user'
    )

    printer_name = fields.Char(
        string='Printer Name',
        related='printer_id.name',
        help='Specified printer name'
    )
    
    priority = fields.Integer(
        string='Priority',
        default=0,
        help='Mapping priority, higher numbers have higher priority'
    )
    
    active = fields.Boolean(
        string='Active',
        default=True,
        help='Whether this mapping is enabled'
    )
    
    condition = fields.Text(
        string='Matching Conditions',
        default='[]',
        help='Matching conditions in JSON format'
    )

    printer_setting_schema = fields.Text(
        string='Printer Setting Schema',
        help='Printer setting schema in JSON format'
    )
    
    printer_settings = fields.Text(
        string='Print Settings',
        help='Print settings in JSON format'
    )

    action_type = fields.Selection(
        selection=[
            ("download", "Download"), 
            ("print", "Print"),
            ('download_after_print', 'Download After Print'),
        ],
        ondelete={"download": "set default", "print": "set default", "advanced": "set default"},
        default="download_after_print",
        help="Download after print"
    )
    
    copies = fields.Integer(
        string='Print Copies',
        default=1,
        help='Default number of print copies'
    )
    
    duplex = fields.Boolean(
        string='Duplex Print',
        default=False,
        help='Whether to print on both sides'
    )
    
    color_mode = fields.Selection([
        ('auto', 'Auto'),
        ('color', 'Color'),
        ('grayscale', 'Grayscale')
    ], string='Color Mode', default='auto', help='Print color mode')
    
    usage_count = fields.Integer(
        string='Usage Count',
        compute='_compute_usage_count',
        help='Number of times this mapping has been used'
    )

    download_after_print = fields.Boolean(
        string='Download After Print',
        default=False,
        help='Whether to download the print after print'
    )
    
    job_ids = fields.One2many(
        'seisei.print.job',
        'mapping_id',
        string='Print Jobs'
    )
    
    group_id = fields.Many2one(
        comodel_name='seisei.report.mapping.group',
        string='Mapping Group',
        help='Group this mapping belongs to'
    )

    @api.depends('name', 'report_name', 'printer_name')
    def _compute_display_name(self):
        """Compute display name"""
        for mapping in self:
            if mapping.name:
                mapping.display_name = mapping.name
            elif mapping.report_name:
                if mapping.printer_name:
                    mapping.display_name = f"{mapping.report_name} → {mapping.printer_name}"
                else:
                    mapping.display_name = f"{mapping.report_name} → Auto"
            else:
                mapping.display_name = "Unnamed Mapping"

    @api.constrains('condition')
    def _check_conditions_format(self):
        """Check condition format"""
        for mapping in self:
            if mapping.condition:
                try:
                    json.loads(mapping.condition)
                except (ValueError, TypeError):
                    raise ValidationError(_('Conditions must be in valid JSON format'))

    @api.model
    def get_mappings(self, report_id, context=None):
        """
        Find matching mapping for report
        
        Args:
            report_id (int): Report ID
            context (dict): Context information
            
        Returns:
            recordset: Matching mapping record
        """
        context = context or {}
        user_mapping_ids = self.env.user.report_mapping_ids

        report_mapping_ids = self.search([
            ('report_id', '=', report_id),
        ])

        mapping_ids = user_mapping_ids + report_mapping_ids

        return mapping_ids
        
    def get_print_settings(self):
        """Get print settings"""
        self.ensure_one()
        
        base_settings = {
            'copies': self.copies,
            'duplex': self.duplex,
            'color_mode': self.color_mode,
        }
        
        if self.print_settings:
            try:
                custom_settings = json.loads(self.print_settings)
                base_settings.update(custom_settings)
            except Exception as e:
                _logger.warning(f"Failed to parse print settings {self.id}: {e}")
        
        return base_settings

    def action_test_mapping(self):
        """
        Test mapping
        """
        self.ensure_one()
        
        test_job = self.env['seisei.print.job'].create({
            'name': f'Test Mapping - {self.display_name}',
            'report_name': self.report_name,
            'printer_name': self.printer_name,
            'type': 'printer_test',
            'mapping_id': self.id,
            'status': 'pending',
            'is_test': True,
            'settings': json.loads(self.printer_settings or '{}'),
        })
        
        # Run the job
        test_job.action_process()
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': _('Test mapping job submitted'),
                'type': 'success',
                'sticky': False,
            }
        }

    def action_view_jobs(self):
        """
        View print jobs
        """
        self.ensure_one()
        return {
            'name': _('Print Jobs'),
            'type': 'ir.actions.act_window',
            'res_model': 'seisei.print.job',
            'view_mode': 'list,form',
            'domain': [('mapping_id', '=', self.id)],
            'context': {
                'default_report_name': self.report_name,
                'default_printer_name': self.printer_name,
                'default_mapping_id': self.id,
            }
        }
    
    @api.depends('job_ids')
    def _compute_usage_count(self):
        """Compute usage count from job records"""
        for mapping in self:
            mapping.usage_count = len(mapping.job_ids)

    def _check_condition(self):
        """
        Check the condition
        """
        domain = safe_eval(self.condition, {"env": self.env})
        return self.filtered_domain(domain)
    
    def get_print_policy(self):
        """
        Get the print policy for the mapping
        """
        return {
            'action_type': self.action_type,
            'printer_id': self.printer_id.id,
            'copies': self.copies,
            'duplex': self.duplex,
            'print_color_mode': self.color_mode,
        }   
