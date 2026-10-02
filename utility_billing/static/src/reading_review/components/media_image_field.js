/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, useState } from "@odoo/owl";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { useRecordObserver } from "@web/model/relational_model/utils";

export class UtilityMediaImageField extends Component {
    setup() {
        this.state = useState({ value: this.props.record.data[this.props.name] });
        useRecordObserver((record) => {
            this.state.value = record.data[this.props.name];
        });
    }
}

UtilityMediaImageField.template = "utility_billing.UtilityMediaImageField";
UtilityMediaImageField.supportedTypes = ["char"];
UtilityMediaImageField.props = standardFieldProps;

registry.category("fields").add("utility_media_image", {
    component: UtilityMediaImageField,
    supportedTypes: ["char"],
});
