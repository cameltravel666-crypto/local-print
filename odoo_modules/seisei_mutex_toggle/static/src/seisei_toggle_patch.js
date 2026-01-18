import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";
import { BooleanToggleField } from "@web/views/fields/boolean_toggle/boolean_toggle_field";

patch(BooleanToggleField.prototype, {
    async onChange(newValue) {
        this.state.value = newValue;
        const changes = { [this.props.name]: newValue };
        await this.props.record.update(changes, { save: false });
    },
});
