# -*- coding: utf-8 -*-

from odoo import api, fields, models


class ResUsers(models.Model):
    """
    Res Users, inherit the printing.action field
    """
    _inherit = "res.users"

    report_mapping_ids = fields.Many2many(
        comodel_name="seisei.report.mapping",
        string="Report Mappings"
    )
    
    mapping_group_ids = fields.Many2many(
        comodel_name='seisei.report.mapping.group',
        string='Mapping Groups',
        help='Mapping groups this user belongs to'
    )

    default_mapping_group_id = fields.Many2one(
        comodel_name='seisei.report.mapping.group',
        string='Default Mapping Group',
        help='Default mapping group for this user'
    )

    default_print_action = fields.Selection(
        selection=[
            ("download", "Download"), 
            ("print", "Print"),
            ('download_after_print', 'Download Print'),
        ],
        ondelete={"download": "set default", "print": "set default", "download_after_print": "set default"},
        default="download",
        help="Default print action if no mapping is found !"
    )

    default_printer_id = fields.Many2one(
        comodel_name='seisei.printer',
        string='Default Printer',
        help='Default printer for this user if no mapping is found !'
    )

    default_print_copies = fields.Integer(
        string='Default Copies',
        default=1,
        help='Default number of copies for this user'
    )

    default_print_duplex = fields.Boolean(
        string='Default Duplex',
        default=False,
        help='Default duplex setting for this user'
    )

    default_print_color_mode = fields.Selection([
        ('auto', 'Auto'),
        ('color', 'Color'),
        ('grayscale', 'Grayscale')
    ], string='Default Color Mode', 
       default='auto', 
       help='Default color mode for this user')

    @property
    def SELF_READABLE_FIELDS(self):
        return super().SELF_READABLE_FIELDS + [
            "report_mapping_ids",
            "mapping_group_ids",
            "default_mapping_group_id",
            "default_print_action",
            "default_printer_id",
            "default_print_copies",
            "default_print_duplex",
            "default_print_color_mode",
        ]

    @property
    def SELF_WRITEABLE_FIELDS(self):
        return super().SELF_WRITEABLE_FIELDS + [
            "report_mapping_ids",
            "mapping_group_ids",
            "default_mapping_group_id",
            "default_print_action",
            "default_printer_id",
            "default_print_copies",
            "default_print_duplex",
            "default_print_color_mode",
        ]
    
    @api.onchange('mapping_group_ids')
    def _onchange_mapping_group_id(self):
        """
        当用户所属组改变时，自动应用组设置
        """
        # Add mappings from all groups
        for group in self.mapping_group_ids:
            self.report_mapping_ids = [(4, mapping.id) for mapping in group.mapping_ids]
        
        # Set default mapping group if not set or not in current groups
        if not self.default_mapping_group_id \
            or self.default_mapping_group_id.id not in self.mapping_group_ids.ids:
            if self.mapping_group_ids:
                self.default_mapping_group_id = self.mapping_group_ids[0]

    @api.onchange('default_mapping_group_id')
    def _onchange_default_mapping_group_id(self):
        """
        When the default mapping group changes, update the report mappings
        """
        if self.default_mapping_group_id:
            # Update default settings from the group
            if not self.default_print_action:   
                self.default_print_action = self.default_mapping_group_id.default_print_action
            if not self.default_printer_id:
                self.default_printer_id = self.default_mapping_group_id.default_printer_id
            if not self.default_print_copies:
                self.default_print_copies = self.default_mapping_group_id.default_print_copies
            if not self.default_print_duplex:
                self.default_print_duplex = self.default_mapping_group_id.default_print_duplex
            
            # Add the group's mappings to user's mappings
            if self.default_mapping_group_id not in self.mapping_group_ids:
                self.mapping_group_ids = [(4, self.default_mapping_group_id.id)]

    def get_print_policy(self):
        """
        Get the print behaviour for the user
        """
        return {
            'action_type': self.default_print_action,
            'printer_id': self.default_printer_id.id,
            'copies': self.default_print_copies,
            'duplex': self.default_print_duplex,
            'print_color_mode': self.default_print_color_mode,
        }
