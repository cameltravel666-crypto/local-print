# -*- coding: utf-8 -*-

from odoo import http
from odoo.http import request
import logging
import json

_logger = logging.getLogger(__name__)


class PosPrintController(http.Controller):
    """POS 打印任务控制器 - 供 POS 前端轮询和操作打印任务"""

    @http.route('/pos/print_jobs/pending', type='json', auth='user', methods=['POST'])
    def get_pending_jobs(self, config_id, limit=10, **kwargs):
        """
        获取待打印任务列表
        
        Args:
            config_id: POS 配置 ID
            limit: 返回的最大任务数
        
        Returns:
            {
                'success': True/False,
                'jobs': [...],
                'error': '...'
            }
        """
        try:
            pos_config = request.env['pos.config'].browse(config_id)
            if not pos_config.exists():
                return {
                    'success': False,
                    'error': 'INVALID_CONFIG',
                    'message': 'POS 配置不存在'
                }
            
            # 获取待打印任务
            jobs = request.env['pos.print.job'].get_pending_jobs(config_id, limit=limit)
            
            # 序列化任务数据
            jobs_data = []
            for job in jobs:
                jobs_data.append({
                    'id': job.id,
                    'name': job.name,
                    'print_type': job.print_type,
                    'print_payload': json.loads(job.print_payload),
                    'printer_name': job.printer_name,
                    'qr_order_id': job.qr_order_id.id if job.qr_order_id else None,
                    'pos_order_id': job.pos_order_id.id if job.pos_order_id else None,
                    'trace_id': job.trace_id,
                    'create_date': job.create_date.isoformat() if job.create_date else None,
                })
            
            return {
                'success': True,
                'jobs': jobs_data,
                'count': len(jobs_data)
            }
            
        except Exception as e:
            _logger.error(f"Failed to get pending jobs: {e}")
            return {
                'success': False,
                'error': 'SERVER_ERROR',
                'message': str(e)
            }

    @http.route('/pos/print_jobs/claim', type='json', auth='user', methods=['POST'])
    def claim_job(self, job_id, client_id, **kwargs):
        """
        认领打印任务（原子操作）
        
        Args:
            job_id: 任务 ID
            client_id: 客户端标识（IP/主机名）
        
        Returns:
            {
                'success': True/False,
                'job': {...},
                'error': '...'
            }
        """
        try:
            job = request.env['pos.print.job'].browse(job_id)
            if not job.exists():
                return {
                    'success': False,
                    'error': 'JOB_NOT_FOUND',
                    'message': '任务不存在'
                }
            
            # 原子认领
            success, error_msg = job.action_claim(client_id)
            
            if success:
                # 返回任务数据
                return {
                    'success': True,
                    'job': {
                        'id': job.id,
                        'name': job.name,
                        'print_type': job.print_type,
                        'print_payload': json.loads(job.print_payload),
                        'printer_name': job.printer_name,
                        'trace_id': job.trace_id,
                    }
                }
            else:
                return {
                    'success': False,
                    'error': 'CLAIM_FAILED',
                    'message': error_msg or '任务已被其他客户端认领'
                }
                
        except Exception as e:
            _logger.error(f"Failed to claim job {job_id}: {e}")
            return {
                'success': False,
                'error': 'SERVER_ERROR',
                'message': str(e)
            }

    @http.route('/pos/print_jobs/mark_done', type='json', auth='user', methods=['POST'])
    def mark_job_done(self, job_id, **kwargs):
        """
        标记任务完成
        
        Args:
            job_id: 任务 ID
        
        Returns:
            {'success': True/False, 'error': '...'}
        """
        try:
            job = request.env['pos.print.job'].browse(job_id)
            if not job.exists():
                return {
                    'success': False,
                    'error': 'JOB_NOT_FOUND',
                    'message': '任务不存在'
                }
            
            job.action_mark_done()
            
            return {'success': True}
            
        except Exception as e:
            _logger.error(f"Failed to mark job {job_id} as done: {e}")
            return {
                'success': False,
                'error': 'SERVER_ERROR',
                'message': str(e)
            }

    @http.route('/pos/print_jobs/mark_failed', type='json', auth='user', methods=['POST'])
    def mark_job_failed(self, job_id, error_message='', **kwargs):
        """
        标记任务失败
        
        Args:
            job_id: 任务 ID
            error_message: 错误信息
        
        Returns:
            {'success': True/False, 'error': '...'}
        """
        try:
            job = request.env['pos.print.job'].browse(job_id)
            if not job.exists():
                return {
                    'success': False,
                    'error': 'JOB_NOT_FOUND',
                    'message': '任务不存在'
                }
            
            job.action_mark_failed(error_message)
            
            return {'success': True}
            
        except Exception as e:
            _logger.error(f"Failed to mark job {job_id} as failed: {e}")
            return {
                'success': False,
                'error': 'SERVER_ERROR',
                'message': str(e)
            }

    @http.route('/pos/print_jobs/retry', type='json', auth='user', methods=['POST'])
    def retry_job(self, job_id, **kwargs):
        """
        重试任务
        
        Args:
            job_id: 任务 ID
        
        Returns:
            {'success': True/False, 'error': '...'}
        """
        try:
            job = request.env['pos.print.job'].browse(job_id)
            if not job.exists():
                return {
                    'success': False,
                    'error': 'JOB_NOT_FOUND',
                    'message': '任务不存在'
                }
            
            job.action_retry()
            
            return {'success': True}
            
        except Exception as e:
            _logger.error(f"Failed to retry job {job_id}: {e}")
            return {
                'success': False,
                'error': 'SERVER_ERROR',
                'message': str(e)
            }

    @http.route('/pos/print_jobs/status', type='json', auth='user', methods=['POST'])
    def get_job_status(self, config_id, limit=20, **kwargs):
        """
        获取任务状态列表（用于调试面板）
        
        Args:
            config_id: POS 配置 ID
            limit: 返回的最大任务数
        
        Returns:
            {
                'success': True/False,
                'jobs': [...],
                'error': '...'
            }
        """
        try:
            pos_config = request.env['pos.config'].browse(config_id)
            if not pos_config.exists():
                return {
                    'success': False,
                    'error': 'INVALID_CONFIG',
                    'message': 'POS 配置不存在'
                }
            
            # 获取最近的任务（所有状态）
            jobs = request.env['pos.print.job'].search([
                ('pos_config_id', '=', config_id),
            ], limit=limit, order='create_date desc')
            
            # 序列化任务数据
            jobs_data = []
            for job in jobs:
                jobs_data.append({
                    'id': job.id,
                    'name': job.name,
                    'state': job.state,
                    'print_type': job.print_type,
                    'printer_name': job.printer_name,
                    'claimed_by': job.claimed_by,
                    'claimed_at': job.claimed_at.isoformat() if job.claimed_at else None,
                    'printed_at': job.printed_at.isoformat() if job.printed_at else None,
                    'error_message': job.error_message,
                    'retry_count': job.retry_count,
                    'trace_id': job.trace_id,
                    'qr_order_id': job.qr_order_id.id if job.qr_order_id else None,
                    'pos_order_id': job.pos_order_id.id if job.pos_order_id else None,
                    'create_date': job.create_date.isoformat() if job.create_date else None,
                })
            
            return {
                'success': True,
                'jobs': jobs_data,
                'count': len(jobs_data)
            }
            
        except Exception as e:
            _logger.error(f"Failed to get job status: {e}")
            return {
                'success': False,
                'error': 'SERVER_ERROR',
                'message': str(e)
            }



