/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { registry } from "@web/core/registry";

const fieldRegistry = registry.category("fields");

// Delay patching until registry is ready
function patchDatetimeField() {
    const DatetimeField = fieldRegistry.get("datetime");
    if (!DatetimeField || !DatetimeField.prototype) {
        return false;
    }

    patch(DatetimeField.prototype, {
        setup() {
            super.setup();

            if (
                this.props?.name === "request_date_from" ||
                this.props?.name === "request_date_to"
            ) {
                this.options = {
                    ...this.options,
                    enableTime: true,
                    time_24hr: false,
                };
            }
        },
    });

    console.log("custom_timeoff: DatetimeField patched for 12hr format");
    return true;
}

// Try immediately
if (!patchDatetimeField()) {
    // Retry once the app is ready
    window.requestAnimationFrame(() => patchDatetimeField());
}


// /** @odoo-module **/
// import { patch } from 'web.utils';
// import { DatetimeField } from '@web/views/fields/datetime/datetime_field';
// import { registry } from '@web/core/registry';

// patch(DatetimeField.prototype, 'hr_leave_force_12hr', {
//     setup() {
//         this._super(...arguments);

//         // Force 12-hour for leave datetime fields
//         if (this.props.name === 'request_date_from' || this.props.name === 'request_date_to') {
//             this.options = Object.assign({}, this.options, {
//                 enableTime: true,
//                 time_24hr: false, // 12-hour format
//             });
//         }
//     },
// });

// registry.category('fields').add('datetime', DatetimeField);
