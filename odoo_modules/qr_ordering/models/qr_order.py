# -*- coding: utf-8 -*-

import secrets
import hashlib
import json
import base64
from datetime import datetime, timedelta
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

import logging
_logger = logging.getLogger(__name__)


class QrOrder(models.Model):
    """QR Code Order Model"""
    _name = 'qr.order'
    _description = _('QR Order')
    _order = 'create_date desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(
        string=_('Order Number'),
        required=True,
        readonly=True,
        default=lambda self: self._generate_order_number(),
        copy=False,
        tracking=True
    )

    # Relations
    session_id = fields.Many2one(
        'qr.session',
        string=_('Session'),
        required=True,
        ondelete='cascade'
    )
    table_id = fields.Many2one(
        'qr.table',
        string=_('Table'),
        related='session_id.table_id',
        store=True,
        readonly=True
    )
    pos_config_id = fields.Many2one(
        'pos.config',
        string=_('POS Config'),
        related='table_id.pos_config_id',
        store=True,
        readonly=True
    )
    pos_order_id = fields.Many2one(
        'pos.order',
        string=_('POS Order'),
        readonly=True,
        help=_('Order after syncing to POS system')
    )
    pos_session_id = fields.Many2one(
        'pos.session',
        string=_('POS Session'),
        readonly=True,
        help=_('Related POS session')
    )
    restaurant_table_id = fields.Many2one(
        'restaurant.table',
        string=_('Restaurant Table'),
        related='table_id.pos_table_id',
        store=True,
        readonly=True,
        help=_('Table in POS system')
    )
    partner_id = fields.Many2one(
        'res.partner',
        string=_('Customer'),
        help=_('Related customer (optional)')
    )
    source = fields.Selection([
        ('qr', _('QR Code')),
        ('pos', _('POS')),
        ('kiosk', _('Kiosk')),
    ], string=_('Source'), default='qr', readonly=True)

    # Order state
    state = fields.Selection([
        ('cart', _('Cart')),
        ('ordered', _('Ordered')),
        ('cooking', _('Cooking')),
        ('serving', _('Serving')),
        ('paid', _('Paid')),
        ('cancelled', _('Cancelled')),
    ], string=_('Status'), default='cart', required=True, tracking=True)

    # Order lines
    line_ids = fields.One2many(
        'qr.order.line',
        'order_id',
        string=_('Order Lines')
    )

    # Amount
    total_amount = fields.Float(
        string=_('Total Amount'),
        compute='_compute_totals',
        store=True,
        tracking=True
    )
    total_qty = fields.Float(
        string=_('Total Quantity'),
        compute='_compute_totals',
        store=True
    )

    # Note
    note = fields.Text(
        string=_('Note'),
        help=_('Customer special requests')
    )

    # Time records
    order_time = fields.Datetime(
        string=_('Order Time'),
        readonly=True
    )
    cooking_time = fields.Datetime(
        string=_('Cooking Start'),
        readonly=True
    )
    serve_time = fields.Datetime(
        string=_('Serve Time'),
        readonly=True
    )

    # Idempotency control (prevent duplicate submission)
    print_idempotency_key = fields.Char(
        string='Print Idempotency Key',
        readonly=True,
        copy=False,
        index=True,
        help=_('Idempotency key to prevent duplicate printing, format: {qr_order_id}_{revision}')
    )
    print_revision = fields.Integer(
        string='Print Revision',
        default=0,
        readonly=True,
        help=_('Print version number, +1 for each additional order')
    )
    last_print_time = fields.Datetime(
        string=_('Last Print Time'),
        readonly=True
    )

    @api.model
    def _generate_order_number(self):
        """Generate order number"""
        return f"QRO-{fields.Datetime.now().strftime('%Y%m%d%H%M%S')}-{secrets.token_hex(2).upper()}"

    @api.depends('line_ids.subtotal', 'line_ids.qty')
    def _compute_totals(self):
        """Compute total amount and quantity"""
        for record in self:
            record.total_amount = sum(record.line_ids.mapped('subtotal'))
            record.total_qty = sum(record.line_ids.mapped('qty'))

    def action_submit_order(self):
        """
        Submit order

        Returns: dict
        - success: True/False
        - error_code: Error code
        - error_message: Error message
        """
        self.ensure_one()

        if self.state != 'cart':
            return {
                'success': False,
                'error_code': 'INVALID_STATE',
                'error_message': _('Can only submit cart orders')
            }
        if not self.line_ids:
            return {
                'success': False,
                'error_code': 'EMPTY_ORDER',
                'error_message': _('Order cannot be empty')
            }

        # First update state to ordered
        self.write({
            'state': 'ordered',
            'order_time': fields.Datetime.now(),
        })

        # Sync to POS (includes POS Session validation, KDS notification, kitchen printing)
        success, error_code, error_message = self._sync_to_pos()
        if not success:
            # Sync failed, rollback state
            self.write({'state': 'cart', 'order_time': False})
            return {
                'success': False,
                'error_code': error_code,
                'error_message': error_message
            }

        # Send realtime notification to client
        self._send_notification('order_submitted')

        # Auto transition to cooking
        self.write({
            'state': 'cooking',
            'cooking_time': fields.Datetime.now(),
        })

        return {'success': True}

    def action_add_items(self, lines_data):
        """
        Add items function
        lines_data: [{'product_id': x, 'qty': y, 'note': z}, ...]
        """
        self.ensure_one()
        if self.state not in ['cooking', 'serving']:
            raise UserError(_('Current state does not allow adding items'))

        # Get current max batch number
        max_batch = max(self.line_ids.mapped('batch_number') or [0])
        new_batch = max_batch + 1

        # Create new order lines
        for line_data in lines_data:
            self.env['qr.order.line'].create({
                'order_id': self.id,
                'product_id': line_data['product_id'],
                'qty': line_data.get('qty', 1),
                'note': line_data.get('note', ''),
                'batch_number': new_batch,
            })

        # Sync added items to POS (includes KDS and printing)
        self._sync_add_items_to_pos(new_batch)

        return True

    def _sync_to_pos(self):
        """
        Sync order to POS system

        Returns: (success, error_code, error_message)
        - success: True/False
        - error_code: Error code (e.g. 'NO_POS_SESSION')
        - error_message: User-friendly error message

        Idempotency guarantee:
        - Generate idempotency_key = {qr_order_id}_{revision}
        - If same key exists and already printed, skip printing
        """
        self.ensure_one()

        # 0. Idempotency check - generate current version idempotency_key
        new_revision = self.print_revision + 1
        new_idempotency_key = f"{self.id}_{new_revision}"

        # Check if this version already processed
        if self.print_idempotency_key == new_idempotency_key:
            _logger.info(f"Order {self.name} already processed with key {new_idempotency_key}, skipping duplicate")
            return True, None, None

        # 1. Validate POS Session
        pos_session = self._get_active_pos_session()
        if not pos_session:
            _logger.warning(f"No active POS session for order {self.name}, config: {self.pos_config_id.name}")
            return False, 'NO_POS_SESSION', _('POS not opened, please contact staff to start POS system')

        # 2. Check if table already has draft POS order (for merging)
        restaurant_table = self.table_id.pos_table_id
        existing_pos_order = None
        if restaurant_table:
            existing_pos_order = self.env['pos.order'].sudo().search([
                ('table_id', '=', restaurant_table.id),
                ('session_id', '=', pos_session.id),
                ('state', '=', 'draft'),
            ], limit=1, order='id desc')

        if existing_pos_order:
            # 3a. Append order lines to existing POS order
            _logger.info(f"Found existing POS order {existing_pos_order.name} for table {restaurant_table.table_number}, appending lines")
            self._append_lines_to_pos_order(existing_pos_order, pos_session)
            pos_order = existing_pos_order
        else:
            # 3b. Create new POS order
            order_data = self._prepare_pos_order_data(pos_session)
            _logger.info(f"Creating new POS order for QR Order {self.name}")
            pos_order = self.env['pos.order'].create(order_data)
            _logger.info(f"Created POS Order {pos_order.name} for QR Order {self.name}")

        # 4. Update QR order POS relation and idempotency fields
        self.write({
            'pos_order_id': pos_order.id,
            'pos_session_id': pos_session.id,
            'print_revision': new_revision,
            'print_idempotency_key': new_idempotency_key,
            'last_print_time': fields.Datetime.now(),
        })

        # 5. Create KDS change record and send notification
        self._create_kds_change(pos_order)

        # 6. Send print notification to POS frontend
        # Print agent runs on POS host, only POS frontend can trigger actual printing
        self._send_print_notification(pos_order)

        _logger.info(f"QR Order {self.name} synced to POS Order {pos_order.name} with idempotency_key {new_idempotency_key}")
        return True, None, None

    def _append_lines_to_pos_order(self, pos_order, pos_session):
        """Append current QR order product lines to existing POS order"""
        for line in self.line_ids:
            product = line.product_id
            # Get product tax configuration
            fiscal_position = pos_session.config_id.default_fiscal_position_id
            taxes = product.taxes_id.filtered(lambda t: t.company_id == pos_session.company_id)
            if fiscal_position:
                taxes = fiscal_position.map_tax(taxes)

            # Calculate tax-inclusive/exclusive prices
            price_unit = line.price_unit
            if taxes:
                tax_result = taxes.compute_all(
                    price_unit,
                    currency=pos_session.currency_id,
                    quantity=line.qty,
                    product=product,
                )
                price_subtotal = tax_result['total_excluded']
                price_subtotal_incl = tax_result['total_included']
            else:
                price_subtotal = price_unit * line.qty
                price_subtotal_incl = price_subtotal

            self.env['pos.order.line'].create({
                'order_id': pos_order.id,
                'product_id': product.id,
                'qty': line.qty,
                'price_unit': price_unit,
                'price_subtotal': price_subtotal,
                'price_subtotal_incl': price_subtotal_incl,
                'full_product_name': product.name,
                'customer_note': f"[QR:{self.name}] {line.note or ''}",
                'tax_ids': [(6, 0, taxes.ids)] if taxes else [],
                'skip_change': True,  # Mark as sent
            })

        # Recalculate POS order total
        pos_order._onchange_amount_all()
        _logger.info(f"Appended {len(self.line_ids)} lines to POS order {pos_order.name}")

    def _get_active_pos_session(self):
        """Get active POS session"""
        return self.env['pos.session'].search([
            ('config_id', '=', self.pos_config_id.id),
            ('state', '=', 'opened'),
        ], limit=1)

    def _prepare_pos_order_data(self, pos_session):
        """Prepare POS order data"""
        lines = []
        total_tax = 0.0
        total_amount = 0.0

        for line in self.line_ids:
            product = line.product_id
            # Get product tax configuration (using POS session fiscal position)
            fiscal_position = pos_session.config_id.default_fiscal_position_id
            taxes = product.taxes_id.filtered(lambda t: t.company_id == pos_session.company_id)
            if fiscal_position:
                taxes = fiscal_position.map_tax(taxes)

            # Calculate tax-inclusive/exclusive prices
            price_unit = line.price_unit
            if taxes:
                # Calculate tax
                tax_result = taxes.compute_all(
                    price_unit,
                    currency=pos_session.currency_id,
                    quantity=line.qty,
                    product=product,
                )
                price_subtotal = tax_result['total_excluded']
                price_subtotal_incl = tax_result['total_included']
                line_tax = price_subtotal_incl - price_subtotal
            else:
                price_subtotal = price_unit * line.qty
                price_subtotal_incl = price_subtotal
                line_tax = 0.0

            total_tax += line_tax
            total_amount += price_subtotal_incl

            lines.append((0, 0, {
                'product_id': product.id,
                'qty': line.qty,
                'price_unit': price_unit,
                'price_subtotal': price_subtotal,
                'price_subtotal_incl': price_subtotal_incl,
                'full_product_name': product.name,
                'customer_note': line.note or '',
                'tax_ids': [(6, 0, taxes.ids)] if taxes else [],
                'skip_change': True,  # Mark as sent, POS frontend won't show "send to kitchen" again
            }))

        # Generate pos_reference (format: QR-{session_id}-{sequence})
        # This field is called .includes() in POS frontend's _isSelfOrder method
        sequence = self.env['pos.order'].search_count([
            ('session_id', '=', pos_session.id)
        ]) + 1
        pos_reference = f"QR {pos_session.id:05d}-{sequence:04d}"

        return {
            'session_id': pos_session.id,
            'config_id': self.pos_config_id.id,
            'table_id': self.table_id.pos_table_id.id if self.table_id.pos_table_id else False,
            'pos_reference': pos_reference,
            'lines': lines,
            'amount_total': total_amount,
            'amount_tax': total_tax,
            'amount_paid': 0,
            'amount_return': 0,
            # Note: pos.order model doesn't have note field, note info stored in order line customer_note
        }

    def _sync_add_items_to_pos(self, batch_number):
        """
        Sync added items to POS

        Idempotency guarantee:
        - Each add generates new revision
        - idempotency_key = {qr_order_id}_{revision}
        """
        self.ensure_one()
        if not self.pos_order_id:
            _logger.warning(f"No POS order linked for QR order {self.name}")
            return False

        # Idempotency check - generate new version idempotency_key
        new_revision = self.print_revision + 1
        new_idempotency_key = f"{self.id}_{new_revision}"

        # Check if this version already processed (prevent duplicate add item printing)
        if self.print_idempotency_key == new_idempotency_key:
            _logger.info(f"Add items for order {self.name} already processed with key {new_idempotency_key}, skipping duplicate")
            return True

        pos_session = self.pos_order_id.session_id
        # Get new batch order lines
        new_lines = self.line_ids.filtered(lambda l: l.batch_number == batch_number)

        for line in new_lines:
            product = line.product_id
            # Get product tax configuration
            fiscal_position = pos_session.config_id.default_fiscal_position_id
            taxes = product.taxes_id.filtered(lambda t: t.company_id == pos_session.company_id)
            if fiscal_position:
                taxes = fiscal_position.map_tax(taxes)

            # Calculate tax-inclusive/exclusive prices
            price_unit = line.price_unit
            if taxes:
                tax_result = taxes.compute_all(
                    price_unit,
                    currency=pos_session.currency_id,
                    quantity=line.qty,
                    product=product,
                )
                price_subtotal = tax_result['total_excluded']
                price_subtotal_incl = tax_result['total_included']
            else:
                price_subtotal = price_unit * line.qty
                price_subtotal_incl = price_subtotal

            self.env['pos.order.line'].create({
                'order_id': self.pos_order_id.id,
                'product_id': product.id,
                'qty': line.qty,
                'price_unit': price_unit,
                'price_subtotal': price_subtotal,
                'price_subtotal_incl': price_subtotal_incl,
                'full_product_name': product.name,
                'customer_note': f"[Add Batch {batch_number}] {line.note or ''}",
                'tax_ids': [(6, 0, taxes.ids)] if taxes else [],
                'skip_change': True,  # Mark as sent
            })

        # Update POS order total (will auto recalculate tax)
        self.pos_order_id._onchange_amount_all()

        # Update idempotency fields
        self.write({
            'print_revision': new_revision,
            'print_idempotency_key': new_idempotency_key,
            'last_print_time': fields.Datetime.now(),
        })

        # Create KDS change record (only includes new batch products)
        self._create_kds_change_for_batch(self.pos_order_id, new_lines)

        # Send print notification to POS frontend (print agent on POS host)
        self._send_print_notification_for_batch(self.pos_order_id, new_lines)

        _logger.info(f"Added {len(new_lines)} items (batch {batch_number}) to POS order {self.pos_order_id.name} with idempotency_key {new_idempotency_key}")
        return True

    def _create_kds_change_for_batch(self, pos_order, lines):
        """Create KDS change record for specified order lines"""
        try:
            if 'ab_pos.order.change' not in self.env:
                return

            existing_changes = self.env['ab_pos.order.change'].sudo().search([
                ('order_id', '=', pos_order.id)
            ])
            next_sequence = len(existing_changes) + 1

            change = self.env['ab_pos.order.change'].sudo().create({
                'order_id': pos_order.id,
                'sequence_number': next_sequence,
                'created_at': fields.Datetime.now(),
            })

            for line in lines:
                self.env['ab_pos.order.change.line'].sudo().create({
                    'change_id': change.id,
                    'product_id': line.product_id.id,
                    'qty': line.qty,
                    'note': line.note or '',
                    'state': 'cooking',
                })

            pos_order.sudo().note_order_change()
            _logger.info(f"Created KDS change #{next_sequence} for batch with {len(lines)} lines")

        except Exception as e:
            _logger.error(f"Failed to create KDS change for batch: {e}")

    def _create_kds_change(self, pos_order):
        """
        Create KDS change record and send notification
        This method simulates POS frontend's sendOrderInPreparationUpdateLastChange behavior
        """
        self.ensure_one()
        try:
            # Check if ab_pos.order.change model exists
            if 'ab_pos.order.change' not in self.env:
                _logger.warning("KDS module (ab_pos.order.change) not installed, skipping KDS notification")
                return

            # Calculate next sequence number
            existing_changes = self.env['ab_pos.order.change'].sudo().search([
                ('order_id', '=', pos_order.id)
            ])
            next_sequence = len(existing_changes) + 1

            # Create change record
            change = self.env['ab_pos.order.change'].sudo().create({
                'order_id': pos_order.id,
                'sequence_number': next_sequence,
                'created_at': fields.Datetime.now(),
            })

            # Create change line for each order line
            for line in self.line_ids:
                self.env['ab_pos.order.change.line'].sudo().create({
                    'change_id': change.id,
                    'product_id': line.product_id.id,
                    'qty': line.qty,
                    'note': line.note or '',
                    'state': 'cooking',
                })

            # Send KDS notification (through pos.order's note_order_change method)
            pos_order.sudo().note_order_change()

            _logger.info(f"Created KDS change #{next_sequence} for POS order {pos_order.name} with {len(self.line_ids)} lines")

        except Exception as e:
            _logger.error(f"Failed to create KDS change for order {self.name}: {e}")

    def _send_print_notification(self, pos_order):
        """
        Send print job to kitchen printer via ylhc_print_manager

        Completely independent from POS frontend, directly through Seisei Print Manager's print queue system
        Send to print agent (Seisei Service), agent executes actual printing

        Print flow:
        1. Find POS config related kitchen printers (pos.printer type cloud_printer)
        2. Get printer's related seisei.printer
        3. Generate receipt content (text format, converted to ESC/POS by print agent)
        4. Create seisei.print.job task
        5. Send to print agent via WebSocket
        """
        self.ensure_one()
        try:
            pos_config = pos_order.config_id
            if not pos_config:
                _logger.warning(f"No POS config for order {pos_order.name}")
                return

            # Find POS config's kitchen printers
            printers_sent = 0
            for printer in pos_config.printer_ids:
                # Check if cloud printer with related Seisei printer
                seisei_printer = None
                if hasattr(printer, 'seisei_printer_id') and printer.seisei_printer_id:
                    seisei_printer = printer.seisei_printer_id
                elif hasattr(printer, 'printer_type') and printer.printer_type == 'cloud_printer':
                    # Try to match seisei.printer by name
                    seisei_printer = self.env['seisei.printer'].sudo().search([
                        ('name', '=', printer.name),
                        ('active', '=', True),
                    ], limit=1)

                if seisei_printer:
                    self._create_kitchen_print_job(seisei_printer, pos_order, is_batch=False)
                    printers_sent += 1
                    _logger.info(f"Created print job for QR order {self.name} on printer {seisei_printer.name}")

            if printers_sent == 0:
                # No Seisei printer found, fallback to old method (notify POS frontend)
                self._send_print_notification_legacy(pos_order)
            else:
                _logger.info(f"Sent print jobs to {printers_sent} printer(s) for QR order {self.name}")

        except Exception as e:
            _logger.error(f"Failed to send print notification for order {self.name}: {e}")
            # Fallback to old method on error
            try:
                self._send_print_notification_legacy(pos_order)
            except Exception as e2:
                _logger.error(f"Legacy print notification also failed: {e2}")

    def _send_print_notification_legacy(self, pos_order):
        """
        Fallback method: Send print notification to POS frontend
        Used when no Seisei printer configured
        """
        pos_config = pos_order.config_id
        access_token = pos_config.access_token
        if not access_token:
            _logger.warning(f"POS config {pos_config.name} has no access_token, cannot send print notification")
            return

        # Prepare print data
        lines_data = []
        for line in self.line_ids:
            product = line.product_id
            categ = product.pos_categ_ids[:1] if product.pos_categ_ids else None
            lines_data.append({
                'product_id': product.id,
                'product_name': product.name,
                'qty': line.qty,
                'note': line.note or '',
                'categ_id': categ.id if categ else False,
                'categ_sequence': categ.sequence if categ else 0,
            })

        notification_data = {
            'order_id': pos_order.id,
            'order_name': pos_order.name,
            'config_id': pos_config.id,
            'table_id': pos_order.table_id.id if pos_order.table_id else False,
            'table_name': pos_order.table_id.table_number if pos_order.table_id else '',
            'qr_order_name': self.name,
            'lines': lines_data,
        }

        pos_config._notify('QR_ORDER_PRINT', notification_data)
        _logger.info(f"Sent legacy print notification to POS frontend for QR order {self.name}")

    def _create_kitchen_print_job(self, seisei_printer, pos_order, is_batch=False, qr_lines=None):
        """
        Create kitchen print job - using Seisei ticket template

        Args:
            seisei_printer: seisei.printer record
            pos_order: pos.order record
            is_batch: Whether batch printing for added items
            qr_lines: Order lines to print for batch (None prints all)
        """
        try:
            table_name = self.table_id.name if self.table_id else ''
            lines_to_print = qr_lines if qr_lines else self.line_ids
            # Use ESC/POS format consistent with KDS directly
            # Don't use Seisei ticket template, to ensure format matches POS KDS printing
            escpos_commands = self._generate_escpos_commands(pos_order, lines_to_print, is_batch)
            escpos_base64 = base64.b64encode(escpos_commands).decode('utf-8')

            # Create print job
            job_name = f'QR Add - {table_name} - {self.name}' if is_batch else f'QR Kitchen - {table_name} - {self.name}'
            job_vals = {
                'name': job_name,
                'printer_id': seisei_printer.id,
                'type': 'pos_receipt_print',
                'is_test': False,
                'metadata': json.dumps({
                    'escpos_commands': escpos_base64,
                    'doc_format': 'escpos',
                    'qr_order_id': self.id,
                    'qr_order_name': self.name,
                    'pos_order_id': pos_order.id,
                    'pos_order_name': pos_order.name,
                    'table_name': table_name,
                    'is_batch': is_batch,
                }),
            }

            job = self.env['seisei.print.job'].sudo().create(job_vals)
            job.action_process()

            _logger.info(f"Created kitchen print job {job.job_id} for QR order {self.name} on printer {seisei_printer.name}")
            return job

        except Exception as e:
            _logger.error(f"Failed to create kitchen print job: {e}")
            return None

    def _prepare_kitchen_template_data(self, pos_order, lines, is_batch=False):
        """
        Prepare kitchen ticket template data, format consistent with POS order
        """
        from datetime import datetime

        # Get order line data
        order_lines = []
        for line in lines:
            product = line.product_id
            order_lines.append({
                'product_name': product.name if product else getattr(line, 'product_name', 'Unknown'),
                'qty': line.qty,
                'price': 0,  # Kitchen ticket doesn't show price
                'note': getattr(line, 'note', '') or '',
            })

        # Build nested data structure, matching field paths in ticket_element.py
        template_data = {
            'order': {
                'name': pos_order.name,
                'date_order': datetime.now(),
                'user_id': {
                    'name': pos_order.employee_id.name if pos_order.employee_id else (
                        pos_order.user_id.name if pos_order.user_id else ''
                    ),
                },
                'table_id': {
                    'name': self.table_id.name if self.table_id else '',
                },
                'note': f"{'[Add]' if is_batch else ''} QR Order: {self.name}",
            },
            'lines': order_lines,
            'is_batch': is_batch,
            'qr_order_name': self.name,
        }

        return template_data

    def _generate_escpos_commands(self, pos_order, lines, is_batch=False):
        """
        Generate ESC/POS print commands - using image rendering (consistent with POS frontend)

        Flow:
        1. Render HTML template (consistent with POS OrderChangeReceipt format)
        2. Convert to image using wkhtmltoimage
        3. Convert image to ESC/POS bitmap commands
        """
        import subprocess
        import tempfile
        import os
        from PIL import Image
        import io

        # 1. Generate HTML content
        html_content = self._render_kitchen_ticket_html(pos_order, lines, is_batch)

        # 2. Convert to image using wkhtmltoimage
        try:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False, encoding='utf-8') as html_file:
                html_file.write(html_content)
                html_path = html_file.name

            img_path = html_path.replace('.html', '.png')

            # wkhtmltoimage params: width 384 pixels (suitable for 80mm thermal printer)
            result = subprocess.run([
                'wkhtmltoimage',
                '--width', '384',
                '--quality', '100',
                '--disable-smart-width',
                html_path,
                img_path
            ], capture_output=True, timeout=30)

            if result.returncode != 0:
                _logger.error(f"wkhtmltoimage failed: {result.stderr.decode()}")
                # Fallback to text mode
                return self._generate_escpos_commands_text(pos_order, lines, is_batch)

            # 3. Read image and convert to ESC/POS bitmap commands
            with Image.open(img_path) as img:
                escpos_commands = self._image_to_escpos(img)

            # Cleanup temp files
            os.unlink(html_path)
            os.unlink(img_path)

            return escpos_commands

        except Exception as e:
            _logger.error(f"Image rendering failed: {e}")
            # Fallback to text mode
            return self._generate_escpos_commands_text(pos_order, lines, is_batch)

    def _render_kitchen_ticket_html(self, pos_order, lines, is_batch=False):
        """
        Render kitchen ticket HTML (consistent with POS OrderChangeReceipt template format)
        """
        # Get data
        config_name = pos_order.config_id.name if pos_order.config_id else ''
        order_time = fields.Datetime.now().strftime('%H:%M')

        employee_name = ''
        if pos_order.employee_id:
            employee_name = pos_order.employee_id.name
        elif pos_order.user_id:
            employee_name = pos_order.user_id.name

        # Table number
        table_number = ''
        if self.table_id and hasattr(self.table_id, 'name'):
            table_number = self.table_id.name
        if hasattr(self, 'restaurant_table_id') and self.restaurant_table_id:
            rt = self.restaurant_table_id
            if hasattr(rt, 'table_number'):
                table_number = str(rt.table_number)

        # Tracking number
        tracking_number = ''
        if hasattr(pos_order, 'tracking_number') and pos_order.tracking_number:
            tracking_number = str(pos_order.tracking_number)

        # Product lines HTML
        lines_html = ''
        for line in lines:
            product = line.product_id
            product_name = product.name if product else getattr(line, 'product_name', 'Unknown')
            qty = int(line.qty)
            lines_html += '<div class="orderline">'
            lines_html += '<div class="line-content">'
            lines_html += '<span class="qty">' + str(qty) + '</span>'
            lines_html += '<span class="product-name">' + str(product_name) + '</span>'
            lines_html += '</div>'

            # Note
            if hasattr(line, 'note') and line.note:
                note_text = str(line.note).replace('\\n', ', ')
                lines_html += '<div class="note">' + note_text + '</div>'

            lines_html += '</div>'

        # Operation title
        op_title = "New"

        # Table display
        table_display = ""
        if table_number:
            table_display = "Table " + table_number
        if tracking_number:
            if table_display:
                table_display += " # " + tracking_number
            else:
                table_display = "# " + tracking_number

        # Complete HTML - using string concatenation to avoid f-string issues
        html = """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: "Microsoft YaHei", "SimHei", "Noto Sans CJK SC", sans-serif; width: 384px; background: white; color: black; padding: 10px; }
        .header { text-align: center; margin-bottom: 10px; }
        .title { font-size: 28px; font-weight: bold; margin-bottom: 5px; }
        .info { font-size: 14px; margin-bottom: 3px; }
        .table-info { font-size: 22px; font-weight: bold; margin: 10px 0; }
        .separator { border-top: 2px dashed black; margin: 10px 0; }
        .op-title { text-align: center; font-size: 18px; font-weight: bold; margin: 10px 0; }
        .orderline { margin: 8px 0; }
        .line-content { font-size: 20px; font-weight: bold; }
        .qty { margin-right: 15px; }
        .note { font-size: 14px; font-style: italic; margin-left: 30px; color: #333; }
    </style>
</head>
<body>
    <div class="header">
        <div class="title">Dine In</div>
        <div class="info">""" + config_name + ":" + order_time + """</div>
        <div class="info">By: """ + employee_name + """</div>
        <div class="table-info">""" + table_display + """</div>
    </div>
    <div class="separator"></div>
    <div class="op-title">""" + op_title + """</div>
    <div class="lines">
        """ + lines_html + """
    </div>
</body>
</html>"""
        return html

    def _image_to_escpos(self, img):
        """
        Convert PIL Image to ESC/POS bitmap commands
        Using GS v 0 command (consistent with POS frontend CloudPrinter)
        """
        # Convert to grayscale
        img = img.convert('L')

        # Floyd-Steinberg dithering to black and white
        img = img.convert('1')

        width, height = img.size
        pixels = list(img.getdata())

        # ESC/POS commands
        ESC = b'\x1b'
        GS = b'\x1d'

        commands = bytearray()

        # Initialize
        commands.extend(ESC + b'@')

        # Center align
        commands.extend(ESC + b'a\x01')

        # GS v 0 - Raster bitmap
        # Format: GS v 0 m xL xH yL yH [data]
        # m = 0: normal mode
        bytes_per_line = (width + 7) // 8

        xL = bytes_per_line & 0xFF
        xH = (bytes_per_line >> 8) & 0xFF
        yL = height & 0xFF
        yH = (height >> 8) & 0xFF

        commands.extend(GS + b'v0\x00')
        commands.append(xL)
        commands.append(xH)
        commands.append(yL)
        commands.append(yH)

        # Convert pixel data
        for y in range(height):
            for x_byte in range(bytes_per_line):
                byte_val = 0
                for bit in range(8):
                    x = x_byte * 8 + bit
                    if x < width:
                        pixel_index = y * width + x
                        # PIL '1' mode: 0=black, 255=white
                        # ESC/POS: 1=print(black), 0=no print(white)
                        if pixels[pixel_index] == 0:  # Black
                            byte_val |= (0x80 >> bit)
                commands.append(byte_val)

        # Feed 3 lines
        commands.extend(ESC + b'd\x03')

        # Partial cut
        commands.extend(GS + b'V\x01')

        return bytes(commands)

    def _generate_escpos_commands_text(self, pos_order, lines, is_batch=False):
        """
        Text mode ESC/POS commands (fallback for image rendering)
        """
        ESC = b'\x1b'
        GS = b'\x1d'

        INIT = ESC + b'@'
        ALIGN_CENTER = ESC + b'a\x01'
        ALIGN_LEFT = ESC + b'a\x00'
        BOLD_ON = ESC + b'E\x01'
        BOLD_OFF = ESC + b'E\x00'
        DOUBLE_HEIGHT = GS + b'!\x10'
        DOUBLE_SIZE = GS + b'!\x30'
        NORMAL_SIZE = GS + b'!\x00'
        FEED_LINES = ESC + b'd\x03'
        PARTIAL_CUT = GS + b'V\x01'

        def encode_text(text):
            try:
                return text.encode('gb18030')
            except:
                return text.encode('utf-8', errors='replace')

        commands = bytearray()
        commands.extend(INIT)

        # Title
        commands.extend(ALIGN_CENTER)
        commands.extend(DOUBLE_SIZE)
        commands.extend(BOLD_ON)
        commands.extend(encode_text("Dine In"))
        commands.extend(b'\n')
        commands.extend(NORMAL_SIZE)
        commands.extend(BOLD_OFF)

        # Config name + time
        config_name = pos_order.config_id.name if pos_order.config_id else ''
        order_time = fields.Datetime.now().strftime('%H:%M')
        commands.extend(encode_text(f"{config_name}:{order_time}"))
        commands.extend(b'\n')

        # Employee
        employee_name = pos_order.employee_id.name if pos_order.employee_id else (pos_order.user_id.name if pos_order.user_id else '')
        if employee_name:
            commands.extend(encode_text(f"By: {employee_name}"))
            commands.extend(b'\n')

        # Table number
        commands.extend(DOUBLE_HEIGHT)
        commands.extend(BOLD_ON)
        table_number = self.table_id.name if self.table_id else ''
        tracking_number = str(pos_order.tracking_number) if hasattr(pos_order, 'tracking_number') and pos_order.tracking_number else ''
        table_line = ''
        if table_number:
            table_line = f"Table {table_number}"
        if tracking_number:
            table_line += f" # {tracking_number}" if table_line else f"# {tracking_number}"
        if table_line:
            commands.extend(encode_text(table_line))
            commands.extend(b'\n')
        commands.extend(NORMAL_SIZE)
        commands.extend(BOLD_OFF)

        # Separator
        commands.extend(b'.' * 32 + b'\n')

        # New
        commands.extend(ALIGN_CENTER)
        commands.extend(BOLD_ON)
        commands.extend(b'New\n')
        commands.extend(BOLD_OFF)
        commands.extend(ALIGN_LEFT)

        # Products
        commands.extend(DOUBLE_HEIGHT)
        for line in lines:
            product_name = line.product_id.name if line.product_id else 'Unknown'
            commands.extend(encode_text(f"{int(line.qty)} {product_name}"))
            commands.extend(b'\n')
            if hasattr(line, 'note') and line.note:
                commands.extend(NORMAL_SIZE)
                commands.extend(encode_text(f"  {line.note}"))
                commands.extend(b'\n')
                commands.extend(DOUBLE_HEIGHT)
        commands.extend(NORMAL_SIZE)

        commands.extend(FEED_LINES)
        commands.extend(PARTIAL_CUT)

        return bytes(commands)

    def _get_change_sequence(self, pos_order):
        """Get order change sequence number"""
        if 'ab_pos.order.change' in self.env:
            changes = self.env['ab_pos.order.change'].sudo().search([
                ('order_id', '=', pos_order.id)
            ])
            return len(changes) + 1
        return 1

    def _format_two_columns(self, left, right, width=32):
        """Format two column text (left align + right align)"""
        left = str(left) if left else ''
        right = str(right) if right else ''
        # Calculate Chinese character width (each Chinese char takes 2 positions)
        left_width = sum(2 if ord(c) > 127 else 1 for c in left)
        right_width = sum(2 if ord(c) > 127 else 1 for c in right)
        spaces = max(1, width - left_width - right_width)
        return left + ' ' * spaces + right

    def _append_order_line(self, commands, line, is_canceled=False):
        """Add order line to print commands"""
        product = line.product_id
        product_name = product.name or ''
        qty = abs(int(line.qty) if line.qty == int(line.qty) else line.qty)

        # Format: qty + product name (consistent with KDS)
        line_text = f'{qty}   {product_name}\n'
        commands.extend(line_text.encode('gbk', errors='replace'))

        # Product attributes (TYPE) - if any
        if hasattr(product, 'attribute_line_ids') and product.attribute_line_ids:
            attr_names = []
            for attr_line in product.attribute_line_ids:
                if attr_line.value_ids:
                    attr_names.extend([v.name for v in attr_line.value_ids])
            if attr_names:
                commands.extend(f'TYPE: {", ".join(attr_names)}\n'.encode('gbk', errors='replace'))

        # Note (NOTE) - separate line
        if line.note:
            commands.extend(f'NOTE: {line.note}\n'.encode('gbk', errors='replace'))

    def _generate_receipt_data(self, pos_order, lines, is_batch=False):
        """
        Generate receipt data (structured JSON) - unified KDS template format

        Data structure consistent with POS KDS (OrderChangePrint.vue)
        Print agent (Seisei Service) will generate actual ESC/POS commands from this data
        """
        table_name = self.table_id.name if self.table_id else ''

        # Get change sequence number
        change_seq = self._get_change_sequence(pos_order)
        change_name = f'Order-{change_seq:03d}'

        # Order UID
        order_uid = pos_order.pos_reference or pos_order.name or self.name

        # Customer info
        partner = pos_order.partner_id if pos_order.partner_id else None
        customer_info = None
        if partner:
            customer_info = {
                'name': partner.name or '',
                'phone': partner.phone or '',
                'email': partner.email or '',
                'comment': partner.comment or '',
            }

        # Delivery address
        service_type = getattr(pos_order, 'ab_service_type', None)
        delivery_address = None
        if partner and service_type == 'delivery':
            if partner.street or partner.city or partner.zip:
                delivery_address = {
                    'street': partner.street or '',
                    'city': partner.city or '',
                    'zip': partner.zip or '',
                }

        # Build order line info - grouped as CANCELED and ORDERED
        canceled_lines = []
        ordered_lines = []

        for line in lines:
            product = line.product_id
            categ = product.pos_categ_ids[:1] if product.pos_categ_ids else None

            # Get product attribute values
            attr_values = []
            if hasattr(product, 'attribute_line_ids') and product.attribute_line_ids:
                for attr_line in product.attribute_line_ids:
                    if attr_line.value_ids:
                        attr_values.extend([v.name for v in attr_line.value_ids])

            line_info = {
                'product_id': product.id,
                'product_name': product.name,
                'display_name': product.display_name or product.name,
                'qty': abs(line.qty),
                'note': line.note or '',
                'state': line.state,
                'attribute_values': attr_values,
                'categ_id': categ.id if categ else False,
                'categ_name': categ.name if categ else '',
            }

            if line.qty <= 0 or line.state == 'cancelled':
                canceled_lines.append(line_info)
            else:
                ordered_lines.append(line_info)

        return {
            'source': 'qr_ordering',
            'print_type': 'kitchen_ticket',
            'template_version': 'kds_unified',  # Mark using unified KDS template

            # Order change info (consistent with KDS)
            'change_name': change_name,
            'change_sequence': change_seq,

            # Order info
            'order_uid': order_uid,
            'qr_order_id': self.id,
            'qr_order_name': self.name,
            'pos_order_id': pos_order.id,
            'pos_order_name': pos_order.name,

            # Table info
            'table_id': self.table_id.id if self.table_id else False,
            'table_name': table_name,

            # Time info
            'order_time': fields.Datetime.now().strftime('%H:%M'),
            'order_datetime': fields.Datetime.now().strftime('%Y-%m-%d %H:%M:%S'),

            # Customer info (consistent with KDS)
            'customer': customer_info,
            'service_type': service_type,
            'delivery_address': delivery_address,

            # Product lines - grouped (consistent with KDS)
            'canceled_lines': canceled_lines,
            'ordered_lines': ordered_lines,

            # Compatible with old format
            'lines': ordered_lines + canceled_lines,
            'line_count': len(ordered_lines) + len(canceled_lines),
            'total_qty': sum(l['qty'] for l in ordered_lines),

            # Note
            'note': self.note or '',

            # Receipt format config
            'receipt_config': {
                'show_price': False,  # Kitchen ticket doesn't show price
                'show_total': False,
                'paper_width': '80mm',
                'auto_cut': True,
            }
        }

    def _send_print_notification_for_batch(self, pos_order, qr_lines):
        """
        Send batch add items print job to kitchen printer

        Through ylhc_print_manager, similar to _send_print_notification
        But marked as is_batch=True, ticket title shows "Add Items"
        """
        self.ensure_one()
        try:
            pos_config = pos_order.config_id
            if not pos_config:
                _logger.warning(f"No POS config for order {pos_order.name}")
                return

            # Find POS config's kitchen printers
            printers_sent = 0
            for printer in pos_config.printer_ids:
                seisei_printer = None
                if hasattr(printer, 'seisei_printer_id') and printer.seisei_printer_id:
                    seisei_printer = printer.seisei_printer_id
                elif hasattr(printer, 'printer_type') and printer.printer_type == 'cloud_printer':
                    seisei_printer = self.env['seisei.printer'].sudo().search([
                        ('name', '=', printer.name),
                        ('active', '=', True),
                    ], limit=1)

                if seisei_printer:
                    self._create_kitchen_print_job(seisei_printer, pos_order, is_batch=True, qr_lines=qr_lines)
                    printers_sent += 1

            if printers_sent == 0:
                # Fallback to old method
                self._send_print_notification_for_batch_legacy(pos_order, qr_lines)
            else:
                _logger.info(f"Sent batch print jobs to {printers_sent} printer(s) for QR order {self.name}")

        except Exception as e:
            _logger.error(f"Failed to send batch print notification: {e}")
            try:
                self._send_print_notification_for_batch_legacy(pos_order, qr_lines)
            except Exception as e2:
                _logger.error(f"Legacy batch print notification also failed: {e2}")

    def _send_print_notification_for_batch_legacy(self, pos_order, qr_lines):
        """
        Fallback method: Send batch add items print notification to POS frontend
        """
        pos_config = pos_order.config_id
        access_token = pos_config.access_token
        if not access_token:
            _logger.warning(f"POS config {pos_config.name} has no access_token")
            return

        lines_data = []
        for line in qr_lines:
            product = line.product_id
            categ = product.pos_categ_ids[:1] if product.pos_categ_ids else None
            lines_data.append({
                'product_id': product.id,
                'product_name': product.name,
                'qty': line.qty,
                'note': line.note or '',
                'categ_id': categ.id if categ else False,
                'categ_sequence': categ.sequence if categ else 0,
            })

        notification_data = {
            'order_id': pos_order.id,
            'order_name': pos_order.name,
            'config_id': pos_config.id,
            'table_id': pos_order.table_id.id if pos_order.table_id else False,
            'table_name': pos_order.table_id.table_number if pos_order.table_id else '',
            'qr_order_name': self.name,
            'is_batch': True,
            'lines': lines_data,
        }

        pos_config._notify('QR_ORDER_PRINT', notification_data)
        _logger.info(f"Sent legacy batch print notification for QR order {self.name}")

    def _send_notification(self, event_type):
        """Send realtime notification"""
        self.ensure_one()
        # Send notification via Odoo Bus
        channel = f'qr_order_{self.session_id.access_token}'
        self.env['bus.bus']._sendone(channel, 'qr_order_update', {
            'event': event_type,
            'order_id': self.id,
            'order_name': self.name,
            'state': self.state,
            'total_amount': self.total_amount,
        })


