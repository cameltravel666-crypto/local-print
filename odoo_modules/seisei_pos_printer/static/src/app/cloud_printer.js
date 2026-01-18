/** @odoo-module */

import { BasePrinter } from "@point_of_sale/app/printer/base_printer";
import { _t } from "@web/core/l10n/translation";
import { rpc } from "@web/core/network/rpc";

/**
 * CloudPrinter - Sends print jobs to Seisei Print Manager via RPC.
 * The print job is then forwarded to the client via WebSocket.
 * Uses the same Floyd-Steinberg dithering as EpsonPrinter for optimal print quality.
 */
export class CloudPrinter extends BasePrinter {
    setup({ printerId }) {
        super.setup(...arguments);
        this.printerId = printerId;
    }

    /**
     * @override
     * Process canvas and generate complete ESC/POS commands
     */
    processCanvas(canvas) {
        const rasterData = this.canvasToRaster(canvas);
        const escposCommands = this.generateEscposCommands(canvas.width, canvas.height, rasterData);
        return escposCommands;
    }

    /**
     * Transform a (potentially colored) canvas into a monochrome raster image.
     * Uses Floyd-Steinberg dithering for better quality.
     * (Same algorithm as EpsonPrinter)
     */
    canvasToRaster(canvas) {
        const imageData = canvas.getContext("2d").getImageData(0, 0, canvas.width, canvas.height);
        const pixels = imageData.data;
        const width = imageData.width;
        const height = imageData.height;
        const errors = Array.from(Array(width), (_) => Array(height).fill(0));
        const rasterData = new Array(width * height).fill(0);

        for (let y = 0; y < height; y++) {
            for (let x = 0; x < width; x++) {
                let oldColor, newColor;

                // Compute grayscale level using luminosity coefficients
                const idx = (y * width + x) * 4;
                oldColor = pixels[idx] * 0.299 + pixels[idx + 1] * 0.587 + pixels[idx + 2] * 0.114;

                // Propagate the error from neighbor pixels
                oldColor += errors[x][y];
                oldColor = Math.min(255, Math.max(0, oldColor));

                if (oldColor < 128) {
                    // This pixel should be black
                    newColor = 0;
                    rasterData[y * width + x] = 1;
                } else {
                    // This pixel should be white
                    newColor = 255;
                    rasterData[y * width + x] = 0;
                }

                // Propagate the error using Floyd-Steinberg coefficients
                const error = oldColor - newColor;
                if (error) {
                    if (x < width - 1) {
                        errors[x + 1][y] += (7 / 16) * error;
                    }
                    if (x > 0 && y < height - 1) {
                        errors[x - 1][y + 1] += (3 / 16) * error;
                    }
                    if (y < height - 1) {
                        errors[x][y + 1] += (5 / 16) * error;
                    }
                    if (x < width - 1 && y < height - 1) {
                        errors[x + 1][y + 1] += (1 / 16) * error;
                    }
                }
            }
        }

        return rasterData.join("");
    }

    /**
     * Generate complete ESC/POS commands from raster data
     */
    generateEscposCommands(width, height, rasterData) {
        const bytesPerLine = Math.ceil(width / 8);
        const ESC = 0x1b;
        const GS = 0x1d;
        
        // Convert raster string to bytes
        const rasterBytes = [];
        for (let i = 0; i < rasterData.length; i += 8) {
            const sub = rasterData.substr(i, 8).padEnd(8, '0');
            rasterBytes.push(parseInt(sub, 2));
        }
        
        // Build ESC/POS command sequence
        const commands = [];
        
        // Initialize printer
        commands.push(ESC, 0x40);  // ESC @
        
        // Center alignment
        commands.push(ESC, 0x61, 0x01);  // ESC a 1
        
        // GS v 0 - Raster bit image
        const xL = bytesPerLine & 0xff;
        const xH = (bytesPerLine >> 8) & 0xff;
        const yL = height & 0xff;
        const yH = (height >> 8) & 0xff;
        commands.push(GS, 0x76, 0x30, 0x00, xL, xH, yL, yH);
        
        // Append raster data
        commands.push(...rasterBytes);
        
        // Feed 3 lines
        commands.push(ESC, 0x64, 0x03);  // ESC d 3
        
        // Partial cut with feed
        commands.push(GS, 0x56, 0x41, 0x03);  // GS V A 3
        
        // Convert to base64
        const uint8Array = new Uint8Array(commands);
        let binary = '';
        for (let i = 0; i < uint8Array.length; i++) {
            binary += String.fromCharCode(uint8Array[i]);
        }
        return btoa(binary);
    }

    /**
     * Generate ESC/POS command to open cash drawer
     */
    generateCashboxCommand() {
        const ESC = 0x1b;
        // ESC p m t1 t2 - Open drawer connected to pin 0
        const commands = [ESC, 0x70, 0x00, 0x19, 0x19];
        const uint8Array = new Uint8Array(commands);
        let binary = '';
        for (let i = 0; i < uint8Array.length; i++) {
            binary += String.fromCharCode(uint8Array[i]);
        }
        return btoa(binary);
    }

    /**
     * @override
     * Send print job to Seisei Print Manager via RPC
     */
    async sendPrintingJob(escposData) {
        try {
            const result = await rpc("/seisei_pos_printer/print_receipt", {
                printer_id: this.printerId,
                escpos_data: escposData,
            });
            
            if (result.error) {
                console.error("Cloud print error:", result.error);
                return { result: false, printerErrorCode: result.error };
            }
            
            return { result: true, jobId: result.job_id };
        } catch (error) {
            console.error("Cloud print RPC error:", error);
            throw error;
        }
    }

    /**
     * @override
     * Open cash drawer via Seisei Print Manager
     */
    async openCashbox() {
        try {
            const escposData = this.generateCashboxCommand();
            await rpc("/seisei_pos_printer/open_cashbox", {
                printer_id: this.printerId,
                escpos_data: escposData,
            });
        } catch (error) {
            console.error("Cloud cashbox error:", error);
        }
    }

    /**
     * @override
     */
    getActionError() {
        return {
            successful: false,
            message: {
                title: _t("Connection to Cloud Print Manager failed"),
                body: _t("Please check if the Seisei Print Manager is running and the printer is online."),
            },
        };
    }

    /**
     * @override
     */
    getResultsError(printResult) {
        const errorCode = printResult?.printerErrorCode || "";
        let message = _t("The print job was sent but the printer reported an error.") + "\n";
        
        if (errorCode) {
            message += "\n" + _t("Error code:") + " " + errorCode;
        }
        
        message += "\n" + _t("Please check if the printer is online and has paper.");
        
        return {
            successful: false,
            errorCode: errorCode,
            message: {
                title: _t("Cloud printing failed"),
                body: message,
            },
        };
    }
}
