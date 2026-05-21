from odoo import models, fields
from dateutil.relativedelta import relativedelta

class ProfitLossWizard(models.TransientModel):
    _name = 'custom.profit.loss.wizard'
    _description = 'Custom Profit and Loss Wizard'

    date_from = fields.Date(string='Start Date', required=True, default=lambda self: fields.Date.context_today(self).replace(month=1, day=1))
    date_to = fields.Date(string='End Date', required=True, default=fields.Date.context_today)

    def action_print_report(self):
        self.ensure_one()
        
        # Calculate previous year dates for comparison
        date_from_prev = self.date_from - relativedelta(years=1)
        date_to_prev = self.date_to - relativedelta(years=1)

        data = {
            'date_from': self.date_from,
            'date_to': self.date_to,
            'date_from_prev': date_from_prev,
            'date_to_prev': date_to_prev,
            'company_id': self.env.company.id,
        }
        return self.env.ref('custom_financial_reports.action_report_profit_loss').report_action(self, data=data)