# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import UserError
import logging
import json

_logger = logging.getLogger(__name__)


class PosPrintJob(models.Model):
    """POS 打印任务模型 - 用于 QR 订单的打印任务管理"""
    _name = 'pos.print.job'
    _description = 'POS Print Job / POS 打印任务'
    _order = 'create_date desc'

    name = fields.Char(
        string='Job Name / 任务名称',
        required=True,
        readonly=True,
        default=lambda self: self._generate_job_name(),
        copy=False
    )
    
    # 关联
    pos_config_id = fields.Many2one(
        'pos.config',
        string='POS Config / POS配置',
        required=True,
        index=True,
        help='关联的 POS 配置'
    )
    pos_order_id = fields.Many2one(
        'pos.order',
        string='POS Order / POS订单',
        readonly=True,
        help='关联的 POS 订单（如果有）'
    )
    qr_order_id = fields.Many2one(
        'qr.order',
        string='QR Order / QR订单',
        readonly=True,
        help='关联的 QR 订单'
    )
    
    # 任务状态
    state = fields.Selection([
        ('pending', 'Pending / 待打印'),
        ('printing', 'Printing / 打印中'),
        ('done', 'Done / 已完成'),
        ('failed', 'Failed / 失败'),
        ('cancelled', 'Cancelled / 已取消'),
    ], string='Status / 状态', default='pending', required=True, index=True)
    
    # 打印数据
    print_payload = fields.Text(
        string='Print Payload / 打印数据',
        required=True,
        help='JSON 格式的打印数据，与 POS 点餐打印格式一致'
    )
    
    # 打印信息
    printer_name = fields.Char(
        string='Printer Name / 打印机名称',
        help='目标打印机名称'
    )
    print_type = fields.Selection([
        ('order', 'Order / 订单'),
        ('kitchen', 'Kitchen / 厨房单'),
        ('receipt', 'Receipt / 小票'),
    ], string='Print Type / 打印类型', default='order', required=True)
    
    # 执行信息
    claimed_by = fields.Char(
        string='Claimed By / 被认领',
        help='认领该任务的 POS 客户端标识（IP/主机名）'
    )
    claimed_at = fields.Datetime(
        string='Claimed At / 认领时间',
        readonly=True
    )
    printed_at = fields.Datetime(
        string='Printed At / 打印时间',
        readonly=True
    )
    error_message = fields.Text(
        string='Error Message / 错误信息',
        help='如果打印失败，记录错误信息'
    )
    retry_count = fields.Integer(
        string='Retry Count / 重试次数',
        default=0,
        help='重试次数'
    )
    
    # 追踪
    trace_id = fields.Char(
        string='Trace ID / 追踪ID',
        help='用于追踪和调试'
    )

    _sql_constraints = [
        ('name_unique', 'unique(name)', 'Job name must be unique!'),
    ]

    @api.model
    def _generate_job_name(self):
        """生成任务名称"""
        return f"PRINT-{fields.Datetime.now().strftime('%Y%m%d%H%M%S')}-{self.env['ir.sequence'].next_by_code('pos.print.job') or '0000'}"

    def action_claim(self, client_id):
        """
        认领打印任务（原子操作）
        返回: (success, error_message)
        """
        self.ensure_one()
        
        # 使用 SQL 原子更新，确保只有一个客户端能认领
        self.env.cr.execute("""
            UPDATE pos_print_job
            SET state = 'printing',
                claimed_by = %s,
                claimed_at = NOW()
            WHERE id = %s
            AND state = 'pending'
            RETURNING id
        """, (client_id, self.id))
        
        result = self.env.cr.fetchone()
        
        if result:
            self.env.cr.commit()
            self.invalidate_recordset(['state', 'claimed_by', 'claimed_at'])
            _logger.info(f"Job {self.name} claimed by {client_id}")
            return True, None
        else:
            # 任务已被其他客户端认领或状态已改变
            return False, 'Job already claimed or status changed'

    def action_mark_done(self):
        """标记任务完成"""
        self.ensure_one()
        self.write({
            'state': 'done',
            'printed_at': fields.Datetime.now(),
        })
        _logger.info(f"Job {self.name} marked as done")

    def action_mark_failed(self, error_message):
        """标记任务失败"""
        self.ensure_one()
        self.write({
            'state': 'failed',
            'error_message': error_message,
            'retry_count': self.retry_count + 1,
        })
        _logger.warning(f"Job {self.name} marked as failed: {error_message}")

    def action_retry(self):
        """重试任务"""
        self.ensure_one()
        if self.state not in ['failed', 'cancelled']:
            raise UserError('只能重试失败或已取消的任务')
        
        self.write({
            'state': 'pending',
            'claimed_by': False,
            'claimed_at': False,
            'error_message': False,
        })
        _logger.info(f"Job {self.name} retried")

    @api.model
    def get_pending_jobs(self, pos_config_id, limit=10):
        """获取待打印任务列表"""
        return self.search([
            ('pos_config_id', '=', pos_config_id),
            ('state', '=', 'pending'),
        ], limit=limit, order='create_date asc')

    @api.model
    def create_job_from_qr_order(self, qr_order, print_type='order'):
        """
        从 QR 订单创建打印任务
        
        Args:
            qr_order: qr.order 记录
            print_type: 打印类型（order/kitchen/receipt）
        
        Returns:
            pos.print.job 记录
        """
        # 获取 POS 订单（如果已同步）
        pos_order = qr_order.pos_order_id
        
        # 准备打印 payload（需要与 POS 点餐打印格式一致）
        # TODO: 这里需要根据实际的 YLHC Recorder payload 格式来构建
        print_payload = self._prepare_print_payload(qr_order, pos_order, print_type)
        
        job = self.create({
            'pos_config_id': qr_order.pos_config_id.id,
            'pos_order_id': pos_order.id if pos_order else False,
            'qr_order_id': qr_order.id,
            'print_type': print_type,
            'print_payload': json.dumps(print_payload, ensure_ascii=False),
            'printer_name': self._get_printer_name(qr_order.pos_config_id, print_type),
            'trace_id': f"QR-{qr_order.name}",
        })
        
        _logger.info(f"Created print job {job.name} for QR order {qr_order.name}")
        return job

    def _prepare_print_payload(self, qr_order, pos_order, print_type):
        """
        准备打印 payload
        需要与 POS 点餐打印格式一致
        """
        # 基础订单信息
        payload = {
            'order_id': pos_order.id if pos_order else None,
            'order_name': qr_order.name,
            'table_name': qr_order.table_id.name if qr_order.table_id else '',
            'order_time': qr_order.order_time.isoformat() if qr_order.order_time else None,
            'total_amount': qr_order.total_amount,
            'note': qr_order.note or '',
        }
        
        # 订单行
        lines = []
        for line in qr_order.line_ids:
            lines.append({
                'product_name': line.product_name,
                'qty': line.qty,
                'price_unit': line.price_unit,
                'subtotal': line.subtotal,
                'note': line.note or '',
            })
        payload['lines'] = lines
        
        # 根据打印类型添加额外信息
        if print_type == 'kitchen':
            # 厨房单可能需要额外信息
            payload['kitchen_note'] = qr_order.note or ''
        
        return payload

    def _get_printer_name(self, pos_config, print_type):
        """
        获取打印机名称
        需要根据 POS 配置和打印类型确定
        """
        # TODO: 从 POS 配置或系统参数中获取打印机名称
        # 这里先返回默认值
        if print_type == 'kitchen':
            return 'kitchen_printer'
        elif print_type == 'receipt':
            return 'receipt_printer'
        else:
            return 'order_printer'



