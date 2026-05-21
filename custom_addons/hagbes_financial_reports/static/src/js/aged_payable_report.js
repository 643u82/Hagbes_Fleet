/** @odoo-module */
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, onWillStart, useState, useRef } from "@odoo/owl";
import { Dropdown } from "@web/core/dropdown/dropdown";
import { DropdownItem } from "@web/core/dropdown/dropdown_item";

export class AgedPayableReport extends Component {
    static template = "AgedPayableTemp";
    static components = { Dropdown, DropdownItem };
    setup() {
        this.orm = useService("orm");
        this.actionService = useService("action");
        this.state = useState({
            data: {
                lines: [],
                move_line: [],
                total: {},
                diff0_sum_display: 0,
                diff1_sum_display: 0,
                diff2_sum_display: 0,
                diff3_sum_display: 0,
                diff4_sum_display: 0,
                diff5_sum_display: 0,
                total_debit_display: 0,
            },
            options: this.props.action.context || {},
            date_to: new Date().toISOString().split('T')[0],
        });

        // Initialize options if empty
        if (!this.state.options.date_to) {
            this.state.options.date_to = this.state.date_to;
        }
        if (!this.state.options.target_move) {
            this.state.options.target_move = 'posted';
        }
        if (!this.state.options.date_compare_mode) {
            this.state.options.date_compare_mode = 'due_date';
        }

        onWillStart(async () => {
            await this.getReportData();
        });
    }

    async getReportData() {
        // Ensure options are passed correctly
        const result = await this.orm.call(
            "report.custom_financial_reports.report_aged_payable",
            "get_report_data",
            [this.state.options]
        );
        this.state.data = result;
        this.state.date_to = result.date_at; // Update display date from backend
    }

    async applyFilter(filterType) {
        const today = new Date();
        let newDate;

        if (filterType === 'today') {
            newDate = today;
        } else if (filterType === 'last-month-end') {
            newDate = new Date(today.getFullYear(), today.getMonth(), 0);
        } else if (filterType === 'last-quarter-end') {
            const quarterMonth = Math.floor((today.getMonth() + 3) / 3) * 3 - 3; // Start of current quarter
            newDate = new Date(today.getFullYear(), quarterMonth, 0);
        } else if (filterType === 'last-year-end') {
            newDate = new Date(today.getFullYear(), 0, 0);
        } else if (filterType.target && filterType.target.value) {
            // Input event
            newDate = new Date(filterType.target.value);
        }

        if (newDate) {
            this.state.options.date_to = newDate.toISOString().split('T')[0];
            await this.getReportData();
        }
    }

    async toggleTargetMove() {
        this.state.options.target_move = this.state.options.target_move === 'posted' ? 'all' : 'posted';
        await this.getReportData();
    }

    async toggleDateType() {
        this.state.options.date_compare_mode = this.state.options.date_compare_mode === 'due_date' ? 'invoice_date' : 'due_date';
        await this.getReportData();
    }

    // Navigation methods
    async openPartner(ev) {
        const partnerId = parseInt(ev.currentTarget.dataset.id);
        if (partnerId) {
            await this.actionService.doAction({
                type: 'ir.actions.act_window',
                res_model: 'res.partner',
                res_id: partnerId,
                views: [[false, 'form']],
                target: 'current',
            });
        }
    }

    async gotoJournalItem(ev) {
        const partnerId = parseInt(ev.currentTarget.dataset.id);
        if (partnerId) {
            await this.actionService.doAction({
                type: 'ir.actions.act_window',
                name: 'Journal Items',
                res_model: 'account.move.line',
                domain: [['partner_id', '=', partnerId], ['account_id.account_type', '=', 'liability_payable'], ['parent_state', '=', 'posted']],
                views: [[false, 'list'], [false, 'form']],
                target: 'current',
            });
        }
    }

    async gotoJournalEntry(ev) {
        const moveId = parseInt(ev.currentTarget.dataset.id);
        if (moveId) {
            await this.actionService.doAction({
                type: 'ir.actions.act_window',
                res_model: 'account.move',
                res_id: moveId,
                views: [[false, 'form']],
                target: 'current',
            });
        }
    }

    async onPartnerSearchInput(ev) {
        const query = ev.target.value;
        if (query.length > 2) {
            const domain = [['name', 'ilike', query]];
            const partners = await this.orm.searchRead("res.partner", domain, ['id', 'name'], { limit: 10 });
            this.state.partner_results = partners;
        } else {
            this.state.partner_results = [];
        }
    }

    async onPartnerFilterSelected(partnerId) {
        if (!this.state.options.partner_ids) {
            this.state.options.partner_ids = [];
        }
        const index = this.state.options.partner_ids.indexOf(partnerId);
        if (index > -1) {
            this.state.options.partner_ids.splice(index, 1);
        } else {
            this.state.options.partner_ids.push(partnerId);
        }
        await this.getReportData();
    }

    async print_pdf() {
        await this.actionService.doAction({
            type: 'ir.actions.report',
            report_type: 'qweb-pdf',
            report_name: 'custom_financial_reports.report_aged_payable',
            report_file: 'custom_financial_reports.report_aged_payable',
            data: this.state.options,
            display_name: 'Aged Payable',
        });
    }

    async print_xlsx() {
        // Placeholder for XLSX printing if needed, or link to existing action
        // Usually this calls a controller or another action.
        // For now keeping it compatible with existing code structure if any.
    }
}
AgedPayableReport.template = "AgedPayableTemp";
registry.category("actions").add("a_p", AgedPayableReport);
