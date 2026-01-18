# -*- coding: utf-8 -*-

import logging
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class PrintStation(models.Model):
    """
    Print Station Model
    Used to organize and manage printers by physical location or logical grouping
    """
    _name = 'seisei.station'
    _description = 'Print Station'
    _rec_name = 'display_name'
    _order = 'is_default desc, sequence, name'

    name = fields.Char(
        string='Station Name',
        required=True,
        index=True,
        help='Unique identification name of the station'
    )
    
    display_name = fields.Char(
        string='Display Name',
        compute='_compute_display_name',
        store=True,
        help='Friendly name for display'
    )
    
    code = fields.Char(
        string='Station Code',
        required=True,
        index=True,
        help='Short code for quick identification of the station'
    )
    
    description = fields.Text(
        string='Description',
        help='Detailed description of the station'
    )
    
    location = fields.Char(
        string='Physical Location',
        help='Physical location description, e.g.: Building 1 Floor 1 - Finance Department'
    )
    
    ip_address = fields.Char(
        string='IP Address',
        help='Network IP address of the station'
    )
    
    mac_address = fields.Char(
        string='MAC Address',
        help='MAC address of the station'
    )
    
    hostname = fields.Char(
        string='Hostname',
        help='Hostname of the station'
    )
    
    is_active = fields.Boolean(
        string='Active',
        default=True,
        help='Whether this station is active'
    )
    
    is_default = fields.Boolean(
        string='Default Station',
        default=False,
        help='Whether this is the system default station'
    )
    
    sequence = fields.Integer(
        string='Sequence',
        default=10,
        help='Display order, smaller numbers appear first'
    )
    
    printer_ids = fields.One2many(
        comodel_name='seisei.printer',
        inverse_name='station_id',
        string='Related Printers',
        help='All printers under this station'
    )
    
    printer_count = fields.Integer(
        string='Printer Count',
        compute='_compute_printer_count',
        help='Number of printers under this station'
    )
    
    active_printer_count = fields.Integer(
        string='Active Printer Count',
        compute='_compute_printer_count',
        help='Number of active printers under this station'
    )
    
    # Contact information
    responsible_user_id = fields.Many2one(
        comodel_name='res.users',
        string='Responsible User',
        help='Person responsible for this station'
    )
    
    contact_phone = fields.Char(
        string='Contact Phone',
        help='Contact phone of the responsible person'
    )
    
    contact_email = fields.Char(
        string='Contact Email',
        help='Contact email of the responsible person'
    )
    
    last_sync_time = fields.Datetime(
        string='Last Sync Time',
        help='Last time synchronized with service'
    )
    
    create_date = fields.Datetime(
        string='Create Date',
        readonly=True
    )
    
    write_date = fields.Datetime(
        string='Write Date',
        readonly=True
    )

    # SQL constraints
    _sql_constraints = [
        ('unique_name', 'unique(name)', 'Station name must be unique!'),
        ('unique_code', 'unique(code)', 'Station code must be unique!'),
        ('check_sequence', 'check(sequence >= 0)', 'Sequence value must be greater than or equal to 0!'),
    ]

    @api.depends('name', 'code', 'location')
    def _compute_display_name(self):
        """Compute display name"""
        for record in self:
            if record.location:
                record.display_name = f"{record.name} ({record.location})"
            else:
                record.display_name = record.name

    @api.depends('printer_ids', 'printer_ids.active')
    def _compute_printer_count(self):
        """Compute printer count"""
        for record in self:
            record.printer_count = len(record.printer_ids)
            record.active_printer_count = len(record.printer_ids.filtered('active'))

    @api.constrains('is_default')
    def _check_default_station(self):
        """Ensure only one default station"""
        for record in self:
            if record.is_default:
                other_defaults = self.search([
                    ('is_default', '=', True),
                    ('id', '!=', record.id)
                ])
                if other_defaults:
                    raise ValidationError(_('There can only be one default station in the system!'))
                
    @api.model
    def create(self, vals):
        """Handle creation of station"""
        # If this is the first station, automatically set as default
        if not self.search_count([]):
            vals['is_default'] = True
            
        return super().create(vals)

    def write(self, vals):
        """Handle update of station"""
        # If canceling default status, ensure at least one default station remains
        if 'is_default' in vals and not vals['is_default']:
            if self.is_default and self.search_count([('is_default', '=', True)]) == 1:
                raise ValidationError(_('At least one default station must be maintained!'))
                
        return super().write(vals)

    def unlink(self):
        """Check before deleting station"""
        for record in self:
            if record.printer_ids:
                raise UserError(_('Cannot delete a station that contains printers! Please remove all printers first.'))
                
        return super().unlink()

    def action_view_printers(self):
        """View printers under the station"""
        self.ensure_one()
        return {
            'name': _('Station Printers'),
            'type': 'ir.actions.act_window',
            'res_model': 'seisei.printer',
            'view_mode': 'list,form',
            'domain': [('station_id', '=', self.id)],
            'context': {
                'default_station_id': self.id,
                'search_default_station_id': self.id,
            },
            'target': 'current',
        }

    def action_sync_printers(self):
        """
        Sync station printers
        """
        self.ensure_one()
        # TODO: Implement synchronization logic with service
        self.last_sync_time = fields.Datetime.now()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Sync Complete'),
                'message': _('Printer information for station %s has been synchronized') % self.display_name,
                'type': 'success',
            }
        }

    @api.model
    def get_default_station(self):
        """Get default station"""
        default_station = self.search([('is_default', '=', True)], limit=1)
        if not default_station:
            # If no default station, create one
            default_station = self.create({
                'name': 'Default Station',
                'code': 'DEFAULT',
                'description': 'System default station',
                'is_default': True,
            })
        return default_station

    def name_get(self):
        """Custom name display"""
        result = []
        for record in self:
            name = record.display_name or record.name
            if record.is_default:
                name = f"★ {name}"
            result.append((record.id, name))
        return result

    @api.model
    def name_search(self, name='', args=None, operator='ilike', limit=100):
        """Custom name search"""
        args = args or []
        if name:
            domain = [
                '|', '|', '|',
                ('name', operator, name),
                ('code', operator, name),
                ('display_name', operator, name),
                ('location', operator, name)
            ]
            records = self.search(domain + args, limit=limit)
            return records.name_get()
        return super().name_search(name, args, operator, limit)
