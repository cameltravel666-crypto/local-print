/** @odoo-module */

import { Component, useState, useRef, onMounted, onWillUnmount } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

/**
 * Seisei Ticket Editor
 * Visual drag-and-drop editor for ticket templates
 */
export class TicketEditor extends Component {
    static template = "seisei_print_manager.TicketEditor";
    static props = {
        action: { type: Object, optional: true },
    };

    setup() {
        // Services
        this.rpc = useService("rpc");
        this.notification = useService("notification");
        this.actionService = useService("action");

        // State
        this.state = useState({
            // Template data
            templateId: null,
            templateName: "",
            templateCode: "",
            templateType: "pos_receipt",
            paperWidth: 80,

            // Elements
            elements: [],
            selectedElement: null,
            draggedElement: null,

            // UI state
            isLoading: true,
            isSaving: false,
            showPreview: false,
            previewImage: null,

            // Undo/Redo
            history: [],
            historyIndex: -1,
        });

        // Element types for toolbox
        this.elementTypes = [
            { type: "text", label: _t("Text"), icon: "fa-font", defaultHeight: 30 },
            { type: "dynamic_field", label: _t("Dynamic Field"), icon: "fa-code", defaultHeight: 30 },
            { type: "image", label: _t("Image/Logo"), icon: "fa-image", defaultHeight: 80 },
            { type: "separator", label: _t("Separator"), icon: "fa-minus", defaultHeight: 20 },
            { type: "barcode", label: _t("Barcode"), icon: "fa-barcode", defaultHeight: 60 },
            { type: "qrcode", label: _t("QR Code"), icon: "fa-qrcode", defaultHeight: 100 },
        ];

        // Refs
        this.canvasRef = useRef("canvas");

        // Lifecycle
        onMounted(() => this.onMounted());
        onWillUnmount(() => this.onWillUnmount());
    }

    async onMounted() {
        // Get template ID from action params
        const params = this.props.action?.params || {};
        this.state.templateId = params.template_id;

        if (this.state.templateId) {
            await this.loadTemplate();
        } else {
            this.state.isLoading = false;
        }

        // Setup keyboard shortcuts
        this.keyHandler = this.onKeyDown.bind(this);
        document.addEventListener("keydown", this.keyHandler);
    }

    onWillUnmount() {
        document.removeEventListener("keydown", this.keyHandler);
    }

    /**
     * Load template from server
     */
    async loadTemplate() {
        this.state.isLoading = true;
        try {
            const result = await this.rpc(
                `/seisei/ticket/template/${this.state.templateId}/load`,
                {}
            );

            if (result.success) {
                const template = result.template;
                this.state.templateName = template.name;
                this.state.templateCode = template.code;
                this.state.templateType = template.template_type;
                this.state.paperWidth = template.paper_width;
                this.state.elements = template.elements.map((el, idx) => ({
                    ...el,
                    _uid: `el_${Date.now()}_${idx}`,
                }));
                this.saveHistory();
            } else {
                this.notification.add(result.error || _t("Failed to load template"), {
                    type: "danger",
                });
            }
        } catch (error) {
            console.error("Failed to load template:", error);
            this.notification.add(_t("Failed to load template"), { type: "danger" });
        }
        this.state.isLoading = false;
    }

    /**
     * Save template to server
     */
    async saveTemplate() {
        this.state.isSaving = true;
        try {
            const elements = this.state.elements.map((el) => ({
                type: el.type,
                sequence: el.sequence,
                pos_x: el.pos_x || 0,
                pos_y: el.pos_y || 0,
                width: el.width,
                height: el.height,
                text_content: el.text_content,
                font_size: el.font_size,
                text_align: el.text_align,
                is_bold: el.is_bold,
                field_name: el.field_name,
                image_data: el.image_data,
                separator_style: el.separator_style,
                barcode_type: el.barcode_type,
                barcode_field: el.barcode_field,
            }));

            const result = await this.rpc(
                `/seisei/ticket/template/${this.state.templateId}/save`,
                {
                    elements,
                    name: this.state.templateName,
                    paper_width: this.state.paperWidth,
                }
            );

            if (result.success) {
                this.notification.add(_t("Template saved successfully"), {
                    type: "success",
                });
            } else {
                this.notification.add(result.error || _t("Failed to save"), {
                    type: "danger",
                });
            }
        } catch (error) {
            console.error("Failed to save template:", error);
            this.notification.add(_t("Failed to save template"), { type: "danger" });
        }
        this.state.isSaving = false;
    }

