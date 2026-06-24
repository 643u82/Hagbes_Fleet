/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component } from "@odoo/owl";

export class HagbesFleetDashboard extends Component {
    static template = "hagbes_fleet.Dashboard";

    async _onOpenReport(actionName) {
        return this.env.services.action.doAction(actionName);
    }
}

registry.category("actions").add("hagbes_fleet.Dashboard", HagbesFleetDashboard);
