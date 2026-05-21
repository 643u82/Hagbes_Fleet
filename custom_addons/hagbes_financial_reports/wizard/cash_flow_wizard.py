from odoo import models, fields

class CashFlowWizard(models.TransientModel):
    _name = 'custom.cash.flow.wizard'
    _description = 'Custom Cash Flow Wizard'

    date_from = fields.Date(string='Start Date', required=True, default=lambda self: fields.Date.context_today(self).replace(month=1, day=1))
    date_to = fields.Date(string='End Date', required=True, default=fields.Date.context_today)

    def action_print_report(self):
        self.ensure_one()
        data = {
            'date_from': self.date_from,
            'date_to': self.date_to,
            'company_id': self.env.company.id,
        }
        return self.env.ref('custom_financial_reports.action_report_cash_flow').report_action(self, data=data)