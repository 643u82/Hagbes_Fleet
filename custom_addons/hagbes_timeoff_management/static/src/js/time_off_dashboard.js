/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import {
    TimeOffDashboardCalendarRenderer,
} from "@hr_holidays/views/calendar/calendar_renderer";

import { TimeOffDashboard } from "@hr_holidays/dashboard/time_off_dashboard";

import { useService } from "@web/core/utils/hooks";
import { onWillStart } from "@odoo/owl";

console.log("custom_timeoff: time_off_dashboard.js loaded");

patch(TimeOffDashboardCalendarRenderer, {
    
    setup() {
        super.setup?.(...arguments);   
        this.orm = useService("orm");
        this.user = useService("user");
        this.yearBalances = { year_2: 0, year_1: 0, current: 0, total: 0 };
        this.loadUserBalances();
    },

    async loadUserBalances() {
        try {
            const data = await this.orm.call(
                "hr.leave.allocation",
                "get_logged_in_user_balances",
                []
            );
            this.yearBalances = data || {};
            console.log("custom_timeoff: calendar renderer loaded balances", this.yearBalances);
            this.render(true);
        } catch (error) {
            console.error("Failed to load user balances:", error);
        }
    },

    _renderDashboard() {
        const b = this.yearBalances;
        const cy = new Date().getFullYear();
        return `
            <div class="o_timeoff_dashboard_header d-flex justify-content-around align-items-center">
                <div class="o_stat_box text-center">
                    <div class="o_stat_value fw-bold fs-4">${b.year_2.toFixed(1)}</div>
                    <div class="o_stat_label text-muted">${cy - 2} Balance</div>
                </div>
                <div class="o_stat_box text-center">
                    <div class="o_stat_value fw-bold fs-4">${b.year_1.toFixed(1)}</div>
                    <div class="o_stat_label text-muted">${cy - 1} Balance</div>
                </div>
                <div class="o_stat_box text-center">
                    <div class="o_stat_value fw-bold fs-4">${b.current.toFixed(1)}</div>
                    <div class="o_stat_label text-muted">${cy} Balance</div>
                </div>
                <div class="o_stat_box text-center">
                    <div class="o_stat_value fw-bold fs-4 text-success">${b.total.toFixed(1)}</div>
                    <div class="o_stat_label text-muted">Total Balance</div>
                </div>
            </div>
        `;
    },
});


const _originalLoad = TimeOffDashboard.prototype.loadDashboardData;
patch(TimeOffDashboard, {
    async loadDashboardData(date = false) {
        console.log("custom_timeoff: patched loadDashboardData called", { date });
        // call original
        await _originalLoad.call(this, date);
        try {
            if (this.state && Array.isArray(this.state.holidays)) {
                console.log("custom_timeoff: before filter", this.state.holidays.map(c=>c.title||c.name));
                this.state.holidays = this.state.holidays.filter((card) => {
                    const title = (card.title || card.name || "").toString().trim();
                    return title !== "Pending Requests";
                });
                console.log("custom_timeoff: after filter", this.state.holidays.map(c=>c.title||c.name));
                 
                this.render && this.render(true);
            }
            
            try {
                if (this.orm && typeof this.orm.call === 'function') {
                    const data = await this.orm.call(
                        "hr.leave.allocation",
                        "get_logged_in_user_balances",
                        []
                    );
                    if (data) {
                        this.state = this.state || {};
                        // numeric values
                        this.state.my_custom_field_1 = (data.year_2 != null) ? parseFloat(data.year_2) : 0;
                        this.state.my_custom_field_2 = (data.year_1 != null) ? parseFloat(data.year_1) : 0;
                        this.state.my_custom_field_3 = (data.current != null) ? parseFloat(data.current) : 0;
                        this.state.my_custom_field_4 = (data.total != null) ? parseFloat(data.total) : 0;
                        // compute labels using the current year
                        const cy = new Date().getFullYear();
                        this.state.my_custom_label_year2 = `${cy - 2} Balance`;
                        this.state.my_custom_label_year1 = `${cy - 1} Balance`;
                        this.state.my_custom_label_current = `${cy} Balance`;
                        console.log("custom_timeoff: loaded balances (from loadDashboardData)", data, {
                            y2: this.state.my_custom_field_1,
                            y1: this.state.my_custom_field_2,
                            current: this.state.my_custom_field_3,
                            total: this.state.my_custom_field_4,
                        });
                        this.render && this.render(true);
                    }
                }
            } catch (err) {
                console.error("custom_timeoff: error fetching balances in loadDashboardData", err);
            }
        } catch (e) {
            console.error("Error filtering Pending Requests card:", e);
        }
    },
});


patch(TimeOffDashboard, {
    setup() {
        
        super.setup?.(...arguments);
        this.orm = useService("orm");

        
        try {
            if (!this.state) {
                this.state = {};
            }
            this.state.my_custom_field_1 = 0;
            this.state.my_custom_field_2 = 0;
            this.state.my_custom_field_3 = 0;
            this.state.my_custom_field_4 = 0;
        } catch (e) {
            console.error("custom_timeoff: error initializing custom fields", e);
        }

        onWillStart(async () => {
            try {
                const data = await this.orm.call(
                    "hr.leave.allocation",
                    "get_logged_in_user_balances",
                    []
                );
                if (data) {
                    // store numeric values 
                    this.state.my_custom_field_1 = (data.year_2 != null) ? parseFloat(data.year_2) : 0;
                    this.state.my_custom_field_2 = (data.year_1 != null) ? parseFloat(data.year_1) : 0;
                    this.state.my_custom_field_3 = (data.current != null) ? parseFloat(data.current) : 0;
                    this.state.my_custom_field_4 = (data.total != null) ? parseFloat(data.total) : 0;
                    console.log("custom_timeoff: loaded balances", data, {
                        y2: this.state.my_custom_field_1,
                        y1: this.state.my_custom_field_2,
                        current: this.state.my_custom_field_3,
                        total: this.state.my_custom_field_4,
                    });
                    this.render && this.render(true);
                }
            } catch (err) {
                console.error("custom_timeoff: failed to load custom stat balances", err);
            }
        });
    },
});