    /**
     * Generate preview
     */
    async generatePreview() {
        try {
            const result = await this.rpc(
                `/seisei/ticket/template/${this.state.templateId}/preview`,
                {}
            );

            if (result.success) {
                this.state.previewImage = `data:image/png;base64,${result.preview}`;
                this.state.showPreview = true;
            }
        } catch (error) {
            console.error("Failed to generate preview:", error);
        }
    }

    /**
     * Close preview modal
     */
    closePreview() {
        this.state.showPreview = false;
        this.state.previewImage = null;
    }

    /**
     * Handle drag start from toolbox
     */
    onToolboxDragStart(event, elementType) {
        event.dataTransfer.effectAllowed = "copy";
        event.dataTransfer.setData("text/plain", JSON.stringify({
            action: "new",
            type: elementType.type,
            defaultHeight: elementType.defaultHeight,
        }));
    }

    /**
     * Handle element drag start (for reordering)
     */
    onElementDragStart(event, element) {
        this.state.draggedElement = element;
        event.dataTransfer.effectAllowed = "move";
        event.dataTransfer.setData("text/plain", JSON.stringify({
            action: "move",
            uid: element._uid,
        }));
    }

    /**
     * Handle drag over canvas
     */
    onCanvasDragOver(event) {
        event.preventDefault();
        event.dataTransfer.dropEffect = "copy";
    }

    /**
     * Handle drop on canvas
     */
    onCanvasDrop(event, targetIndex = null) {
        event.preventDefault();

        try {
            const data = JSON.parse(event.dataTransfer.getData("text/plain"));

            if (data.action === "new") {
                // Add new element
                const newElement = this.createNewElement(data.type, data.defaultHeight);
                if (targetIndex !== null) {
                    this.state.elements.splice(targetIndex, 0, newElement);
                } else {
                    this.state.elements.push(newElement);
                }
                this.updateSequences();
                this.selectElement(newElement);
                this.saveHistory();
            } else if (data.action === "move" && this.state.draggedElement) {
                // Reorder element
                const sourceIndex = this.state.elements.findIndex(
                    (el) => el._uid === data.uid
                );
                if (sourceIndex !== -1 && targetIndex !== null && sourceIndex !== targetIndex) {
                    const [movedElement] = this.state.elements.splice(sourceIndex, 1);
                    const insertIndex = targetIndex > sourceIndex ? targetIndex - 1 : targetIndex;
                    this.state.elements.splice(insertIndex, 0, movedElement);
                    this.updateSequences();
                    this.saveHistory();
                }
            }
        } catch (error) {
            console.error("Drop error:", error);
        }

        this.state.draggedElement = null;
    }

    /**
     * Create a new element
     */
    createNewElement(type, defaultHeight) {
        const baseElement = {
            _uid: `el_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
            type,
            sequence: (this.state.elements.length + 1) * 10,
            pos_x: 0,
            pos_y: 0,
            width: null,
            height: defaultHeight,
            text_content: type === "text" ? _t("New Text") : "",
            font_size: "normal",
            text_align: "left",
            is_bold: false,
            field_name: type === "dynamic_field" ? "order.name" : "",
            image_data: null,
            separator_style: "solid",
            barcode_type: type === "qrcode" ? "qr" : "code128",
            barcode_field: "",
        };

        return baseElement;
    }

    /**
     * Update sequence numbers
     */
    updateSequences() {
        this.state.elements.forEach((el, idx) => {
            el.sequence = (idx + 1) * 10;
        });
    }

    /**
     * Select an element
     */
    selectElement(element) {
        this.state.selectedElement = element;
    }

    /**
     * Delete selected element
     */
    deleteElement(element) {
        const index = this.state.elements.findIndex((el) => el._uid === element._uid);
        if (index !== -1) {
            this.state.elements.splice(index, 1);
            this.updateSequences();
            if (this.state.selectedElement?._uid === element._uid) {
                this.state.selectedElement = null;
            }
            this.saveHistory();
        }
    }

    /**
     * Move element up in order
     */
    moveElementUp(element) {
        const index = this.state.elements.findIndex((el) => el._uid === element._uid);
        if (index > 0) {
            const temp = this.state.elements[index - 1];
            this.state.elements[index - 1] = element;
            this.state.elements[index] = temp;
            this.updateSequences();
            this.saveHistory();
        }
    }

    /**
     * Move element down in order
     */
    moveElementDown(element) {
        const index = this.state.elements.findIndex((el) => el._uid === element._uid);
        if (index < this.state.elements.length - 1) {
            const temp = this.state.elements[index + 1];
            this.state.elements[index + 1] = element;
            this.state.elements[index] = temp;
            this.updateSequences();
            this.saveHistory();
        }
    }

    /**
     * Duplicate element
     */
    duplicateElement(element) {
        const newElement = {
            ...element,
            _uid: `el_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
        };
        const index = this.state.elements.findIndex((el) => el._uid === element._uid);
        this.state.elements.splice(index + 1, 0, newElement);
        this.updateSequences();
        this.selectElement(newElement);
        this.saveHistory();
    }

