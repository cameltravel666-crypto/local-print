# -*- coding: utf-8 -*-

import json
import logging
from datetime import datetime, timedelta
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import base64
import json

_logger = logging.getLogger(__name__)


class PrinterInfo(models.Model):
    """
    Printer Information Model
    """
    _name = 'seisei.printer'
    _description = 'Printer Information'
    _rec_name = 'display_name'
    _order = 'is_default desc, name'

    name = fields.Char(
        string=_('Printer Name'),
        required=True,
        index=True,
        help=_('Printer name in the system')
    )

    config_id = fields.Char(
        string=_('Configuration ID'),
        help=_('Configuration ID, used for printer identification')
    )
    
    display_name = fields.Char(
        string=_('Display Name'),
        compute='_compute_display_name',
        store=True,
        help=_('Friendly name for display')
    )
    
    system_name = fields.Char(
        string=_('System Name'),
        help=_('Actual printer name in the operating system')
    )
    
    station_id = fields.Many2one(
        comodel_name='seisei.station',
        string=_('Station'),
        required=True,
        index=True,
        help=_('Station this printer belongs to')
    )

    station_code = fields.Char(
        string=_('Station Code'),
        related='station_id.code',
        store=True,
        help=_('Unique identifier of the station')
    )
    
    description = fields.Text(
        string=_('Description'),
        help=_('Printer description information')
    )
    
    location = fields.Char(
        string=_('Location'),
        help=_('Physical location of the printer')
    )
    
    manufacturer = fields.Char(
        string=_('Manufacturer'),
        help=_('Printer manufacturer')
    )
    
    model = fields.Char(
        string=_('Model'),
        help=_('Printer model')
    )
    
    is_default = fields.Boolean(
        string=_('Default Printer'),
        help=_('Whether this is the system default printer')
    )
    
    status = fields.Selection([
        ('idle', _('Idle')),
        ('printing', _('Printing')),
        ('error', _('Error')),
        ('offline', _('Offline')),
        ('unknown', _('Unknown'))
    ], string=_('Status'), default='unknown', help=_('Current printer status'))
    
    status_message = fields.Char(
        string=_('Status Message'),
        help=_('Detailed status information')
    )
    
    supported_formats = fields.Text(
        string=_('Supported Formats'),
        help=_('Supported file formats, stored in JSON format')
    )
    
    capabilities = fields.Text(
        string=_('Printer Capabilities'),
        help=_('Printer capability information, stored in JSON format')
    )
    
    service_sync = fields.Boolean(
        string=_('Service Sync'),
        default=False,
        help=_('Whether synced from service')
    )
    
    last_sync_time = fields.Datetime(
        string=_('Last Sync Time'),
        help=_('Last time synced from service')
    )
    
    active = fields.Boolean(
        string=_('Active'),
        default=True,
        help=_('Whether to activate this printer')
    )
    
    # Statistics fields
    total_jobs = fields.Integer(
        string=_('Total Jobs'),
        compute='_compute_job_statistics',
        help=_('Total number of jobs processed by this printer')
    )
    
    success_jobs = fields.Integer(
        string=_('Successful Jobs'),
        compute='_compute_job_statistics',
        help=_('Number of successfully completed jobs')
    )
    
    failed_jobs = fields.Integer(
        string=_('Failed Jobs'),
        compute='_compute_job_statistics',
        help=_('Number of failed jobs')
    )
    
    success_rate = fields.Float(
        string=_('Success Rate'),
        compute='_compute_job_statistics',
        help=_('Job success rate percentage')
    )
    
    # Mapping count
    mapping_count = fields.Integer(
        string=_('Mapping Count'),
        compute='_compute_mapping_count',
        help=_('Number of report mappings using this printer')
    )

    @api.depends('name', 'model', 'location', 'station_id')
    def _compute_display_name(self):
        """Compute display name"""
        for printer in self:
            parts = []
            if printer.station_id:
                parts.append(f"[{printer.station_id.code}]")
            parts.append(printer.name)
            if printer.model:
                parts.append(f"({printer.model})")
            if printer.location:
                parts.append(f"@ {printer.location}")
            printer.display_name = ' '.join(parts)

    def _compute_job_statistics(self):
        """Compute job statistics"""
        for printer in self:
            jobs = self.env['seisei.print.job'].search([
                ('printer_name', '=', printer.name)
            ])
            
            printer.total_jobs = len(jobs)
            printer.success_jobs = len(jobs.filtered(lambda j: j.status == 'completed'))
            printer.failed_jobs = len(jobs.filtered(lambda j: j.status == 'failed'))
            
            if printer.total_jobs > 0:
                printer.success_rate = (printer.success_jobs / printer.total_jobs) * 100
            else:
                printer.success_rate = 0.0

    def _compute_mapping_count(self):
        """Compute mapping count"""
        for printer in self:
            printer.mapping_count = self.env['seisei.report.mapping'].search_count([
                ('printer_name', '=', printer.name)
            ])

    @api.constrains('is_default')
    def _check_single_default(self):
        """Ensure only one default printer"""
        for printer in self:
            if printer.is_default:
                other_defaults = self.search([
                    ('is_default', '=', True),
                    ('id', '!=', printer.id)
                ])
                if other_defaults:
                    raise ValidationError(_('There can only be one default printer.'))

    @api.constrains('name', 'station_id')
    def _check_station_printer_name(self):
        """Ensure printer name is unique within the same station"""
        for printer in self:
            if printer.name and printer.station_id:
                other_printers = self.search([
                    ('name', '=', printer.name),
                    ('station_id', '=', printer.station_id.id),
                    ('id', '!=', printer.id)
                ])
                if other_printers:
                    raise ValidationError(
                        _('A printer named "%s" already exists in station "%s".') % 
                        (printer.name, printer.station_id.display_name)
                    )

    def action_test_print(self):
        """Test print"""
        self.ensure_one()

        if not self.station_id or not self.station_id.code:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'message': _('Printer lacks station information, cannot perform test print'),
                    'type': 'warning',
                    'sticky': False,
                }
            }
        
        # Create test print job
        test_job = self.env['seisei.print.job'].create({
            'name': _('Test Print - %s') % self.name,
            'report_name': 'printer_test',
            'type': 'printer_test',
            'printer_id': self.id,
            'status': 'pending',
            'is_test': True,
        })
        
        # Trigger print processing
        test_job.action_process()
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': _('Test print job has been submitted'),
                'type': 'success',
                'sticky': False,
            }
        }

    @api.model
    def create(self, vals):
        """Automatically assign default station when creating printer"""
        if not vals.get('station_id'):
            # If no station specified, assign to default station
            default_station = self.env['seisei.station'].get_default_station()
            vals['station_id'] = default_station.id
        return super().create(vals)

    def name_get(self):
        """Custom name display including station information"""
        result = []
        for record in self:
            if record.station_id:
                name = f"[{record.station_id.code}] {record.display_name}"
            else:
                name = record.name
            if record.is_default:
                name = f"★ {name}"
            result.append((record.id, name))
        return result

    @api.model
    def find_printer_by_station_and_name(self, station_name, printer_name):
        """Find printer by station name and printer name"""
        station = self.env['seisei.station'].search([
            '|',
            ('name', '=', station_name),
            ('code', '=', station_name)
        ], limit=1)
        
        if not station:
            return self.browse([])
            
        return self.search([
            ('station_id', '=', station.id),
            ('name', '=', printer_name)
        ], limit=1)

    def action_set_default(self):
        """Set as default printer"""
        self.ensure_one()
        
        # Clear other default printers
        self.search([('is_default', '=', True)]).write({'is_default': False})
        
        # Set current as default
        self.write({'is_default': True})
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': _('Set as default printer'),
                'type': 'success',
                'sticky': False,
            }
        }
    
    def action_sync_status(self):
        """Sync status
        
        Send WebSocket message to request client to sync printer status
        """
        for printer in self:

            if not printer.station_id or not printer.station_id.code:
                _logger.warning(_("Printer %s lacks station information, skipping status sync!") % printer.name)
                continue

            # Create status sync job
            test_job = self.env['seisei.print.job'].create({
                'name': _('%s Status Sync') % printer.display_name,
                'type': 'sync_printer_status',
                'printer_name': printer.name,
                'status': 'pending'
            })
            
            # Trigger print processing
            test_job.action_process()
            
            _logger.info(_("Printer status sync request sent: %s @ %s") % (printer.name, printer.station_id.code))
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': _('Status sync request sent, waiting for client response'),
                'type': 'info',
                'sticky': False,
            }
        }

    def action_view_jobs(self):
        """View print jobs"""
        self.ensure_one()
        return {
            'name': _('Print Jobs'),
            'type': 'ir.actions.act_window',
            'res_model': 'seisei.print.job',
            'view_mode': 'list,form',
            'domain': [('printer_name', '=', self.name)],
            'context': {'default_printer_name': self.name}
        }

    def action_view_mappings(self):
        """View mapping configuration"""
        self.ensure_one()
        return {
            'name': _('Report Mappings'),
            'type': 'ir.actions.act_window',
            'res_model': 'seisei.report.mapping',
            'view_mode': 'list,form',
            'domain': [('printer_name', '=', self.name)],
            'context': {'default_printer_name': self.name}
        }

    @api.model
    def _remove_printer(self, websocket_request, station_code, printer_name):
        """
        Remove printer
        Args:
            websocket_request: WebSocket request instance
            station_code (str): Station code
            printer_name (str): Printer name
        """
        try:
            existing_printer = self.search([
                ('station_id.code', '=', station_code),
                ('name', '=', printer_name)
            ], limit=1)
            
            if existing_printer:
                existing_printer.unlink()
                _logger.debug(_("Remove printer: %s") % printer_name)
                
                # Create job to send remove printer message
                job = self.env['seisei.print.job'].create({
                    'name': _('Remove Printer - %s') % printer_name,
                    'type': 'remove_printer',
                    'station_code': station_code,
                    'printer_id': existing_printer.id,
                    'status': 'pending'
                })

                # Trigger print processing
                job.action_process()

            else:
                _logger.warning(_("Attempting to remove non-existent printer: %s") % printer_name)
                
        except Exception as e:
            _logger.error(_("Error occurred while removing printer: %s") % str(e))


    @api.model
    def _handle_print_job_message(self, websocket_request, data):
        """
        Handle print job message
        
        Args:
            websocket_request: WebSocket request instance
            data (dict): Print job data
        """
        try:
            job_id = data.get('job_id')
            job_status = data.get('status')
            printer_name = data.get('printer_name')
            station_code = data.get('station_code')
            status_message = data.get('message', '')
            
            if not job_id:
                _logger.warning(_("Print job message missing job_id"))
                return
            
            if not job_status:
                _logger.warning(_("Print job message missing status: %s") % job_id)
                return
            
            if not printer_name or not station_code:
                _logger.warning(_("Print job message missing printer_name or station_code: %s") % job_id)
                return
                
            _logger.debug(_("Processing print job status update: Job %s -> %s") % (job_id, job_status))
            printer = self.search([
                ('station_id.code', '=', station_code),
                ('name', '=', printer_name)
            ], limit=1)
            
            # Update task status in database
            PrintJob = self.env['seisei.print.job']
            success = PrintJob.update_status(job_id, job_status, status_message)
            
            if success:
                _logger.info(_("Successfully updated print job status: %s -> %s") % (job_id, job_status))
            else:
                _logger.warning(_("Failed to update print job status: %s -> %s") % (job_id, job_status))
                
                # Even if database update fails, create notification job (possibly external job)
                notification_job = self.env['seisei.print.job'].create({
                    'name': _('Update Print Job Status Notification - %s') % job_id,
                    'type': 'update_job_status_notification',
                    'station_code': station_code,
                    'printer_id': printer.id if printer else False,
                    'status': 'pending',
                    'metadata': json.dumps({
                        'original_job_id': job_id,
                        'job_status': job_status,
                        'status_message': status_message
                    })
                })
                
                notification_job.action_process()
            
        except Exception as e:
            _logger.error(_("Error occurred while processing print job message: %s") % str(e))

    @api.model
    def _send_printer_sync_notification(self, printer_data, station_code=None):
        """Send printer sync notification"""
        try:
            # Extract required information from printer data
            printer_name = printer_data.get('name')
            if not printer_name:
                _logger.warning(_("Printer data missing name, cannot send sync notification"))
                return
            
            # If no station_code provided, try to get from printer_data
            if not station_code:
                station_code = printer_data.get('station_code', 'unknown')

            printer = self.search([
                ('station_id.code', '=', station_code),
                ('name', '=', printer_name)
            ], limit=1)
            
            # Create sync notification job
            notification_job = self.env['seisei.print.job'].create({
                'name': _('Printer Sync Notification - %s') % printer_name,
                'type': 'printer_sync_notification',
                'printer_id': printer.id if printer else False,
                'status': 'pending',
                'metadata': json.dumps({
                    'notification_data': {
                        'type': 'printer_sync',
                        'printer_data': printer_data,
                        'timestamp': fields.Datetime.now().isoformat()
                    }
                })
            })
            
            # Trigger processing
            notification_job.action_process()
            
            _logger.info(_("Printer sync notification sent: %s @ %s") % (printer_name, station_code))
        except Exception as e:
            _logger.error(_("Error occurred while sending printer sync notification: %s") % str(e))


    @api.model
    def _handle_print_manager_message(self, message):
        """
        Handle unified print management sync messages, dispatching based on message type
        Args:
            message (dict): Sync data, format {'message_type': 'sync_printers', 'data': station_info}
        """
        # Ensure QR order patch is applied on first print-related activity
        from ..hooks import ensure_qr_order_patched
        ensure_qr_order_patched(self.env)

        try:
            # Extract message type
            message_type = message.get('message_type', 'unknown')
            _logger.info(_("Processing print management sync message: %s") % message_type)
            
            # Dispatch based on message type
            if message_type == 'sync_printers':
                # Extract station data (containing machine identification and printer list)
                station_data = message.get('data', {})
                self._handle_sync_printers(station_data)
            elif message_type == 'job_status_update':
                # Handle job status update from client
                status_data = message.get('data', {})
                self._handle_job_status_update(status_data)
            else:
                _logger.warning(_("Unknown print management sync type: %s") % message_type)
                
        except Exception as e:
            _logger.error(_("Error processing print management sync message: %s") % str(e))

    @api.model
    def _handle_job_status_update(self, status_data):
        """
        Handle job status update from client
        Args:
            status_data (dict): Status update data containing job_id, status, message, etc.
        """
        try:
            job_id = status_data.get('job_id')
            status = status_data.get('status')
            message = status_data.get('message', '')

            if not job_id:
                _logger.warning(_("Job status update missing job_id"))
                return

            # Find and update the job
            job = self.env['seisei.print.job'].search([('job_id', '=', job_id)], limit=1)
            if job:
                job.write({
                    'status': status,
                    'error_message': message if status == 'failed' else '',
                })
                _logger.info(_("Job status updated from client: %s -> %s") % (job_id, status))
            else:
                _logger.warning(_("Job not found for status update: %s") % job_id)

        except Exception as e:
            _logger.error(_("Error handling job status update: %s") % str(e))

    @api.model
    def _handle_sync_printers(self, station_data):
        """
        Handle print manager sync events
        Args:
            station_data (dict): Station sync data, containing machine identification and printer list
        """
        try:
            _logger.info(_("Starting to process station sync data: %s") % list(station_data.keys()))
            
            # Extract station information
            station_info = {
                'server_name': station_data.get('server_name', ''),
                'machine_name': station_data.get('machine_name', ''),
                'machine_id': station_data.get('machine_id', ''),
                'client_label': station_data.get('client_label', ''),  # 保留以兼容旧版本
                'location_tag': station_data.get('location_tag', ''),
                'system_info': station_data.get('system_info', ''),
                'network_info': station_data.get('network_info', ''),
            }
            
            _logger.info(_("Station information: machine_name=%s, location_tag=%s") % (station_info['machine_name'], station_info.get('location_tag', '')))
            
            server_config = station_data.get('server_config', {})
            config_id = server_config.get('config_id', False)

            # Get or create station
            station = self._get_or_create_station(station_info)
            
            # Get printer list
            printers_data = station_data.get('printers', [])
            sync_type = station_data.get('sync_type', 'full')
            sync_count = 0
            
            _logger.info(_("Processing station sync: %s (type: %s, %d printers)") % (station.display_name, sync_type, len(printers_data)))
            
            # Process each printer
            for printer_data in printers_data:
                try:
                    printer_name = printer_data.get('name')
                    if not printer_name:
                        _logger.warning(_("Skipping printer data without name"))
                        continue
                    
                    # Prepare printer data
                    printer_vals = {
                        'name': printer_name,
                        'config_id': config_id,
                        'system_name': printer_data.get('system_name', printer_name),
                        'description': printer_data.get('description', ''),
                        'location': printer_data.get('location', ''),
                        'manufacturer': printer_data.get('manufacturer', ''),
                        'model': printer_data.get('model', ''),
                        'is_default': printer_data.get('is_default', False),
                        'status': printer_data.get('status', 'unknown'),
                        'status_message': printer_data.get('status_message', ''),
                        'supported_formats': str(printer_data.get('supported_formats', [])),
                        'capabilities': str(printer_data.get('capabilities', {})),
                        'service_sync': True,
                        'last_sync_time': fields.Datetime.now(),
                        'station_id': station.id,  # Associate with station
                    }
                    
                    # Find existing printer record (first by UUID, then by station+name)
                    existing_printer = self.search([
                        ('name', '=', printer_name),
                        ('station_id', '=', station.id)
                    ], limit=1)
                    
                    if existing_printer:
                        # Update existing printer
                        existing_printer.write(printer_vals)
                        _logger.info(_("Updated printer information: %s @ %s") % (printer_name, station.display_name))
                    else:
                        # Create new printer
                        existing_printer = self.create(printer_vals)
                        _logger.info(_("Created new printer: %s @ %s") % (printer_name, station.display_name))
                    
                    sync_count += 1
                    
                    # Send individual printer sync confirmation notification
                    notification_data = {
                        'type': 'print_manager_sync_result',
                        'printer_name': printer_name,
                        'station_name': station.display_name,
                        'station_code': station.code,
                        'sync_type': sync_type,
                        'success': True,
                        'timestamp': fields.Datetime.now().isoformat(),
                        'message': _('Printer %s sync successful') % printer_name
                    }
                    
                    # Send sync result notification through print_job
                    sync_job = self.env['seisei.print.job'].create({
                        'name': _('Sync Result Notification - %s') % printer_name,
                        'type': 'sync_result_notification',
                        'printer_id': existing_printer.id if existing_printer else False,
                        'status': 'pending',
                        'metadata': json.dumps(notification_data)
                    })
                    sync_job.action_process()
                    
                except Exception as printer_error:
                    _logger.error(_("Error processing printer %s: %s") % (printer_data.get('name', 'Unknown'), str(printer_error)))
                    
                    # Send individual printer error notification
                    error_notification = {
                        'type': 'print_manager_sync_result',
                        'printer_name': printer_data.get('name', 'Unknown'),
                        'station_name': station.display_name if station else 'Unknown',
                        'sync_type': sync_type,
                        'success': False,
                        'timestamp': fields.Datetime.now().isoformat(),
                        'message': _('Printer sync failed: %s') % str(printer_error)
                    }
                    
                    # Send error notification through print_job
                    error_job = self.env['seisei.print.job'].create({
                        'name': _('Sync Error Notification - %s') % printer_data.get("name", "Unknown"),
                        'type': 'sync_error_notification',
                        'printer_id': existing_printer.id if existing_printer else False,
                        'status': 'pending',
                        'metadata': json.dumps(error_notification)
                    })
                    error_job.action_process()

            # For full sync, remove printers that no longer exist on the client
            if sync_type == 'full' and station:
                synced_printer_names = [p.get('name') for p in printers_data if p.get('name')]
                obsolete_printers = self.search([
                    ('station_id', '=', station.id),
                    ('name', 'not in', synced_printer_names),
                    ('service_sync', '=', True),  # Only remove service-synced printers
                ])
                if obsolete_printers:
                    obsolete_names = obsolete_printers.mapped('name')
                    _logger.info(_("Removing %d obsolete printers from station %s: %s") % (
                        len(obsolete_printers), station.display_name, obsolete_names))
                    obsolete_printers.unlink()

            # Update station last sync time
            if station:
                station.write({'last_sync_time': fields.Datetime.now()})

            _logger.info(_("Station sync completed: %s, successfully synced %d printers") % (station.display_name, sync_count))
            
        except Exception as e:
            _logger.error(_("Error processing station sync: %s") % str(e))
            
            # Send overall error notification
            error_notification = {
                'type': 'print_manager_sync_result',
                'station_name': station_data.get('machine_name', 'Unknown'),
                'sync_type': station_data.get('sync_type', 'unknown'),
                'success': False,
                'timestamp': fields.Datetime.now().isoformat(),
                'message': _('Station sync failed: %s') % str(e)
            }
            
            # Send overall error notification through print_job
            station_error_job = self.env['seisei.print.job'].create({
                'name': _('Station Sync Error Notification - %s') % station_data.get("machine_name", "Unknown"),
                'type': 'station_sync_error_notification',
                'printer_id': False,  # No specific printer for station sync errors
                'status': 'pending',
                'metadata': json.dumps(error_notification)
            })
            station_error_job.action_process()

    @api.model
    def _get_or_create_station(self, station_info):
        """
        Get or create station based on station information
        
        Args:
            station_info (dict): Station information
            
        Returns:
            seisei.station: Station record
        """
        try:
            Station = self.env['seisei.station']
            
            # Extract key information
            machine_name = station_info.get('machine_name', '').strip()
            machine_id = station_info.get('machine_id', '').strip()
            location_tag = station_info.get('location_tag', '').strip()
            
            # Use machine_id as primary identifier, fallback to machine_name
            station_code = machine_id or machine_name or 'UNKNOWN'
            station_name = machine_name or location_tag or machine_id or 'Unknown Station'
            
            # Find existing station (by code or name)
            existing_station = Station.search([
                '|',
                ('code', '=', station_code),
                ('name', '=', station_name)
            ], limit=1)
            
            if existing_station:
                # Update existing station information
                update_vals = {}
                
                # Update basic information
                if machine_name and existing_station.name != machine_name:
                    update_vals['name'] = machine_name
                if machine_id and existing_station.code != machine_id:
                    update_vals['code'] = machine_id
                
                # Update location_tag
                location_tag = station_info.get('location_tag', '').strip()
                if location_tag and existing_station.location != location_tag:
                    update_vals['location'] = location_tag
                
                # Update network information
                network_info = station_info.get('network_info', {})
                if isinstance(network_info, dict):
                    ip_address = network_info.get('ip_address', '').strip()
                    hostname = network_info.get('hostname', '').strip()
                    mac_address = network_info.get('mac_address', '').strip()
                    
                    if ip_address and existing_station.ip_address != ip_address:
                        update_vals['ip_address'] = ip_address
                    if hostname and existing_station.hostname != hostname:
                        update_vals['hostname'] = hostname
                    if mac_address and existing_station.mac_address != mac_address:
                        update_vals['mac_address'] = mac_address
                
                # Update description (combined system information)
                system_info = station_info.get('system_info', {})
                if isinstance(system_info, dict):
                    description_parts = []
                    if system_info.get('platform'):
                        description_parts.append(_("System: %s") % system_info['platform'])
                    if system_info.get('version'):
                        description_parts.append(_("Version: %s") % system_info['version'])
                    if system_info.get('architecture'):
                        description_parts.append(_("Architecture: %s") % system_info['architecture'])
                    
                    new_description = ' | '.join(description_parts)
                    if new_description and existing_station.description != new_description:
                        update_vals['description'] = new_description
                
                # If there are updates, execute update
                if update_vals:
                    existing_station.write(update_vals)
                    _logger.info(_("Updated station information: %s") % existing_station.display_name)
                
                return existing_station
            else:
                # Create new station
                station_vals = {
                    'name': station_name,
                    'code': station_code,
                    'location': station_info.get('location_tag', ''),
                    'is_active': True,
                    'is_default': False,  # New stations are not default by default
                }
                
                # Add network information
                network_info = station_info.get('network_info', {})
                if isinstance(network_info, dict):
                    station_vals.update({
                        'ip_address': network_info.get('ip_address', ''),
                        'hostname': network_info.get('hostname', ''),
                        'mac_address': network_info.get('mac_address', ''),
                    })
                
                # Add system information as description
                system_info = station_info.get('system_info', {})
                if isinstance(system_info, dict):
                    description_parts = []
                    if system_info.get('platform'):
                        description_parts.append(_("System: %s") % system_info['platform'])
                    if system_info.get('version'):
                        description_parts.append(_("Version: %s") % system_info['version'])
                    if system_info.get('architecture'):
                        description_parts.append(_("Architecture: %s") % system_info['architecture'])
                    
                    station_vals['description'] = ' | '.join(description_parts)
                
                new_station = Station.create(station_vals)
                _logger.info(_("Created new station: %s") % new_station.display_name)
                
                return new_station
                
        except Exception as e:
            _logger.error(_("Error getting or creating station: %s") % str(e))
            # Return default station
            return self.env['seisei.station'].get_default_station()

    def print_document(self, report, document, doc_format, **print_opts):
        """
        Print a file
        Format could be pdf, qweb-pdf, raw, ...
        """
        self.ensure_one()
        
        if not self.station_id or not self.station_id.code:
            _logger.error(_("Printer %s lacks station information, cannot print document") % self.name)
            return False

        paper_format = report.get_paperformat()
        paper_format_record = paper_format.read()[0]
        # remove magic fields
        paper_format_record.pop('id', None)
        paper_format_record.pop('create_uid', None)
        paper_format_record.pop('create_date', None)
        paper_format_record.pop('write_uid', None)
        paper_format_record.pop('write_date', None)
        
        test_job = self.env['seisei.print.job'].create({
            'name': _('Print Report %s') % (report.name if report else "Document"),
            'type': 'print_document',
            'printer_id': self.id,
            'status': 'pending',
            'is_test': False,
            'metadata': json.dumps({
                'doc_data': base64.b64encode(document).decode('utf-8') if doc_format == 'qweb-pdf' else document,
                'doc_format': doc_format,
                'print_opts': print_opts,
                'paper_format': paper_format_record,
            })
        })

        # Trigger printing
        test_job.action_process()
        
        return True
