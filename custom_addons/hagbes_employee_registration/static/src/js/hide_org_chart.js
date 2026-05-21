/** @odoo-module **/

import { registry } from "@web/core/registry";
const { onMounted } = owl;

registry.category("view_hooks").add("hide_org_chart", {
    setup() {
        onMounted(() => {
            const rightColumn = document.querySelector("#o_employee_right");
            const orgTitle = Array.from(document.querySelectorAll("div.o_horizontal_separator"))
                .find(el => el.textContent.includes("Organization Chart"));

            if (rightColumn) {
                rightColumn.style.display = "none";
            }

            if (orgTitle) {
                orgTitle.style.display = "none";
            }
        });
    },
});
