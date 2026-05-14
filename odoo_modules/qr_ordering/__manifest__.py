# -*- coding: utf-8 -*-
{
    'name': 'QR Code Ordering',
    'version': '18.0.1.0.2',
    'category': 'Point of Sale',
    'summary': 'Customer self-service ordering via QR code',
    'description': '''
扫码点餐模块
============

功能特点:
---------
* 每个餐桌生成唯一二维码
* 客户扫码进入移动端点餐界面
* 支持图片和视频展示菜品
* 购物车和加菜功能
* 订单实时同步到 POS 系统
* 自动触发小票打印
* 多语言支持（中文/日文/英文）
* 防恶意点餐机制（动态 Token + Session）

QR Code Ordering Module
=======================

Features:
---------
* Generate unique QR code for each table
* Mobile-friendly ordering interface
* Support image and video for products
* Shopping cart and add-more-items function
* Real-time sync with POS system
* Auto-trigger receipt printing
* Multi-language support (Chinese/Japanese/English)
* Anti-abuse mechanism (Dynamic Token + Session)
    ''',
    'author': 'Seisei',
    'website': 'https://seisei.co.jp',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'point_of_sale',
        'pos_restaurant',
        'bus',
    ],
    'external_dependencies': {
        'python': ['qrcode', 'pillow'],
    },
    'data': [
        'security/ir.model.access.csv',
        'data/qr_ordering_data.xml',
        'views/qr_table_views.xml',
        'views/qr_session_views.xml',
        'views/qr_order_views.xml',
        'views/product_views.xml',
        'views/qr_ordering_menus.xml',
        'views/qr_ordering_templates.xml',
        'views/qr_ordering_templates_v2.xml',  # V2 Mobile Optimized
        'views/qr_pos_assets.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'qr_ordering/static/src/css/qr_ordering.css',
            'qr_ordering/static/src/js/qr_ordering.js',
            'qr_ordering/static/src/css/qr_ordering_v2.css',  # V2 CSS
            'qr_ordering/static/src/js/qr_ordering_v2.js',    # V2 JS
        ],
        'point_of_sale._assets_pos': [
            'qr_ordering/static/src/pos/qr_print_service.js',
            'qr_ordering/static/src/js/pos_print_consumer.js',
        ],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
}

