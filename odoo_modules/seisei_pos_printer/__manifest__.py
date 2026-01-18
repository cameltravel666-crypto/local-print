# -*- coding: utf-8 -*-
{
    'name': 'Seisei POS Printer',
    'version': '1.0.0',
    'category': 'Point of Sale',
    'summary': 'Bridge POS printers to Seisei Print Manager for remote ESC/POS printing',
    'description': """
        POS Seisei Printer Integration
        ============================

        This module bridges Point of Sale printers with Seisei Print Manager:

        Main Features:
        -------------
        * 🌐 Cloud Print mode for POS configuration
        * 🔗 Associate POS with Seisei printers for receipt printing
        * 🖨️ Route print jobs through Seisei Print Manager
        * 📡 Support for remote ESC/POS printing via WebSocket
        * 🔄 Intercept /hw_proxy/default_printer_action for Seisei routing

        Configuration:
        -------------
        1. Go to POS > Configuration > Settings
        2. Enable 'Cloud Print' in Connected Devices section
        3. Select a Seisei printer for receipt printing
        4. Print jobs will be routed through Seisei Print Manager
    """,
    'author': 'Seisei',
    'website': 'https://github.com/seisei',
    'depends': [
        'point_of_sale',
        'seisei_print_manager',
    ],
    'data': [
        'views/pos_printer_views.xml',
        'views/res_config_settings_views.xml',
    ],
    'assets': {
        'point_of_sale._assets_pos': [
            'seisei_pos_printer/static/src/app/cloud_printer.js',
            'seisei_pos_printer/static/src/overrides/models/pos_store.js',
        ],
    },
    'installable': True,
    'auto_install': False,
    'license': 'AGPL-3',
}