class QrOrderLine(models.Model):
    """QR Order Line"""
    _name = 'qr.order.line'
    _description = _('QR Order Line')
    _order = 'batch_number, sequence, id'

    order_id = fields.Many2one(
        'qr.order',
        string=_('Order'),
        required=True,
        ondelete='cascade'
    )
    sequence = fields.Integer(
        string=_('Sequence'),
        default=10
    )

    # Product info
    product_id = fields.Many2one(
        'product.product',
        string=_('Product'),
        required=True,
        domain=[('available_in_pos', '=', True)]
    )
    product_name = fields.Char(
        string=_('Product Name'),
        related='product_id.name',
        readonly=True
    )

    # Quantity and price
    qty = fields.Float(
        string=_('Quantity'),
        default=1,
        required=True
    )
    price_unit = fields.Float(
        string=_('Unit Price'),
        compute='_compute_price',
        store=True
    )
    subtotal = fields.Float(
        string=_('Subtotal'),
        compute='_compute_price',
        store=True
    )

    # Batch (distinguish first order and additional items)
    batch_number = fields.Integer(
        string=_('Batch'),
        default=1,
        help=_('Batch number: 1=first order, 2+=additional items')
    )

    # Note
    note = fields.Char(
        string=_('Note'),
        help=_('Special requests: less spicy, no cilantro, etc.')
    )

    # State
    state = fields.Selection([
        ('pending', _('Pending')),
        ('submitted', _('Submitted')),
        ('cooking', _('Cooking')),
        ('served', _('Served')),
        ('cancelled', _('Cancelled')),
    ], string=_('Status'), default='pending')

    @api.depends('product_id', 'qty')
    def _compute_price(self):
        """Compute price"""
        for line in self:
            if line.product_id:
                line.price_unit = line.product_id.lst_price
                line.subtotal = line.price_unit * line.qty
            else:
                line.price_unit = 0
                line.subtotal = 0
