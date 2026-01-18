# -*- coding: utf-8 -*-
{
    'name': 'Seisei Mutex Toggle',
    'version': '18.0.1.0',
    'category': 'Technical',
    'summary': 'Mutex toggle field widget for Odoo',
    'description': """
        Mutex Toggle Field Widget
        ==========================
        
        This module provides a mutex toggle field widget that ensures only one record
        can have the toggle enabled at a time within a list view.
        
        Features:
        ---------
        * Automatic mutual exclusion in list views
        * Extends standard boolean toggle field
        * Patches boolean toggle to prevent auto-save
        
        Usage:
        ------
        Add widget="mutex_toggle" to your boolean field in list view:
        
        <field name="your_boolean_field" widget="mutex_toggle"/>
    """,
    'author': 'Seisei',
    'website': 'https://github.com/seisei',
    'depends': [
        'web',
    ],
    'assets': {
        'web.assets_backend': [
            'seisei_mutex_toggle/static/src/seisei_toggle_patch.js',
            'seisei_mutex_toggle/static/src/seisei_mutex_toggle.js',
            'seisei_mutex_toggle/static/src/seisei_mutex_toggle.scss',
        ],
    },
    'installable': True,
    'auto_install': False,
    'application': False,
    'license': 'LGPL-3',
}
