# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class ReportMappingGroup(models.Model):
    """
    Report mapping group model
    Users can belong to a group and inherit all mappings from that group
    """
    _name = 'seisei.report.mapping.group'
    _description = 'Report Mapping Group'
    _rec_name = 'name'
    _order = 'sequence, name'

    name = fields.Char(
        string='Group Name',
        required=True,
        help='Name of the mapping group'
    )
    
    code = fields.Char(
        string='Group Code',
        required=True,
        help='Unique code for the group'
    )
    
    sequence = fields.Integer(
        string='Sequence',
        default=10,
        help='Display order'
    )
    
    description = fields.Text(
        string='Description',
        help='Description of the group'
    )
    
    active = fields.Boolean(
        string='Active',
        default=True,
        help='Whether this group is active'
    )
    
    mapping_ids = fields.One2many(
        comodel_name='seisei.report.mapping',
        inverse_name='group_id',
        string='Mappings',
        help='Mappings associated with this group'
    )
    
    user_ids = fields.Many2many(
        comodel_name='res.users',
        string='Users',
        help='Users belonging to this group'
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
        help='Default printer for users in this group'
    )
    
    default_copies = fields.Integer(
        string='Default Copies',
        default=1,
        help='Default number of print copies for this group'
    )
    
    default_duplex = fields.Boolean(
        string='Default Duplex',
        default=False,
        help='Default duplex setting for this group'
    )

    def get_print_policy(self):
        """
        Get the print policy for the group
        """
        return {
            'action_type': self.default_print_action,
            'printer_id': self.default_printer_id.id,
            'copies': self.default_copies,
            'duplex': self.default_duplex,
        }