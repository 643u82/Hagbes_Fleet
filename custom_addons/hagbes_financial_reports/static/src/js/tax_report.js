/** @odoo-module */

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, onWillStart, useState } from "@odoo/owl";

export class TaxReport extends Component {
    setup() {
        this.orm = useService("orm");
        this.actionService = useService("action");
        this.state = useState({
            data: { sales_tax: [], purchase_tax: [] },
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
            "report.custom_financial_reports.report_tax_report",
            "get_report_data",
            [this.state.options]
        );
    }

    async print_pdf() {
        await this.actionService.doAction({
            type: 'ir.actions.report',
            report_type: 'qweb-pdf',
            report_name: 'custom_financial_reports.report_tax_report',
            report_file: 'custom_financial_reports.report_tax_report',
            data: this.state.options,
            display_name: 'Tax Report',
        });
    }
}
TaxReport.template = "TaxReportTemp";
registry.category("actions").add("tax_r", TaxReport);
