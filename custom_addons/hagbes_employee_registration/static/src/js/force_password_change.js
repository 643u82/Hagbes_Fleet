/** @odoo-module */

import { registry } from "@web/core/registry";
import { session } from "@web/session";

registry.category("main_components").add("ForcePasswordRedirect", {
    setup() {
        if (session.user_context.must_change_password) {
            window.location = "/web/force_password_change";
        }
    },
});
