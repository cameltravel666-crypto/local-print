# -*- coding: utf-8 -*-

import logging
import json
import uuid
from datetime import datetime, timedelta
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class PrintJob(models.Model):
    """Print Job Model"""
    _name = 'seisei.print.job'
    _description = 'Print Job'
    _rec_name = 'display_name'
    _order = 'priority desc, create_date desc'

    name = fields.Char(
        string=_('Job Name'),
        required=True,
        help=_('Name of the print job')
    )
    
    display_name = fields.Char(
        string=_('Display Name'),
        compute='_compute_display_name',
        store=True
    )

    channel_name = fields.Char(
        string=_('Channel Name'),
        compute='_compute_channel_name',
        store=True,
        help=_('WebSocket channel name for real-time updates')
    )
    
    job_id = fields.Char(
        string=_('Job ID'),
        default=lambda self: str(uuid.uuid4()),
        required=True,
        index=True,
        copy=False,
        help=_('Unique job identifier')
    )
    
    report_name = fields.Char(
        string=_('Report Name'),
        index=True,
        help=_('Technical name of the report to print')
    )
    
    report_display_name = fields.Char(
        string=_('Report Display Name'),
        help=_('Friendly display name of the report')
    )

    station_code = fields.Char(
        string=_('Station Code'),
        related='printer_id.station_id.code',
        help=_('Code of the station this job belongs to')
    )
    
    printer_name = fields.Char(
        string=_('Printer Name'),
        related='printer_id.name',
        help=_('Name of the printer to execute the print')
    )
    
    printer_id = fields.Many2one(
        comodel_name='seisei.printer',
        string=_('Printer'),
        help=_('Related printer record')
    )
    
    mapping_id = fields.Many2one(
        comodel_name='seisei.report.mapping',
        string=_('Mapping Rule'),
        help=_('Mapping rule used')
    )
    
    document_id = fields.Integer(
        string=_('Document ID'),
        help=_('ID of the document record to print')
    )
    
    document_model = fields.Char(
        string=_('Document Model'),
        help=_('Model that the document belongs to')
    )
    
    format = fields.Selection([
        ('pdf', 'PDF'),
        ('xlsx', 'Excel'),
        ('docx', 'Word'),
        ('html', 'HTML'),
        ('txt', _('Text'))
    ], string=_('Format'), default='pdf', help=_('Document format'))
    
    copies = fields.Integer(
        string=_('Copies'),
        default=1,
        help=_('Number of copies to print')
    )
    
    status = fields.Selection([
        ('pending', _('Pending')),
        ('processing', _('Processing')),
        ('printing', _('Printing')),
        ('completed', _('Completed')),
        ('failed', _('Failed')),
        ('cancelled', _('Cancelled'))
    ], string=_('Status'), default='pending', index=True, help=_('Job status'))
    
    type = fields.Char(
        string=_('Job Type'), 
        default='report_print', 
        index=True, 
        help=_('Print job type for client identification of processing method'))
    
    priority = fields.Integer(
        string=_('Priority'),
        default=0,
        help=_('Job priority, higher number means higher priority')
    )
    
    settings = fields.Text(
        string=_('Print Settings'),
        help=_('JSON format print settings')
    )
    
    error_message = fields.Text(
        string=_('Error Message'),
        help=_('Error message when job fails')
    )
    
    retry_count = fields.Integer(
        string=_('Retry Count'),
        default=0,
        help=_('Number of job retries')
    )
    
    max_retries = fields.Integer(
        string=_('Max Retries'),
        default=3,
        help=_('Maximum number of retries')
    )
    
    # Time fields
    scheduled_time = fields.Datetime(
        string=_('Scheduled Time'),
        help=_('Scheduled execution time')
    )
    
    started_at = fields.Datetime(
        string=_('Started At'),
        help=_('Job processing start time')
    )
    
    completed_at = fields.Datetime(
        string=_('Completed At'),
        help=_('Job completion time')
    )
    
    duration = fields.Float(
        string=_('Duration (seconds)'),
        compute='_compute_duration',
        help=_('Job execution duration')
    )
    
    # Metadata
    metadata = fields.Text(
        string=_('Metadata'),
        help=_('JSON format job metadata')
    )
    
    is_test = fields.Boolean(
        string=_('Test Job'),
        default=False,
        help=_('Whether this is a test job')
    )
    
    user_id = fields.Many2one(
        'res.users',
        string=_('Created by User'),
        default=lambda self: self.env.user,
        help=_('User who created the job')
    )

    job_data = fields.Text(
        string=_('Job Data'),
        help=_('JSON format job data')
    )

    @api.depends('name', 'station_code')
    def _compute_channel_name(self):
        """Compute channel name based on job data"""
        for job in self:
            if job.station_code:
                job.channel_name = f'seisei_service.{job.station_code}'
            else:
                job.channel_name = False

    @api.depends('name', 'report_name', 'printer_name', 'station_code', 'status')
    def _compute_display_name(self):
        """Compute display name"""
        for job in self:
            if job.name:
                display_name = job.name
            else:
                display_name = f"{job.report_name} → {job.printer_name}"
            
            # Add station code to display name if available
            if job.station_code:
                display_name = f"[{job.station_code}] {display_name}"
            
            status_map = {
                'pending': '⏳',
                'processing': '⚙️',
                'printing': '🖨️',
                'completed': '✅',
                'failed': '❌',
                'cancelled': '🚫'
            }
            status_icon = status_map.get(job.status, '❓')
            job.display_name = f"{status_icon} {display_name}"

    @api.depends('started_at', 'completed_at')
    def _compute_duration(self):
        """Compute execution duration"""
        for job in self:
            if job.started_at and job.completed_at:
                delta = job.completed_at - job.started_at
                job.duration = delta.total_seconds()
            else:
                job.duration = 0.0

    @api.constrains('settings')
    def _check_settings_format(self):
        """Check settings format"""
        for job in self:
            if job.settings:
                try:
                    json.loads(job.settings)
                except (ValueError, TypeError):
                    raise ValidationError(_('Print settings must be in valid JSON format'))

    @api.constrains('metadata')
    def _check_metadata_format(self):
        """Check metadata format"""
        for job in self:
            if job.metadata:
                try:
                    json.loads(job.metadata)
                except (ValueError, TypeError):
                    raise ValidationError(_('Metadata must be in valid JSON format'))

    def run_job(self):
        """Process print job"""
        for job in self:
            if job.status != 'pending':
                continue
            
            try:
                job._update_status('processing', _('Starting job processing'))
                job.started_at = fields.Datetime.now()
                
                # Verify printer availability
                if not job._check_printer_available():
                    raise UserError(_('Printer not available: %s') % job.printer_name)
                
                # Send to service for printing
                success = job._send_to_service()
                
                if success:
                    job._update_status('printing', _('Sent to printer'))
                else:
                    raise UserError(_('Failed to send to printer'))
                    
            except Exception as e:
                job._handle_error(str(e))

    def _check_printer_available(self):
        """Check if printer is available"""
        printer = self.printer_id
        if not printer and self.printer_name:
            printer = self.env['seisei.printer'].search([
                ('name', '=', self.printer_name),
                ('active', '=', True)
            ], limit=1)
        
        if not printer:
            return False
        
        return printer.status not in ['error', 'server-error', 'unavailable', 'unknown']

    def _send_to_service(self):
        """
        Send to service for printing
        Note: In the new architecture, this should send messages to clients via WebSocket
        or directly mark job status and wait for client polling
        """
        try:
            data = {
                'id': self.job_id,
                'type': self.type,
                'config_id': self.printer_id.config_id,
                'printer_name': self.printer_id.name,
                'copies': self.copies,
                'priority': self.priority,
                'metadata': json.loads(self.metadata or '{}'),
            }

            # Use unified printer_manager channel
            # Always use 'print_document' as message type for client compatibility
            self.env['bus.bus']._sendone(self.channel_name, 'print_document', data)

            _logger.info(f"Print job published to message queue: {self.job_id}")
            return True
            
        except Exception as e:
            _logger.error(f"Failed to publish print job: {e}")
            return False
        

    def _update_status(self, status, message=''):
        """
        Update job status
        """
        self.ensure_one()
        old_status = self.status
        
        self.write({
            'status': status,
            'error_message': message if status == 'failed' else '',
        })
        
        if status == 'completed':
            self.completed_at = fields.Datetime.now()
        elif status == 'processing':
            self.started_at = fields.Datetime.now()
        
        _logger.info(f"Job status updated {self.job_id}: {old_status} -> {status} - {message}")

    def _handle_error(self, error_message):
        """Handle error"""
        self.ensure_one()
        _logger.error(f"Job failed: {self.job_id} - {error_message}")
        self.retry_count += 1
        
        if self.retry_count <= self.max_retries:
            # Can retry
            self._update_status('pending', _('Retry %s/%s: %s') % (self.retry_count, self.max_retries, error_message))
            
            # Delayed retry
            retry_delay = min(300, 30 * (2 ** (self.retry_count - 1)))  # Exponential backoff, max 5 minutes
            self.scheduled_time = fields.Datetime.now() + timedelta(seconds=retry_delay)
            
            _logger.warning(f"Job failed, will retry in {retry_delay} seconds: {self.job_id}")
        else:
            # Exceeded max retries, mark as failed
            self._update_status('failed', error_message)
            _logger.error(f"Job finally failed: {self.job_id} - {error_message}")

    def action_process(self):
        """Process job"""
        for job in self:
            if job.status == 'pending':
                job.run_job()

    def action_retry(self):
        """Manual retry"""
        for job in self:
            if job.status in ['failed', 'cancelled']:
                job.write({
                    'status': 'pending',
                    'error_message': '',
                    'scheduled_time': False,
                })
                job.action_process()

    def action_cancel(self):
        """Cancel job"""
        for job in self:
            if job.status in ['pending', 'processing']:
                job._update_status('cancelled', _('User cancelled'))

    def action_view_document(self):
        """
        View related document
        """
        self.ensure_one()
        if self.document_model and self.document_id:
            return {
                'name': _('Related Document'),
                'type': 'ir.actions.act_window',
                'res_model': self.document_model,
                'res_id': self.document_id,
                'view_mode': 'form',
                'target': 'current',
            }

    @api.model
    def update_status(self, job_id, status, message=''):
        """
        Receive status update from Service
        
        Args:
            job_id (str): Job ID
            status (str): New status
            message (str): Status message
        
        Returns:
            bool: Whether update was successful
        """
        try:
            job = self.browse(job_id)
            if not job:
                _logger.warning(f"Job not found: {job_id}")
                return False
            
            job._update_status(status, message)
            return True
            
        except Exception as e:
            _logger.error(f"Failed to update job status from Service: {job_id} -> {status}, error: {str(e)}")
            return False


    @api.model
    def cleanup_old_jobs(self, days=30):
        """Clean up old jobs"""
        cutoff_date = fields.Datetime.now() - timedelta(days=days)
        old_jobs = self.search([
            ('status', 'in', ['completed', 'failed', 'cancelled']),
            ('create_date', '<', cutoff_date),
            ('is_test', '=', False)  # Keep test jobs for debugging
        ])
        
        count = len(old_jobs)
        old_jobs.unlink()
        _logger.info(f"Cleaned up {count} old print jobs")
        
        return count
    
    @api.model
    def handle_job_result(self, result_data: dict):
        """
        Handle job result (generic method)
        
        Args:
            result_data (dict): Job result data
                {
                    'job_id': 'Job ID',
                    'type': 'Job type',
                    'success': True/False,
                    'message': 'Result message',
                    'timestamp': timestamp,
                    'original_data': original job data
                }
        
        Returns:
            bool: Whether processing was successful
        """
        try:
            job_id = result_data.get('job_id')
            type = result_data.get('type', 'unknown')
            success = result_data.get('success', False)
            message = result_data.get('message', '')
            
            # Find corresponding job
            job = self.search([('job_id', '=', job_id), ('type', '=', type)], limit=1)
            
            if not job:
                _logger.warning(f"Job not found: {job_id} (type: {type})")
                return False
            
            if success:
                job._update_status('completed', _('%s job successful: %s') % (type, message))
                _logger.info(f"Job completed: {job_id} (type: {type})")
            else:
                job._update_status('failed', _('%s job failed: %s') % (type, message))
                _logger.error(f"Job failed: {job_id} (type: {type}): {message}")
            
            return True
            
        except Exception as e:
            _logger.error(f"Failed to handle job result: {str(e)}")
            return False
