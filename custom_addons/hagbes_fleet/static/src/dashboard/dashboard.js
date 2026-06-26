/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component } from "@odoo/owl";

export class HagbesFleetDashboard extends Component {
    static template = "hagbes_fleet.Dashboard";

    // Provide safe defaults so the OWL template never crashes / stays blank
    // if no data-loading logic exists yet.
    metrics = {
        total_vehicles: 0,
        available_vehicles: 0,
        allocated_vehicles: 0,
        allocation_count: 0,
        total_trips: 0,
        total_fleet_distance: 0,
        average_distance: 0,
        active_allocations: 0,
        in_maintenance_vehicles: 0,
        out_of_service_vehicles: 0,
        vehicles_due: 0,
        vehicles_overdue: 0,
        total_maintenance_events: 0,
        total_maintenance_cost: 0,
    };

    async _onOpenReport(actionName) {
        return this.env.services.action.doAction(actionName);
    }
}


registry.category("actions").add("hagbes_fleet.Dashboard", HagbesFleetDashboard);
