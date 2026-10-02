/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component } from "@odoo/owl";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

export class UtilityMediaImageField extends Component {}

UtilityMediaImageField.template = "utility_billing.UtilityMediaImageField";
UtilityMediaImageField.supportedTypes = ["char"];
UtilityMediaImageField.props = standardFieldProps;

registry.category("fields").add("utility_media_image", {
    component: UtilityMediaImageField,
    supportedTypes: ["char"],
});
