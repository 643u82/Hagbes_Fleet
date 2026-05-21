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

export class BalanceSheetReport extends Component {
    static template = "custom_financial_reports.BalanceSheetReport";
    static components = { Layout, Dropdown, DropdownItem, DateTimePicker };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        
        this.state = useState({
            date_to: DateTime.now(),
            comparison_option: 'no_comparison',
            comparison_date: DateTime.now().minus({ years: 1 }),
            target_move: 'posted',
            journal_ids: [],
            journals: [], // List of available journals
            data: null,
            loading: true,
        });

        onWillStart(async () => {
            // Load Journals
            const journals = await this.orm.searchRead("account.journal", [], ["id", "name", "code"]);
            this.state.journals = journals;
            await this.loadData();
        });
    }

    async loadData() {
        this.state.loading = true;
        const options = {
            date_to: serializeDate(this.state.date_to),
            comparison_option: this.state.comparison_option,
            comparison_date: serializeDate(this.state.comparison_date),
            target_move: this.state.target_move,
            journal_ids: this.state.journal_ids,
        };

        try {
            this.state.data = await this.orm.call(
                "report.custom_financial_reports.report_balance_sheet_ifrs",
                "get_report_data",
                [options]
            );
        } finally {
            this.state.loading = false;
        }
    }

    // --- Handlers ---

    async onDateChanged(date) {
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
        // We need to create a wizard record first or reuse the logic. 
        // For simplicity, we trigger the report action directly with data
        const data = {
            date_to: serializeDate(this.state.date_to),
            comparison_option: this.state.comparison_option,
            comparison_date: serializeDate(this.state.comparison_date),
            journal_ids: this.state.journal_ids,
            target_move: this.state.target_move,
        };
        await this.action.doAction({
            type: 'ir.actions.report',
            report_type: 'qweb-pdf',
            report_name: 'custom_financial_reports.action_report_balance_sheet_ifrs',
            report_file: 'custom_financial_reports.report_balance_sheet_ifrs',
            data: data,
        });
    }

    async exportXlsx() {
         const data = {
            date_to: serializeDate(this.state.date_to),
            comparison_option: this.state.comparison_option,
            comparison_date: serializeDate(this.state.comparison_date),
            journal_ids: this.state.journal_ids,
            target_move: this.state.target_move,
        };
        await this.action.doAction({
            type: 'ir.actions.report',
            report_type: 'xlsx',
            report_name: 'custom_financial_reports.report_balance_sheet_xlsx',
            report_file: 'Balance Sheet',
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
}

registry.category("actions").add("custom_financial_reports.balance_sheet_client_action", BalanceSheetReport);