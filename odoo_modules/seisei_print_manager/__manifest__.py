# -*- coding: utf-8 -*-
{
    'name': 'Seisei Print Manager',
    'version': '1.0.0',
    'category': 'Tools',
    'summary': 'Printer management and report mapping module for service communication',
    'description': """
        Seisei Print Manager
        ==================

        This module provides comprehensive printer management and report mapping functionality:

        Main Features:
        -------------
        * 🏢 Station-based printer group management
        * 🖨️ Real-time printer information sync with service
        * 📊 Report to printer mapping management  
        * 🔄 Automatic print task assignment and scheduling
        * 📡 WebSocket real-time communication
        * 🎯 Intelligent printer selection algorithm
        * 📈 Print job status monitoring

        Technical Features:
        ------------------
        * WebSocket-based real-time communication
        * Hierarchical printer management architecture (Station->Printer)
        * Flexible mapping rule configuration
        * Support for conditional matching and priorities
        * Complete task scheduling system
        * Error handling and retry mechanisms

        Use Cases:
        ----------
        * Unified management for multi-station environments
        * Grouped printer management for different locations
        * Location-based intelligent printer selection
        * Unified management for multi-printer environments
        * Different reports using different printers
        * Automatic printer failover
        * Print job queue management
    """,
    'author': 'Seisei',
    'website': 'https://github.com/seisei',
    'icon': 'icon.png',
    'depends': [
        'base',
        'web',
        'bus',
        'mail',
        'point_of_sale',
        'seisei_mutex_toggle',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/printer_data.xml',
        'data/mapping_group_data.xml',
        'data/ticket_template_data.xml',

        'views/station_views.xml',
        'views/printer_views.xml',
        'views/report_mapping_views.xml',
        'views/report_mapping_group_views.xml',
        'views/print_job_views.xml',
        'views/res_config_settings_views.xml',
        'views/res_users.xml',
        'views/station_views.xml',
        'views/ticket_template_views.xml',
        'views/pos_config_views.xml',
        'views/menu_views.xml',

        'wizards/policy_selector_wizard_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'seisei_print_manager/static/src/js/close_and_notify.js',
            'seisei_print_manager/static/src/report_handler.js',
            # Ticket Editor Components
            'seisei_print_manager/static/src/components/ticket_editor/ticket_editor.js',
            'seisei_print_manager/static/src/components/ticket_editor/ticket_editor.xml',
            'seisei_print_manager/static/src/components/ticket_editor/ticket_editor.scss',
        ],
    },
    'images': [
        'static/description/banner.png',
    ],
    'installable': True,
    'auto_install': False,
    'application': True,
    'sequence': 100,
    'license': 'AGPL-3',
    'post_init_hook': 'post_init_hook',
}