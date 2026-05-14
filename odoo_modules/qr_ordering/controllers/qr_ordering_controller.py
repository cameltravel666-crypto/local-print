# -*- coding: utf-8 -*-

import json
import logging
import base64
import hashlib
import traceback
import uuid
import time
from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)

# QR Ordering Build Version (version + timestamp for cache-busting)
QR_ORDERING_VERSION = '18.0.1.0.0'
QR_ORDERING_BUILD = f"{QR_ORDERING_VERSION}-{int(time.time())}"


class QrOrderingController(http.Controller):
    """扫码点餐控制器"""

    # ==================== 页面路由 ====================

    @http.route('/qr/t/<string:short_code>', type='http', auth='public', website=False)
    def qr_short_code_redirect(self, short_code, **kwargs):
        """
        短代码跳转
        URL: /qr/t/{short_code}

        将短代码转换为完整的点餐链接并重定向
        """
        trace_id = str(uuid.uuid4())[:8]

        try:
            # 查找餐桌
            table = request.env['qr.table'].sudo().search([
                ('short_code', '=', short_code.upper()),
                ('active', '=', True)
            ], limit=1)

            if not table:
                _logger.warning(f"[{trace_id}] Short code not found: {short_code}")
                return request.render('qr_ordering.error_page', {
                    'error_code': 'SHORT_CODE_NOT_FOUND',
                    'error_message': f'Short code "{short_code}" not found',
                    'trace_id': trace_id,
                }, status=404)

            # 构建完整URL并重定向
            redirect_url = f"/qr/order/{table.qr_token}"

            # 保留查询参数
            if kwargs:
                query_string = '&'.join(f"{k}={v}" for k, v in kwargs.items())
                redirect_url += f"?{query_string}"

            _logger.info(f"[{trace_id}] Short code redirect: {short_code} -> {table.name} ({table.qr_token[:8]}...)")

            return request.redirect(redirect_url, code=302)

        except Exception as e:
            _logger.error(f"[{trace_id}] Short code redirect error: {e}")
            return request.render('qr_ordering.error_page', {
                'error_code': 'SYSTEM_ERROR',
                'error_message': 'System error occurred',
                'trace_id': trace_id,
            }, status=500)

    @http.route('/qr/order/<string:table_token>', type='http', auth='public', website=False)
    def qr_ordering_page(self, table_token, **kwargs):
        """
        扫码点餐主页面
        URL: /qr/order/{table_token}

        Feature flags:
        - menu_ui_v2=1: 使用 V2 移动端极致体验版

        保证所有分支都返回有效页面，永不白屏：
        - 正常情况：返回点餐页面
        - token无效/餐桌禁用：返回错误页面（HTTP 404/410）
        - 系统异常：返回错误页面（HTTP 500）
        """
        trace_id = str(uuid.uuid4())[:8]
        client_ip = request.httprequest.remote_addr

        try:
            # 获取或验证会话
            access_token = request.httprequest.cookies.get('qr_access_token')

            _logger.info(f"[{trace_id}] QR page access: token={table_token[:8]}..., ip={client_ip}")

            session, error_code, error_msg = request.env['qr.session'].sudo().validate_access(
                table_token, access_token, client_ip
            )

            if error_code:
                # 根据错误类型返回不同的 HTTP 状态码
                http_status = 404 if error_code == 'TABLE_NOT_FOUND' else 410
                _logger.warning(
                    f"[{trace_id}] QR page error: code={error_code}, msg={error_msg}, "
                    f"token={table_token}, ip={client_ip}"
                )
                return request.render('qr_ordering.error_page', {
                    'error_code': error_code,
                    'error_message': error_msg,
                    'trace_id': trace_id,
                }, status=http_status)

            # 获取语言设置
            lang = kwargs.get('lang', self._detect_language())
            debug_mode = kwargs.get('debug') == '1' or request.httprequest.args.get('debug') == '1'

            # Feature flag: menu_ui_v2
            use_v2 = kwargs.get('menu_ui_v2') == '1' or request.httprequest.args.get('menu_ui_v2') == '1'
            # 也可以从系统参数读取默认值
            if not use_v2:
                use_v2 = request.env['ir.config_parameter'].sudo().get_param('qr_ordering.menu_ui_v2', 'false') == 'true'

            template_name = 'qr_ordering.ordering_page_v2' if use_v2 else 'qr_ordering.ordering_page'
            _logger.info(f"[{trace_id}] Using template: {template_name}, v2={use_v2}")

            # 渲染点餐页面
            response = request.render(template_name, {
                'session': session,
                'table': session.table_id,
                'lang': lang,
                'access_token': session.access_token,
                'build_version': QR_ORDERING_BUILD,
                'debug_mode': debug_mode,
                'trace_id': trace_id,
            })

            # 设置 cache-control headers（防止 HTML 被缓存）
            response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
            response.headers['Pragma'] = 'no-cache'
            response.headers['Expires'] = '0'

            # 设置 cookie
            response.set_cookie('qr_access_token', session.access_token, max_age=4*3600)

            return response

        except Exception as e:
            # 捕获所有异常，确保永不白屏
            _logger.error(
                f"[{trace_id}] QR page exception: token={table_token}, ip={client_ip}, "
                f"error={str(e)}\n{traceback.format_exc()}"
            )
            return request.render('qr_ordering.error_page', {
                'error_code': 'SYSTEM_ERROR',
                'error_message': '系统繁忙，请稍后重试',
                'trace_id': trace_id,
            }, status=500)

    @http.route('/qr/print/<string:table_token>', type='http', auth='user')
    def print_qr_code(self, table_token, **kwargs):
        """
        打印二维码页面
        URL: /qr/print/{table_token}
        """
        from urllib.parse import quote
        
        table = request.env['qr.table'].sudo().search([
            ('qr_token', '=', table_token)
        ], limit=1)
        
        if not table:
            return request.not_found()
        
        # 构建完整的点餐 URL
        # 使用固定的公开域名 demo.nagashiro.top
        qr_base_url = request.env['ir.config_parameter'].sudo().get_param(
            'qr_ordering.base_url',
            default='https://demo.nagashiro.top'
        )
        qr_content_url = f"{qr_base_url}/qr/order/{table.qr_token}"
        
        # URL 编码后的二维码内容
        qr_url_encoded = quote(qr_content_url, safe='')
        
        # 完整的 barcode 图片 URL
        barcode_url = f"/report/barcode/QR/{qr_url_encoded}?width=300&height=300"
        
        return request.render('qr_ordering.print_qr_page', {
            'table': table,
            'qr_content_url': qr_content_url,
            'barcode_url': barcode_url,
        })

    # ==================== 公开图片访问 ====================

    @http.route('/qr/image/product/<int:product_id>', type='http', auth='public', cors='*')
    def public_product_image(self, product_id, size='256', **kwargs):
        """
        公开访问产品图片
        URL: /qr/image/product/{product_id}?size=256
        """
        try:
            product = request.env['product.product'].sudo().browse(product_id)
            if not product.exists():
                return request.not_found()
            
            # 获取图片字段名
            field_name = f'image_{size}' if size in ['128', '256', '512', '1024', '1920'] else 'image_256'
            
            # 获取图片数据
            image_data = getattr(product, field_name, None)
            if not image_data:
                # 尝试从模板获取
                image_data = getattr(product.product_tmpl_id, field_name, None)
            
            if not image_data:
                # 返回默认占位图
                return request.redirect('/web/static/img/placeholder.png')
            
            # 解码 base64 图片
            image_bytes = base64.b64decode(image_data)
            
            # 返回图片
            headers = [
                ('Content-Type', 'image/png'),
                ('Content-Length', len(image_bytes)),
                ('Cache-Control', 'public, max-age=86400'),
            ]
            return request.make_response(image_bytes, headers)
            
        except Exception as e:
            _logger.error(f"Error serving product image: {e}")
            return request.redirect('/web/static/img/placeholder.png')

    # ==================== API 路由 ====================

    def _api_error_response(self, error_code, message, trace_id=None):
        """统一的API错误响应格式"""
        return {
            'success': False,
            'error': error_code,
            'message': message,
            'trace_id': trace_id,
        }

    def _wrap_api_call(self, func, *args, **kwargs):
        """
        包装API调用，确保：
        1. 始终返回JSON（不会返回HTML）
        2. 捕获所有异常
        3. 记录日志（含trace_id）
        """
        trace_id = str(uuid.uuid4())[:8]
        try:
            return func(trace_id, *args, **kwargs)
        except Exception as e:
            _logger.error(
                f"[{trace_id}] API exception: {str(e)}\n{traceback.format_exc()}"
            )
            return self._api_error_response('SYSTEM_ERROR', '系统繁忙，请稍后重试', trace_id)

    @http.route('/qr/api/init', type='json', auth='public', csrf=False)
    def api_init(self, table_token, access_token=None, **kwargs):
        """
        初始化点餐数据
        返回: 餐桌信息、菜单数据、当前订单等
        """
        def _do_init(trace_id):
            client_ip = request.httprequest.remote_addr
            _logger.info(f"[{trace_id}] API init: token={table_token[:8] if table_token else 'None'}..., ip={client_ip}")

            session, error_code, error_msg = request.env['qr.session'].sudo().validate_access(
                table_token, access_token, client_ip
            )

            if error_code:
                _logger.warning(f"[{trace_id}] API init error: {error_code} - {error_msg}")
                return self._api_error_response(error_code, error_msg, trace_id)

            lang = kwargs.get('lang', 'zh_CN')

            return {
                'success': True,
                'trace_id': trace_id,
                'data': {
                    'session': self._serialize_session(session),
                    'table': self._serialize_table(session.table_id),
                    'menu': self._get_menu_data(session.table_id.pos_config_id, lang),
                    'current_order': self._get_current_order(session),
                    'access_token': session.access_token,
                }
            }

        return self._wrap_api_call(_do_init)

    @http.route('/qr/api/menu', type='json', auth='public', csrf=False)
    def api_get_menu(self, table_token, access_token, lang='zh_CN', **kwargs):
        """
        获取菜单数据
        """
        session, error_code, error_msg = self._validate_session(table_token, access_token)
        if error_code:
            return {'success': False, 'error': error_code, 'message': error_msg}
        
        return {
            'success': True,
            'data': self._get_menu_data(session.table_id.pos_config_id, lang)
        }

    @http.route('/qr/api/cart/add', type='json', auth='public', csrf=False)
    def api_add_to_cart(self, table_token, access_token, product_id, qty=1, note='', **kwargs):
        """
        添加菜品到购物车
        """
        session, error_code, error_msg = self._validate_session(table_token, access_token)
        if error_code:
            return {'success': False, 'error': error_code, 'message': error_msg}
        
        try:
            # 获取或创建购物车订单
            order = self._get_or_create_cart(session)
            
            # 检查是否已有相同产品
            existing_line = order.line_ids.filtered(
                lambda l: l.product_id.id == product_id and l.state == 'pending'
            )
            
            if existing_line and not note:
                # 增加数量
                existing_line.qty += qty
            else:
                # 创建新行
                request.env['qr.order.line'].sudo().create({
                    'order_id': order.id,
                    'product_id': product_id,
                    'qty': qty,
                    'note': note,
                })
            
            return {
                'success': True,
                'data': self._serialize_order(order)
            }
        except Exception as e:
            _logger.error(f"Add to cart failed: {e}")
            return {'success': False, 'error': 'ADD_FAILED', 'message': str(e)}

    @http.route('/qr/api/cart/update', type='json', auth='public', csrf=False)
    def api_update_cart(self, table_token, access_token, line_id, qty, **kwargs):
        """
        更新购物车数量
        """
        session, error_code, error_msg = self._validate_session(table_token, access_token)
        if error_code:
            return {'success': False, 'error': error_code, 'message': error_msg}
        
        try:
            line = request.env['qr.order.line'].sudo().browse(line_id)
            
            # 验证权限
            if line.order_id.session_id != session:
                return {'success': False, 'error': 'PERMISSION_DENIED', 'message': '无权操作'}
            
            if line.state != 'pending':
                return {'success': False, 'error': 'LINE_SUBMITTED', 'message': '该菜品已提交，无法修改'}
            
            if qty <= 0:
                line.unlink()
            else:
                line.qty = qty
            
            return {
                'success': True,
                'data': self._serialize_order(line.order_id)
            }
        except Exception as e:
            _logger.error(f"Update cart failed: {e}")
            return {'success': False, 'error': 'UPDATE_FAILED', 'message': str(e)}

    @http.route('/qr/api/cart/remove', type='json', auth='public', csrf=False)
    def api_remove_from_cart(self, table_token, access_token, line_id, **kwargs):
        """
        从购物车移除菜品
        """
        return self.api_update_cart(table_token, access_token, line_id, 0)

    @http.route('/qr/api/order/submit', type='json', auth='public', csrf=False)
    def api_submit_order(self, table_token, access_token, note='', **kwargs):
        """
        提交订单
        """
        session, error_code, error_msg = self._validate_session(table_token, access_token)
        if error_code:
            return {'success': False, 'error': error_code, 'message': error_msg}

        try:
            # 获取购物车订单
            order = request.env['qr.order'].sudo().search([
                ('session_id', '=', session.id),
                ('state', '=', 'cart'),
            ], limit=1)

            if not order:
                return {'success': False, 'error': 'NO_CART', 'message': '购物车为空'}

            if note:
                order.note = note

            # 提交订单（返回结构化响应）
            result = order.action_submit_order()

            if not result.get('success'):
                # 订单提交失败（如 POS Session 未开启）
                return {
                    'success': False,
                    'error': result.get('error_code', 'SUBMIT_FAILED'),
                    'message': result.get('error_message', '订单提交失败')
                }

            # 更新会话状态
            session.state = 'ordering'

            return {
                'success': True,
                'data': self._serialize_order(order)
            }
        except Exception as e:
            _logger.error(f"Submit order failed: {e}")
            return {'success': False, 'error': 'SUBMIT_FAILED', 'message': str(e)}

    @http.route('/qr/api/order/add_items', type='json', auth='public', csrf=False)
    def api_add_items(self, table_token, access_token, items, **kwargs):
        """
        加菜
        items: [{'product_id': x, 'qty': y, 'note': z}, ...]
        """
        session, error_code, error_msg = self._validate_session(table_token, access_token)
        if error_code:
            return {'success': False, 'error': error_code, 'message': error_msg}
        
        try:
            # 获取当前活跃订单
            order = request.env['qr.order'].sudo().search([
                ('session_id', '=', session.id),
                ('state', 'in', ['cooking', 'serving']),
            ], order='create_date desc', limit=1)
            
            if not order:
                return {'success': False, 'error': 'NO_ORDER', 'message': '没有可加菜的订单'}
            
            # 加菜
            order.action_add_items(items)
            
            return {
                'success': True,
                'data': self._serialize_order(order)
            }
        except Exception as e:
            _logger.error(f"Add items failed: {e}")
            return {'success': False, 'error': 'ADD_ITEMS_FAILED', 'message': str(e)}

    @http.route('/qr/api/order/status', type='json', auth='public', csrf=False)
    def api_get_order_status(self, table_token, access_token, **kwargs):
        """
        获取订单状态
        """
        session, error_code, error_msg = self._validate_session(table_token, access_token)
        if error_code:
            return {'success': False, 'error': error_code, 'message': error_msg}
        
        orders = request.env['qr.order'].sudo().search([
            ('session_id', '=', session.id),
        ], order='create_date desc')
        
        return {
            'success': True,
            'data': {
                'orders': [self._serialize_order(o) for o in orders],
                'session_state': session.state,
            }
        }

    # ==================== 辅助方法 ====================

    def _validate_session(self, table_token, access_token):
        """验证会话"""
        client_ip = request.httprequest.remote_addr
        return request.env['qr.session'].sudo().validate_access(
            table_token, access_token, client_ip
        )

    def _detect_language(self):
        """检测语言"""
        accept_lang = request.httprequest.headers.get('Accept-Language', '')
        if 'ja' in accept_lang:
            return 'ja_JP'
        elif 'en' in accept_lang:
            return 'en_US'
        return 'zh_CN'

    def _get_or_create_cart(self, session):
        """获取或创建购物车"""
        order = request.env['qr.order'].sudo().search([
            ('session_id', '=', session.id),
            ('state', '=', 'cart'),
        ], limit=1)
        
        if not order:
            order = request.env['qr.order'].sudo().create({
                'session_id': session.id,
            })
        
        return order

    def _get_menu_data(self, pos_config, lang='zh_CN'):
        """获取菜单数据"""
        # 获取 POS 可用的产品
        products = request.env['product.product'].sudo().with_context(lang=lang).search([
            ('available_in_pos', '=', True),
            ('product_tmpl_id.qr_available', '=', True),
            ('product_tmpl_id.qr_sold_out', '=', False),
        ])
        
        # 获取分类
        categories = request.env['pos.category'].sudo().with_context(lang=lang).search([])
        
        # 按分类组织数据
        menu = {
            'categories': [],
            'products': [],
        }
        
        for cat in categories:
            menu['categories'].append({
                'id': cat.id,
                'name': cat.name,
                'sequence': cat.sequence,
                'parent_id': cat.parent_id.id if cat.parent_id else False,
            })
        
        for product in products:
            # 传递 POS 配置以计算含税价格
            menu['products'].append(product.get_qr_ordering_data(lang, pos_config=pos_config))

        return menu

    def _get_current_order(self, session):
        """获取当前订单"""
        orders = request.env['qr.order'].sudo().search([
            ('session_id', '=', session.id),
            ('state', '!=', 'cancelled'),
        ], order='create_date desc')
        
        if not orders:
            return None
        
        return [self._serialize_order(o) for o in orders]

    def _serialize_session(self, session):
        """序列化会话数据"""
        return {
            'id': session.id,
            'name': session.name,
            'state': session.state,
            'expire_time': session.expire_time.isoformat() if session.expire_time else None,
            'total_amount': session.total_amount,
        }

    def _serialize_table(self, table):
        """序列化餐桌数据"""
        return {
            'id': table.id,
            'name': table.name,
            'state': table.state,
        }

    def _serialize_order(self, order):
        """
        序列化订单数据（含税信息）

        双向同步策略：
        - 如果有关联的 POS 订单，从 POS 订单获取商品行和金额（包含 POS 端加的菜）
        - 否则从 QR 订单行获取（购物车状态）
        """
        pos_order = order.pos_order_id
        _logger.warning(f"[Sync] _serialize_order called for QR {order.id}, pos_order_id={order.pos_order_id}, pos_order={pos_order}")

        if pos_order:
            # ===== 从 POS 订单获取（双向同步）=====
            # POS 订单包含所有商品：QR 下单 + POS 直接加菜
            lines_data = []
            _logger.warning(f"[Sync] QR Order {order.id} -> POS Order {pos_order.id}, POS lines count: {len(pos_order.lines)}")
            for pos_line in pos_order.lines:
                try:
                    line_data = self._serialize_pos_order_line(pos_line)
                    lines_data.append(line_data)
                    _logger.warning(f"[Sync] Serialized POS line {pos_line.id}: {pos_line.full_product_name} x {pos_line.qty}")
                except Exception as e:
                    _logger.error(f"[Sync] Failed to serialize POS line {pos_line.id}: {e}")

            # 金额从 POS 订单获取（最准确）
            amount_total_incl = pos_order.amount_total or 0
            amount_tax = pos_order.amount_tax or 0
            amount_untaxed = amount_total_incl - amount_tax
            total_qty = sum(pos_line.qty for pos_line in pos_order.lines)
        else:
            # ===== 从 QR 订单获取（购物车状态）=====
            lines_data = []
            for line in order.line_ids:
                line_data = self._serialize_order_line(line)
                lines_data.append(line_data)

            # 从订单行计算金额
            amount_tax = 0.0
            amount_total_incl = 0.0
            for line_data in lines_data:
                amount_tax += line_data.get('tax_amount', 0)
                amount_total_incl += line_data.get('subtotal_incl', line_data.get('subtotal', 0))
            amount_untaxed = order.total_amount
            total_qty = order.total_qty

        _logger.info(f"[Sync] Order {order.id} returning {len(lines_data)} lines, total_qty={total_qty}")

        return {
            'id': order.id,
            'name': order.name,
            'state': order.state,
            'pos_order_id': pos_order.id if pos_order else None,
            'pos_order_name': pos_order.name if pos_order else None,
            'total_amount': order.total_amount,  # 税前总额（兼容旧版）
            'amount_untaxed': round(amount_untaxed, 0),  # 未税金额
            'amount_tax': round(amount_tax, 0),  # 税额
            'amount_total_incl': round(amount_total_incl, 0),  # 含税总额
            'total_qty': total_qty,
            'note': order.note or '',
            'order_time': order.order_time.isoformat() if order.order_time else None,
            'lines': lines_data,
        }

    def _serialize_order_line(self, line):
        """序列化订单行数据（含税信息）"""
        subtotal = line.subtotal  # 税前小计
        subtotal_incl = subtotal  # 含税小计（默认同税前）
        tax_amount = 0.0
        tax_rate = 0.0

        # 计算含税价格
        if line.product_id and line.product_id.taxes_id:
            try:
                # 获取公司和税规则
                session = line.order_id.session_id
                pos_config = session.pos_config_id if session else None
                if pos_config:
                    company = pos_config.company_id
                    fiscal_position = pos_config.default_fiscal_position_id
                    taxes = line.product_id.taxes_id.filtered(lambda t: t.company_id == company)
                    if fiscal_position:
                        taxes = fiscal_position.map_tax(taxes)
                    if taxes:
                        tax_result = taxes.compute_all(
                            line.price_unit,
                            currency=company.currency_id,
                            quantity=line.qty,
                            product=line.product_id
                        )
                        subtotal_incl = tax_result['total_included']
                        tax_amount = subtotal_incl - tax_result['total_excluded']
                        if subtotal > 0:
                            tax_rate = (tax_amount / subtotal) * 100
            except Exception as e:
                _logger.warning(f"Tax calculation failed for line {line.id}: {e}")

        return {
            'id': line.id,
            'product_id': line.product_id.id,
            'product_name': line.product_name,
            'qty': line.qty,
            'price_unit': line.price_unit,  # 税前单价
            'subtotal': subtotal,  # 税前小计
            'subtotal_incl': round(subtotal_incl, 0),  # 含税小计
            'tax_amount': round(tax_amount, 0),  # 税额
            'tax_rate': round(tax_rate, 1),  # 税率 %
            'note': line.note or '',
            'batch_number': line.batch_number,
            'state': line.state,
        }

    def _serialize_pos_order_line(self, pos_line):
        """
        序列化 POS 订单行数据

        用于双向同步：当 POS 端加菜时，QR 端也能看到
        """
        product = pos_line.product_id

        # POS 订单行已经有准确的含税/未税金额
        price_unit = pos_line.price_unit or 0
        qty = pos_line.qty or 0
        subtotal = pos_line.price_subtotal or (price_unit * qty)
        subtotal_incl = pos_line.price_subtotal_incl or subtotal
        tax_amount = subtotal_incl - subtotal

        # 计算税率
        tax_rate = 0.0
        if subtotal > 0:
            tax_rate = (tax_amount / subtotal) * 100

        # 解析备注中的来源信息
        # QR 订单的备注格式: "[QR:QRO-xxx] 备注" 或 "[加菜 Batch N] 备注"
        note = pos_line.customer_note or ''
        source = 'pos'  # 默认来源为 POS
        if note.startswith('[QR:'):
            source = 'qr'
            # 提取实际备注
            bracket_end = note.find(']')
            if bracket_end > 0:
                note = note[bracket_end + 1:].strip()
        elif note.startswith('[加菜'):
            source = 'qr_add'
            bracket_end = note.find(']')
            if bracket_end > 0:
                note = note[bracket_end + 1:].strip()

        return {
            'id': pos_line.id,
            'product_id': product.id if product else None,
            'product_name': pos_line.full_product_name or (product.name if product else ''),
            'qty': qty,
            'price_unit': price_unit,
            'subtotal': round(subtotal, 0),
            'subtotal_incl': round(subtotal_incl, 0),
            'tax_amount': round(tax_amount, 0),
            'tax_rate': round(tax_rate, 1),
            'note': note,
            'source': source,  # 'qr' | 'qr_add' | 'pos'
            'batch_number': 1,  # POS 订单行没有批次概念
            'state': 'submitted',  # POS 订单行都是已提交状态
        }

