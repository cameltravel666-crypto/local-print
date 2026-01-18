# -*- coding: utf-8 -*-
"""
Seisei Print Agent
A local print proxy for Odoo 18 POS and Kitchen printing

Developed by Seisei
"""

__version__ = "1.0.0"
__author__ = "Seisei"
__description__ = "Local Print Agent for Odoo 18"

# Application Info
APP_NAME = "Seisei Print Agent"
APP_VERSION = __version__
APP_AUTHOR = __author__

# Default channel prefix (configurable for compatibility with different Odoo modules)
# Use "seisei_service" for seisei_print_manager module (default)
# Use "ylhc_service" for legacy ylhc_print_manager module
DEFAULT_CHANNEL_PREFIX = "seisei_service"
