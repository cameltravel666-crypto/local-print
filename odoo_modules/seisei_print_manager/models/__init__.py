# -*- coding: utf-8 -*-

from . import station
from . import printer
from . import report_mapping
from . import report_mapping_group
from . import print_job
from . import monkey_patch
from . import res_user
from . import res_settings
from . import ir_action_report
from . import ticket_template
from . import ticket_element

# POS integration (optional - only if point_of_sale is installed)
try:
    from . import pos_config
    from . import pos_order
except ImportError:
    pass

# QR Ordering integration is handled via hooks.py monkey patching
# The patch is applied when the registry is initialized
