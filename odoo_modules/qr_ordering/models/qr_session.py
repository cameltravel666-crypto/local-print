# -*- coding: utf-8 -*-

import secrets
from datetime import datetime, timedelta
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

import logging
_logger = logging.getLogger(__name__)


class QrSession(models.Model):
    """QR Ordering Session - for anti-abuse and status management"""
    _name = 'qr.session'
    _description = _('QR Ordering Session')
    _order = 'create_date desc'

    name = fields.Char(
        string=_('Session ID'),
        required=True,
        readonly=True,
        default=lambda self: self._generate_session_id(),
        copy=False
    )

    # Related table
    table_id = fields.Many2one(
        'qr.table',
        string=_('Table'),
        required=True,
        ondelete='cascade'
    )

    # Dynamic Token (prevent QR code sharing)
    access_token = fields.Char(
        string=_('Access Token'),
        required=True,
        readonly=True,
        default=lambda self: secrets.token_urlsafe(32),
        copy=False,
        help=_('Client access token, regenerated on each scan')
    )

    # Session state
    state = fields.Selection([
        ('active', _('Active')),
        ('ordering', _('Ordering')),
        ('waiting', _('Waiting')),
        ('serving', _('Serving')),
        ('closed', _('Closed')),
    ], string=_('Status'), default='active', required=True)

    # Time control
    expire_time = fields.Datetime(
        string=_('Expire Time'),
        required=True,
        default=lambda self: fields.Datetime.now() + timedelta(hours=4),
        help=_('Session expire time, default 4 hours')
    )
    end_time = fields.Datetime(
        string=_('End Time'),
        readonly=True,
        help=_('Actual session end time')
    )

    # Client info
    client_ip = fields.Char(
        string=_('Client IP'),
        help=_('Client IP from first access')
    )
    user_agent = fields.Char(
        string=_('User Agent')
    )

    # Related orders
    order_ids = fields.One2many(
        'qr.order',
        'session_id',
        string=_('Orders')
    )
    order_count = fields.Integer(
        string=_('Order Count'),
        compute='_compute_order_count'
    )

    # Total amount
    total_amount = fields.Float(
        string=_('Total Amount'),
        compute='_compute_total_amount',
        store=True
    )

    _sql_constraints = [
        ('access_token_unique', 'unique(access_token)', 'Access token must be unique!'),
    ]

    @api.model
    def _generate_session_id(self):
        """Generate session ID"""
        return f"QRS-{fields.Datetime.now().strftime('%Y%m%d%H%M%S')}-{secrets.token_hex(4).upper()}"

    def _compute_order_count(self):
        """Compute order count"""
        for record in self:
            record.order_count = len(record.order_ids)

    @api.depends('order_ids.total_amount')
    def _compute_total_amount(self):
        """Compute total amount"""
        for record in self:
            record.total_amount = sum(record.order_ids.mapped('total_amount'))

    def action_close(self):
        """Close session"""
        for record in self:
            record.state = 'closed'
            record.end_time = fields.Datetime.now()

            # Clear table's current session reference
            if record.table_id.current_session_id == record:
                record.table_id.current_session_id = False
                # If no pending orders, set table state to available
                if not record.order_ids.filtered(lambda o: o.state not in ['cancelled', 'paid']):
                    record.table_id.state = 'available'
                    _logger.info(f"QR session closed for table {record.table_id.name}")
        return True

    def action_extend(self, hours=2):
        """Extend session validity"""
        for record in self:
            record.expire_time = fields.Datetime.now() + timedelta(hours=hours)
        return True

    @api.model
    def validate_access(self, table_token, access_token, client_ip=None):
        """
        Validate access permission
        Returns: (session, error_code, error_message)

        Multi-person ordering support:
        - Same table can have multiple people ordering simultaneously
        - Everyone shares the same session (current_session_id)
        - access_token is used to identify different clients but doesn't block new clients
        """
        # Find table
        table = self.env['qr.table'].sudo().search([
            ('qr_token', '=', table_token),
            ('active', '=', True)
        ], limit=1)

        if not table:
            return None, 'TABLE_NOT_FOUND', _('Table not found or disabled')

        # Check if table has active session
        if table.current_session_id and table.current_session_id.state != 'closed':
            current_session = table.current_session_id

            # Check if session expired
            if current_session.expire_time < fields.Datetime.now():
                current_session.action_close()
                # Session expired, create new session
                return self._create_new_session(table, client_ip)

            # If access_token provided, verify if it matches
            if access_token:
                if current_session.access_token == access_token:
                    # Token matches, return existing session
                    return current_session, None, None

            # Multi-person ordering: allow new client to join existing session
            _logger.info(f"New client joined existing session {current_session.name} for table {table.name}")
            return current_session, None, None

        # No active session, create new session
        return self._create_new_session(table, client_ip)

    def _create_new_session(self, table, client_ip=None):
        """Create new ordering session"""
        # Close table's old session
        if table.current_session_id and table.current_session_id.state != 'closed':
            # If has active orders, don't allow creating new session
            if table.current_session_id.order_ids.filtered(lambda o: o.state not in ['cancelled', 'paid']):
                return None, 'TABLE_HAS_ORDERS', _('Table has unfinished orders, please contact staff')
            table.current_session_id.action_close()

        # Create new session
        session = self.sudo().create({
            'table_id': table.id,
            'client_ip': client_ip,
        })

        # Update table state
        table.sudo().write({
            'state': 'occupied',
            'current_session_id': session.id,
        })

        _logger.info(f"Created QR session {session.name} for table {table.name}")

        return session, None, None

    @api.model
    def cleanup_expired_sessions(self):
        """Scheduled task: cleanup expired sessions"""
        expired = self.search([
            ('state', 'not in', ['closed']),
            ('expire_time', '<', fields.Datetime.now()),
        ])
        for session in expired:
            _logger.info(f"Closing expired session: {session.name}")
            session.action_close()
        return True
