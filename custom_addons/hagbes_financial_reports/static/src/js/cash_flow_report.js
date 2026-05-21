/** @odoo-module */

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, useState, onWillStart } from "@odoo/owl";
import { Layout } from "@web/search/layout";
import { Dropdown } from "@web/core/dropdown/dropdown";
import { DropdownItem } from "@web/core/dropdown/dropdown_item";
import { DateTimePicker } from "@web/core/datetime/datetime_picker";
import { serializeDate } from "@web/core/l10n/dates";
const { DateTime } = luxon;

export class CashFlowReport extends Component {
    static template = "custom_financial_reports.CashFlowReport";
    static components = { Layout, Dropdown, DropdownItem, DateTimePicker };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        
        this.state = useState({
            filter_type: 'this_year',
            anchor_date: DateTime.now(),
            date_from: DateTime.now().startOf('year'),
            date_to: DateTime.now().endOf('year'),
            comparison_option: 'no_comparison',
            comparison_date: DateTime.now().minus({ years: 1 }),
            target_move: 'posted',
            journal_ids: [],
            journals: [],
            data: null,
            loading: true,
        });

        onWillStart(async () => {
            const journals = await this.orm.searchRead("account.journal", [], ["id", "name", "code"]);
            this.state.journals = journals;
            await this.loadData();
        });
    }

    async loadData() {
        this.state.loading = true;
        const options = {
            date_from: serializeDate(this.state.date_from),
            date_to: serializeDate(this.state.date_to),
            comparison_option: this.state.comparison_option,
            comparison_date: serializeDate(this.state.comparison_date),
            target_move: this.state.target_move,
            journal_ids: this.state.journal_ids,
        };

        try {
            // CALLING CASH FLOW REPORT MODEL
            this.state.data = await this.orm.call(
                "report.custom_financial_reports.report_cash_flow",
                "get_report_data",
                [options]
            );
        } finally {
            this.state.loading = false;
        }
    }

    async onFilterTypeChanged(type) {
        this.state.filter_type = type;
        this.recalculateDates();
        await this.loadData();
    }

    async onAnchorDateChanged(date) {
        this.state.anchor_date = date;
        this.recalculateDates();
        await this.loadData();
    }

    recalculateDates() {
        const anchor = this.state.anchor_date;
        if (this.state.filter_type === 'month') {
            this.state.date_from = anchor.startOf('month');
            this.state.date_to = anchor.endOf('month');
        } else if (this.state.filter_type === 'quarter') {
            this.state.date_from = anchor.startOf('quarter');
            this.state.date_to = anchor.endOf('quarter');
        } else if (this.state.filter_type === 'year' || this.state.filter_type === 'this_year') {
            this.state.date_from = anchor.startOf('year');
            this.state.date_to = anchor.endOf('year');
        }
        // Custom handles its own dates via separate pickers
    }

    async onCustomDateFromChanged(date) {
        this.state.date_from = date;
        await this.loadData();
    }

    async onCustomDateToChanged(date) {
        this.state.date_to = date;
        await this.loadData();
    }

    async onComparisonOptionChanged(option) {
        this.state.comparison_option = option;
        await this.loadData();
    }

    async onComparisonDateChanged(date) {
        this.state.comparison_date = date;
        await this.loadData();
    }

    async onTargetMoveChanged(val) {
        this.state.target_move = val ? 'posted' : 'all';
        await this.loadData();
    }

    async onJournalChanged(journalId) {
        const index = this.state.journal_ids.indexOf(journalId);
        if (index > -1) {
            this.state.journal_ids.splice(index, 1);
        } else {
            this.state.journal_ids.push(journalId);
        }
        await this.loadData();
    }

    async printPdf() {
        const data = {
            date_from: serializeDate(this.state.date_from),
            date_to: serializeDate(this.state.date_to),
            comparison_option: this.state.comparison_option,
            comparison_date: serializeDate(this.state.comparison_date),
            journal_ids: this.state.journal_ids,
            target_move: this.state.target_move,
        };
        await this.action.doAction({
            type: 'ir.actions.report',
            report_type: 'qweb-pdf',
            report_name: 'custom_financial_reports.action_report_cash_flow',
            report_file: 'custom_financial_reports.report_cash_flow',
            data: data,
        });
    }

    async exportXlsx() {
         const data = {
            date_from: serializeDate(this.state.date_from),
            date_to: serializeDate(this.state.date_to),
            comparison_option: this.state.comparison_option,
            comparison_date: serializeDate(this.state.comparison_date),
            journal_ids: this.state.journal_ids,
            target_move: this.state.target_move,
        };
        await this.action.doAction({
            type: 'ir.actions.report',
            report_type: 'xlsx',
            report_name: 'custom_financial_reports.report_cash_flow_xlsx',
            report_file: 'Cash Flow',
            data: data,
        });
    }

    async openLine(line) {
        if (!line.domain) return;
        await this.action.doAction({
            type: "ir.actions.act_window",
            name: line.name,
            res_model: "account.move.line",
            view_mode: "list,form",
            domain: line.domain,
            target: "current",
        });
    }
    
    formatCurrency(amount) {
        if (!amount) return "0.00";
        return amount.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    }

    formatDate(dateObj) {
        if (!dateObj) return "";
        if (typeof dateObj === 'string') {
             return DateTime.fromISO(dateObj).toFormat("MM/dd/yyyy");
        }
        return dateObj.toFormat("MM/dd/yyyy");
    }

    getPeriodName() {
        if (this.state.filter_type === 'month') {
            return this.state.anchor_date.toFormat("MMMM yyyy");
        } else if (this.state.filter_type === 'quarter') {
            const start = this.state.date_from.toFormat("MMM");
            const end = this.state.date_to.toFormat("MMM yyyy");
            return `${start} - ${end}`;
        } else if (this.state.filter_type === 'year' || this.state.filter_type === 'this_year') {
            return this.state.anchor_date.toFormat("yyyy");
        }
        return "Custom";
    }
}

registry.category("actions").add("custom_financial_reports.cash_flow_client_action", CashFlowReport);
