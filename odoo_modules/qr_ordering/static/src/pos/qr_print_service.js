/** @odoo-module */
/**
 * QR Order Print Extension for POS
 *
 * This module patches the POS Store to listen for QR order notifications
 * and triggers printing on the POS frontend via YLHC Recorder.
 *
 * The notification flow:
 * 1. QR order is submitted (backend)
 * 2. Backend calls pos.config._notify('QR_ORDER_PRINT', data)
 * 3. This module receives the notification via data.onNotified
 * 4. Calls this.printChanges() to trigger actual printing through YLHC Recorder
 */

import { patch } from "@web/core/utils/patch";
import { PosStore } from "@point_of_sale/app/store/pos_store";

patch(PosStore.prototype, {
    /**
     * @override
     * Initialize QR print listener after server data is processed
     */
    async afterProcessServerData() {
        await super.afterProcessServerData(...arguments);
        console.log("[QR Print] afterProcessServerData complete, initializing QR print listener");
        this._initQrPrintListener();
    },

    _initQrPrintListener() {
        // Use the data service's onNotified method which is already connected to the correct channel
        if (this.data && this.data.onNotified) {
            console.log("[QR Print] Subscribing to QR_ORDER_PRINT notifications");
            this.data.connectWebSocket('QR_ORDER_PRINT', this._handleQrPrintNotification.bind(this));
            console.log("[QR Print] Subscription complete");
        } else {
            console.warn("[QR Print] data.onNotified not available, retrying in 1 second");
            setTimeout(() => this._initQrPrintListener(), 1000);
        }
    },

    _handleQrPrintNotification(notificationData) {
        console.log("[QR Print] Received print notification:", notificationData);

        const {
            order_id,
            order_name,
            config_id,
            lines,
            table_name,
            qr_order_name,
            is_batch
        } = notificationData;

        // Verify this is for our POS config
        if (config_id && config_id !== this.config?.id) {
            console.log("[QR Print] Ignoring notification for different config");
            return;
        }

        // Trigger print
        this._triggerQrOrderPrint(order_id, order_name, lines, table_name, qr_order_name, is_batch);
    },

    async _triggerQrOrderPrint(orderId, orderName, lines, tableName, qrOrderName, isBatch = false) {
        console.log(`[QR Print] Triggering print for order ${orderName} (QR: ${qrOrderName})${isBatch ? ' [BATCH/加菜]' : ''}`);

        try {
            // Build order changes structure for printing
            // This structure matches what POS uses in sendOrderInPreparation
            const orderChange = {
                new: (lines || []).map(line => ({
                    product_id: line.product_id,
                    name: line.product_name,
                    quantity: line.qty,
                    note: line.note || "",
                    customer_note: line.note || "",
                    pos_categ_id: line.categ_id || false,
                    pos_categ_sequence: line.categ_sequence || 0,
                })),
                cancelled: [],
                generalNote: tableName ? `桌号: ${tableName}` : "",
                modeUpdate: false,
            };

            console.log("[QR Print] Order changes:", orderChange);

            // Try to find the order in local models
            let order = null;

            // First try to find in local models
            if (this.models && this.models["pos.order"]) {
                const orders = this.models["pos.order"].getAll();
                order = orders.find(o => o.id === orderId);
            }

            // If not found, create a minimal order-like object for printing
            if (!order) {
                order = this.get_order();
                if (!order || order.id !== orderId) {
                    // Create a minimal order-like object for printing
                    order = {
                        id: orderId,
                        name: orderName,
                        pos_reference: orderName,
                        table_id: null,
                        getCustomerNote: () => tableName ? `桌号: ${tableName}` : "",
                    };
                }
            }

            // Call printChanges - this is the same method POS uses
            if (typeof this.printChanges === "function") {
                console.log("[QR Print] Calling printChanges");
                const result = await this.printChanges(order, orderChange);
                console.log("[QR Print] Print completed, result:", result);
            } else {
                console.error("[QR Print] printChanges method not available");
            }
        } catch (error) {
            console.error("[QR Print] Print failed:", error);
        }
    },
});

console.log("[QR Print] QR Print extension loaded");
