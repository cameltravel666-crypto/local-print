# -*- coding: utf-8 -*-

from odoo.addons.bus.websocket import WebsocketRequest

# Save original method
original_serve_ir_websocket = WebsocketRequest._serve_ir_websocket

def patched_serve_ir_websocket(self, event_name, data):
    """
    Extend WebSocket event handling, add print management related events
    
    Based on the original 'subscribe' and 'update_presence' events,
    add handling for printer synchronization messages
    """
    # Call original method to handle standard events
    if event_name in ('subscribe', 'update_presence'):
        return original_serve_ir_websocket(self, event_name, data)
    
    # Ensure user is authenticated
    self.env['ir.websocket']._authenticate()
    
    # Handle print management related events
    if event_name == 'seisei_service_message':
        # Unified print management synchronization handling, dispatch based on message type
        self.env['seisei.printer']._handle_print_manager_message(data)

WebsocketRequest._serve_ir_websocket = patched_serve_ir_websocket
