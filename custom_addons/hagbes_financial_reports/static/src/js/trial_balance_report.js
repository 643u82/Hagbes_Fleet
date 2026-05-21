/** @odoo-module */

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, onWillStart, useState } from "@odoo/owl";
import { Dropdown } from "@web/core/dropdown/dropdown";
import { DropdownItem } from "@web/core/dropdown/dropdown_item";
import { DateTimePicker } from "@web/core/datetime/datetime_picker";
import { serializeDate } from "@web/core/l10n/dates";
import { formatCurrency } from "@web/core/currency";
const { DateTime } = luxon;

export class TrialBalanceReport extends Component {
    static components = { Dropdown, DropdownItem, DateTimePicker };
    static template = "TrialBalanceTemp";

    setup() {
        this.orm = useService("orm");
        this.actionService = useService("action");
        
        const today = DateTime.now();
        const startOfMonth = today.startOf("month");
        const endOfMonth = today.endOf("month");

        this.state = useState({
            data: null,
            date_from: startOfMonth,
            date_to: endOfMonth,
            date_filter: 'month', // month, quarter, year, custom
            comparison_option: 'no_comparison',
            comparison_date: startOfMonth.minus({ years: 1 }),
            journal_ids: [],
            journals: [],
            target_move: 'posted',
        });

        // Initialize from context if available
        if (this.props.action.context && this.props.action.context.date_from) {
             this.state.date_from = DateTime.fromISO(this.props.action.context.date_from);
             this.state.date_to = DateTime.fromISO(this.props.action.context.date_to);
             this.state.date_filter = 'custom';
        }
        if (this.props.action.context && this.props.action.context.target_move) {
            this.state.target_move = this.props.action.context.target_move;
        }

        onWillStart(async () => {
            await this.getReportData();
        });
    }

    async getReportData() {
        const options = {
            date_from: serializeDate(this.state.date_from),
            date_to: serializeDate(this.state.date_to),
            target_move: this.state.target_move,
            journal_ids: this.state.journal_ids,
        };

        const result = await this.orm.call(
            "report.custom_financial_reports.report_trial_balance",
            "get_report_data",
            [options]
        );
        this.state.data = result;
        this.state.journals = result.journals || [];
    }

    // --- Filter Handlers ---

    async onDateChanged(date) {
        this.state.date_to = date;
        this.state.date_filter = 'custom';
        await this.getReportData();
    }

    async onFilterTypeChanged(type) {
        this.state.date_filter = type;
        const today = DateTime.now();
        if (type === 'month') {
            this.state.date_from = today.startOf('month');
            this.state.date_to = today.endOf('month');
        } else if (type === 'quarter') {
            this.state.date_from = today.startOf('quarter');
            this.state.date_to = today.endOf('quarter');
        } else if (type === 'year') {
            this.state.date_from = today.startOf('year');
            this.state.date_to = today.endOf('year');
        }
        await this.getReportData();
    }

    async onCustomDateFromChanged(date) {
        this.state.date_from = date;
        await this.getReportData();
    }

    async onCustomDateToChanged(date) {
        this.state.date_to = date;
        await this.getReportData();
    }

    async onComparisonOptionChanged(option) {
        this.state.comparison_option = option;
        // Logic for comparison data fetching would go here or in getReportData
        // For now, we just update the UI state
    }

    async onComparisonDateChanged(date) {
        this.state.comparison_date = date;
    }

    async onJournalChanged(journalId) {
        if (this.state.journal_ids.includes(journalId)) {
            this.state.journal_ids = this.state.journal_ids.filter(id => id !== journalId);
        } else {
            this.state.journal_ids.push(journalId);
        }
        await this.getReportData();
    }

    async onTargetMoveChanged(isPosted) {
        this.state.target_move = isPosted ? 'posted' : 'all';
        await this.getReportData();
    }

    // --- Helpers ---

    formatDate(dateStr) {
        if (!dateStr) return "";
        // Handle both Luxon DateTime objects and ISO strings
        if (typeof dateStr === 'object' && dateStr.toFormat) {
            return dateStr.toFormat("MMM yyyy");
        }
        return DateTime.fromISO(dateStr).toFormat("MMM yyyy");
    }

    formatCurrency(amount) {
        if (!this.state.data) return "0.00";
        // Use a default currency ID if not available, or fetch company currency
        // For simplicity in this snippet, we format as number with 2 decimals
        return new Intl.NumberFormat('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(amount);
    }

    async print_pdf() {
        const options = {
            date_from: serializeDate(this.state.date_from),
            date_to: serializeDate(this.state.date_to),
            target_move: this.state.target_move,
            journal_ids: this.state.journal_ids,
        };
        await this.actionService.doAction({
            type: 'ir.actions.report',
            report_type: 'qweb-pdf',
            report_name: 'custom_financial_reports.action_report_trial_balance',
            data: options,
            display_name: 'Trial Balance',
        });
    }
}
registry.category("actions").add("t_b", TrialBalanceReport);
