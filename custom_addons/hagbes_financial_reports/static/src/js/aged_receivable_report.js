/** @odoo-module */

/** @odoo-module */
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, onWillStart, useState, useRef } from "@odoo/owl";
import { Dropdown } from "@web/core/dropdown/dropdown";
import { DropdownItem } from "@web/core/dropdown/dropdown_item";

export class AgedReceivableReport extends Component {
    static template = "AgedReceivableTemp";
    static components = { Dropdown, DropdownItem };
    setup() {
        this.orm = useService("orm");
        this.actionService = useService("action");
        this.state = useState({
            data: { lines: [] },
            options: this.props.action.context || {},
        });

        if (!this.state.options.date_to) {
            const today = new Date();
            this.state.options.date_to = today.toISOString().split('T')[0];
        }

        onWillStart(async () => {
            await this.getReportData();
        });
    }

    async getReportData() {
        this.state.data = await this.orm.call(
            "report.custom_financial_reports.report_aged_receivable",
            "get_report_data",
            [this.state.options]
        );
    }

    async print_pdf() {
        await this.actionService.doAction({
            type: 'ir.actions.report',
            report_type: 'qweb-pdf',
            report_name: 'custom_financial_reports.report_aged_receivable',
            report_file: 'custom_financial_reports.report_aged_receivable',
            data: this.state.options,
            display_name: 'Aged Receivable',
        });
    }
}
AgedReceivableReport.template = "AgedReceivableTemp";
registry.category("actions").add("a_r", AgedReceivableReport);
