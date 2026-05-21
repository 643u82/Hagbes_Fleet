from odoo import models, fields, api

class AccountingDashboard(models.Model):
    _name = 'accounting.dashboard'
    _description = 'Accounting Dashboard'

    name = fields.Char('Dashboard Name', default='Accounting Dashboard')
    total_receivables = fields.Float('Total Receivables', compute='_compute_totals')
    total_payables = fields.Float('Total Payables', compute='_compute_totals')
    cash_balance = fields.Float('Cash Balance', compute='_compute_totals')
    monthly_revenue = fields.Float('Monthly Revenue', compute='_compute_totals')
    monthly_expenses = fields.Float('Monthly Expenses', compute='_compute_totals')

    @api.depends()
    def _compute_totals(self):
        for record in self:
            # Compute receivables
            receivables = self.env['account.move.line'].search([
                ('account_id.account_type', '=', 'asset_receivable'),
                ('reconciled', '=', False)
            ])
            record.total_receivables = sum(receivables.mapped('debit')) - sum(receivables.mapped('credit'))

            # Compute payables
            payables = self.env['account.move.line'].search([
                ('account_id.account_type', '=', 'liability_payable'),
                ('reconciled', '=', False)
            ])
            record.total_payables = sum(payables.mapped('credit')) - sum(payables.mapped('debit'))

            # Compute cash balance
            cash_accounts = self.env['account.move.line'].search([
                ('account_id.account_type', 'in', ['asset_cash', 'liability_credit_card'])
            ])
            record.cash_balance = sum(cash_accounts.mapped('debit')) - sum(cash_accounts.mapped('credit'))

            # Monthly revenue and expenses would require more complex queries
            record.monthly_revenue = 0.0
            record.monthly_expenses = 0.0