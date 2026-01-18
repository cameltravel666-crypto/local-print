
import { BooleanToggleField, booleanToggleField } from "@web/views/fields/boolean_toggle/boolean_toggle_field";
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

export class MutexToggleField extends BooleanToggleField {

    static props = {
        ...standardFieldProps,
        ...BooleanToggleField.props,
        template: {
            optional: true
        },
        props: {
            optional: true
        },
        '*': true,
    };

    async onChange(newValue) {
        const changes = { [this.props.name]: newValue };
        await this.props.record.update(changes);

        if (newValue) {
            let list = this.__owl__.parent.parent.component.props.list;
            let records = list.records;
            for (let i = 0; i < records.length; i++) {
                let record = records[i];
                if (record.id != this.props.record.id) {
                    record.update({ [this.props.name]: false})
                }
            }
        }
    }
};

export const mutexToggleField = {
    ...booleanToggleField,
    component: MutexToggleField,
};

registry.category("fields").add("mutex_toggle", mutexToggleField);
