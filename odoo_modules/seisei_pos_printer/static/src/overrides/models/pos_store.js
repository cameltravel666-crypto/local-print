/** @odoo-module */

import { PosStore } from "@point_of_sale/app/store/pos_store";
import { CloudPrinter } from "@seisei_pos_printer/app/cloud_printer";
import { patch } from "@web/core/utils/patch";

patch(PosStore.prototype, {
    /**
     * @override
     * Initialize cloud printer for receipt printing if configured
     */
    async afterProcessServerData() {
        await super.afterProcessServerData(...arguments);   
        // Check if cloud print is enabled for receipt printer
        if (this.config.use_seisei_cloud_print && this.config.seisei_receipt_printer_id) {
            this.hardwareProxy.printer = new CloudPrinter({
                printerId: this.config.seisei_receipt_printer_id.id,
            });
        }
    },

    /**
     * @override
     * Create cloud printer for order/kitchen printers
     */
    create_printer(config) {
        if (config.printer_type === "cloud_printer" && config.seisei_printer_id) {
            debugger
            return new CloudPrinter({
                printerId: config.seisei_printer_id,
            });
        } else {
            return super.create_printer(...arguments);
        }
    },
});
