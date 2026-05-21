/** @odoo-module **/

import { registry } from "@web/core/registry";
import { patch } from "@web/core/utils/patch";

const FormController = registry.category("views").get("form").Controller;

patch(FormController, {
    setup() {
        super.setup(); // <-- call superclass method with `super`, NOT `this._super`

        // Your custom logic here
        setTimeout(() => {
            const managersGroup = document.querySelector("group[name='managers']");
            if (managersGroup) {
                managersGroup.style.display = "none";
            }
        }, 500);
    },
});

// Hide the managers group in the form view that is manager approval and attendance approval