    /**
     * Update element property
     */
    updateElementProperty(element, property, value) {
        element[property] = value;
        this.saveHistory();
    }

    /**
     * Handle keyboard shortcuts
     */
    onKeyDown(event) {
        // Ctrl+S: Save
        if (event.ctrlKey && event.key === "s") {
            event.preventDefault();
            this.saveTemplate();
        }
        // Ctrl+Z: Undo
        else if (event.ctrlKey && event.key === "z" && !event.shiftKey) {
            event.preventDefault();
            this.undo();
        }
        // Ctrl+Shift+Z or Ctrl+Y: Redo
        else if ((event.ctrlKey && event.shiftKey && event.key === "z") ||
                 (event.ctrlKey && event.key === "y")) {
            event.preventDefault();
            this.redo();
        }
        // Delete: Remove selected element
        else if (event.key === "Delete" && this.state.selectedElement) {
            this.deleteElement(this.state.selectedElement);
        }
    }

    /**
     * Save current state to history
     */
    saveHistory() {
        // Clone current elements
        const snapshot = JSON.stringify(this.state.elements);

        // Remove future history if we're not at the end
        if (this.state.historyIndex < this.state.history.length - 1) {
            this.state.history = this.state.history.slice(0, this.state.historyIndex + 1);
        }

        // Add to history
        this.state.history.push(snapshot);
        this.state.historyIndex = this.state.history.length - 1;

        // Limit history size
        if (this.state.history.length > 50) {
            this.state.history.shift();
            this.state.historyIndex--;
        }
    }

    /**
     * Undo last action
     */
    undo() {
        if (this.state.historyIndex > 0) {
            this.state.historyIndex--;
            const snapshot = JSON.parse(this.state.history[this.state.historyIndex]);
            this.state.elements = snapshot;
            this.state.selectedElement = null;
        }
    }

    /**
     * Redo last undone action
     */
    redo() {
        if (this.state.historyIndex < this.state.history.length - 1) {
            this.state.historyIndex++;
            const snapshot = JSON.parse(this.state.history[this.state.historyIndex]);
            this.state.elements = snapshot;
            this.state.selectedElement = null;
        }
    }

    /**
     * Check if can undo
     */
    get canUndo() {
        return this.state.historyIndex > 0;
    }

    /**
     * Check if can redo
     */
    get canRedo() {
        return this.state.historyIndex < this.state.history.length - 1;
    }

    /**
     * Get canvas width in pixels
     */
    get canvasWidth() {
        return this.state.paperWidth === 58 ? 384 : 576;
    }

    /**
     * Go back to template list
     */
    goBack() {
        this.actionService.doAction({
            type: "ir.actions.act_window",
            res_model: "seisei.ticket.template",
            views: [[false, "kanban"], [false, "list"], [false, "form"]],
            target: "current",
        });
    }

    /**
     * Get element icon class
     */
    getElementIcon(type) {
        const typeInfo = this.elementTypes.find((t) => t.type === type);
        return typeInfo ? typeInfo.icon : "fa-question";
    }

    /**
     * Get element type label
     */
    getElementLabel(type) {
        const typeInfo = this.elementTypes.find((t) => t.type === type);
        return typeInfo ? typeInfo.label : type;
    }

    /**
     * Handle image upload
     */
    async onImageUpload(event, element) {
        const file = event.target.files[0];
        if (!file) return;

        const reader = new FileReader();
        reader.onload = (e) => {
            // Extract base64 data (remove data:image/...;base64, prefix)
            const base64Data = e.target.result.split(",")[1];
            element.image_data = base64Data;
            this.saveHistory();
        };
        reader.readAsDataURL(file);
    }
}

// Register as client action
registry.category("actions").add("seisei_ticket_editor", TicketEditor);
