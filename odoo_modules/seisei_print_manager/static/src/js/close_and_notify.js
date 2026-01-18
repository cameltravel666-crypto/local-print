/** @odoo-module **/

import { registry } from "@web/core/registry";

/**
 * Custom client action: Close dialog and show notification
 * First closes the current dialog/wizard, then displays a notification message
 */
registry.category("actions").add("seisei_close_and_notify", async function (env, action) {
    const { message, type = "success", sticky = false, title } = action.params || {};
    
    // Close current dialog/wizard
    await env.services?.action?.doAction({ type: "ir.actions.act_window_close" });
    
    // Show notification
    if (message) {
        env.services.notification.add(message, {
            type: type,
            sticky: sticky,
            title: title
        });
    }
});
