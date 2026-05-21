/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, onMounted, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class CustomOrgChart extends Component {
    setup() {
        this.orm = useService("orm");
        this.state = useState({ employees: [] });

        onMounted(async () => {
            const employees = await this.orm.searchRead("hr.employee", [], ["name", "parent_id", "job_title"]);
            this.state.employees = employees;
            console.log("📦 Employees Fetched:", employees);

            const container = document.querySelector("#custom-org-chart-container");
            if (!container) return;

            const nodes = employees.map(emp => ({
                id: emp.id,
                name: emp.name,
                title: emp.job_title || "",
                pid: emp.parent_id?.[0] || null,
            }));

            if (typeof OrgChart !== "undefined") {
                new OrgChart(container, {
                    nodes,
                    nodeBinding: {
                        field_0: "name",
                        field_1: "title"
                    }
                });
            } else {
                console.error("OrgChart library not found.");
            }
        });
    }
}
CustomOrgChart.template = "hr_custom_org_chart.CustomOrgChart";

// ✅ THIS LINE is the fix
registry.category("client_actions").add("custom_org_chart", CustomOrgChart);



// odoo.define('your_module.org_chart_patch', function (require) {
//     "use strict";

//     const OrgChartWidget = require('hr_org_chart.OrgChartWidget');

//     OrgChartWidget.include({
//         async loadData() {
//             const result = await this._rpc({
//                 route: '/orgchart/data',
//                 params: {},
//             });
//             return result;
//         },

//         _onAddClick() {
//             this.do_action({
//                 type: 'ir.actions.act_window',
//                 name: 'Create Job Position',
//                 res_model: 'hr.job',
//                 view_mode: 'form',
//                 target: 'new',
//             });
//         },
//     });
// });
