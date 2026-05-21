/** @odoo-module */
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, onWillStart, useState, useRef } from "@odoo/owl";
import { Dropdown } from "@web/core/dropdown/dropdown";
import { DropdownItem } from "@web/core/dropdown/dropdown_item";

export class PartnerLedgerReport extends Component {
    static template = "PartnerLedgerTemp";
    static components = { Dropdown, DropdownItem };
    setup() {
        this.orm = useService("orm");
        this.actionService = useService("action");
        this.state = useState({
            data: { partners: [] },
            options: this.props.action.context || {},
        });

        if (!this.state.options.date_from) {
             const today = new Date();
             const firstDay = new Date(today.getFullYear(), today.getMonth(), 1);
             this.state.options.date_from = firstDay.toISOString().split('T')[0];
             this.state.options.date_to = today.toISOString().split('T')[0];
        }

        onWillStart(async () => {
            await this.getReportData();
        });
    }

    async getReportData() {
        this.state.data = await this.orm.call(
            "report.custom_financial_reports.report_partner_ledger",
            "get_report_data",
            [this.state.options]
        );
    }

    async print_pdf() {
        await this.actionService.doAction({
            type: 'ir.actions.report',
            report_type: 'qweb-pdf',
            report_name: 'custom_financial_reports.report_partner_ledger',
            report_file: 'custom_financial_reports.report_partner_ledger',
            data: this.state.options,
            display_name: 'Partner Ledger',
        });
    }
}
PartnerLedgerReport.template = "PartnerLedgerTemp";
registry.category("actions").add("p_l", PartnerLedgerReport);
