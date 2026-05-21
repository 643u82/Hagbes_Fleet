/** @odoo-module */

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, onWillStart, useState } from "@odoo/owl";
import { Dropdown } from "@web/core/dropdown/dropdown";
import { DropdownItem } from "@web/core/dropdown/dropdown_item";
import { DateTimePicker } from "@web/core/datetime/datetime_picker";
import { serializeDate, deserializeDate } from "@web/core/l10n/dates";
import { formatCurrency } from "@web/core/currency";
const { DateTime } = luxon;

export class GeneralLedgerReport extends Component {
    setup() {
        this.orm = useService("orm");
        this.actionService = useService("action");
        
        const today = DateTime.now();
        const firstDay = today.startOf('month');

        this.state = useState({
            data: null,
            journals: [],
            options: {
                date_from: firstDay,
                date_to: today,
                target_move: 'posted',
                journal_ids: [],
                account_ids: [],
            },
            filter_type: 'month', // month, quarter, year, custom
            expanded_accounts: new Set(),
            search_filter: "",
        });

        // Handle context from action
        if (this.props.action.context && this.props.action.context.date_from) {
             this.state.options.date_from = deserializeDate(this.props.action.context.date_from);
             this.state.options.date_to = deserializeDate(this.props.action.context.date_to);
             this.state.filter_type = 'custom';
        }

        onWillStart(async () => {
            await this.loadJournals();
            await this.getReportData();
        });
    }

    async loadJournals() {
        this.state.journals = await this.orm.searchRead("account.journal", [], ['id', 'code', 'name']);
    }

    async getReportData() {
        // Prepare options for backend (convert dates to strings)
        const options = {
            ...this.state.options,
            date_from: serializeDate(this.state.options.date_from),
            date_to: serializeDate(this.state.options.date_to),
        };

        const result = await this.orm.call(
            "report.custom_financial_reports.report_general_ledger",
            "get_report_data",
            [options]
        );
        
        this.state.data = result;
    }

    // --- Getters ---

    get filteredAccounts() {
        if (!this.state.data) return [];
        let accounts = this.state.data.accounts;
        
        if (this.state.search_filter) {
            const search = this.state.search_filter.toLowerCase();
            accounts = accounts.filter(a => 
                a.name.toLowerCase().includes(search) || 
                a.code.toLowerCase().includes(search)
            );
        }
        return accounts;
    }

    getPeriodName() {
        if (this.state.filter_type === 'month') return this.state.options.date_from.toFormat('MMMM yyyy');
        if (this.state.filter_type === 'quarter') return this.state.options.date_from.toFormat('MMM') + ' - ' + this.state.options.date_to.toFormat('MMM yyyy');
        if (this.state.filter_type === 'year') return this.state.options.date_from.toFormat('yyyy');
        return 'Custom';
    }

    // --- Actions ---

    toggleAccount(accountId) {
        if (this.state.expanded_accounts.has(accountId)) {
            this.state.expanded_accounts.delete(accountId);
        } else {
            this.state.expanded_accounts.add(accountId);
        }
        // Trigger reactivity for Set
        this.state.expanded_accounts = new Set(this.state.expanded_accounts);
    }

    isExpanded(accountId) {
        return this.state.expanded_accounts.has(accountId);
    }

    async printPdf() {
        const options = {
            ...this.state.options,
            date_from: serializeDate(this.state.options.date_from),
            date_to: serializeDate(this.state.options.date_to),
        };
        await this.actionService.doAction({
            type: 'ir.actions.report',
            report_type: 'qweb-pdf',
            report_name: 'custom_financial_reports.report_general_ledger',
            report_file: 'custom_financial_reports.report_general_ledger',
            data: options,
            display_name: 'General Ledger',
        });
    }

    async exportXlsx() {
        // Placeholder for XLSX export logic
        console.log("Export XLSX not implemented yet");
    }

    // --- Filter Handlers ---

    async onFilterTypeChanged(type) {
        this.state.filter_type = type;
        const today = DateTime.now();
        
        if (type === 'month') {
            this.state.options.date_from = today.startOf('month');
            this.state.options.date_to = today.endOf('month');
        } else if (type === 'quarter') {
            this.state.options.date_from = today.startOf('quarter');
            this.state.options.date_to = today.endOf('quarter');
        } else if (type === 'year') {
            this.state.options.date_from = today.startOf('year');
            this.state.options.date_to = today.endOf('year');
        }
        
        if (type !== 'custom') {
            await this.getReportData();
        }
    }

    async onCustomDateFromChanged(date) {
        this.state.options.date_from = date;
        this.state.filter_type = 'custom';
        await this.getReportData();
    }

    async onCustomDateToChanged(date) {
        this.state.options.date_to = date;
        this.state.filter_type = 'custom';
        await this.getReportData();
    }

    async onJournalChanged(journalId) {
        const index = this.state.options.journal_ids.indexOf(journalId);
        if (index === -1) {
            this.state.options.journal_ids.push(journalId);
        } else {
            this.state.options.journal_ids.splice(index, 1);
        }
        await this.getReportData();
    }

    async onTargetMoveChanged(isPosted) {
        this.state.options.target_move = isPosted ? 'posted' : 'all';
        await this.getReportData();
    }

    onSearchChanged(ev) {
        this.state.search_filter = ev.target.value;
    }

    // --- Formatters ---

    formatCurrency(amount) {
        if (!this.state.data) return amount;
        return formatCurrency(amount, this.state.data.company_currency_id);
    }

    formatDate(dateStr) {
        if (!dateStr) return "";
        return DateTime.fromISO(dateStr).toFormat("dd/MM/yyyy");
    }
}
GeneralLedgerReport.template = "GeneralLedgerTemp";
GeneralLedgerReport.components = { Dropdown, DropdownItem, DateTimePicker };
registry.category("actions").add("gen_l", GeneralLedgerReport);
