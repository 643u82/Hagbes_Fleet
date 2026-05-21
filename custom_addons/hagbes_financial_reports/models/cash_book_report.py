from odoo import models, api, fields, _

class CashBookReport(models.AbstractModel):
    _name = 'report.custom_financial_reports.report_cash_book'
    _description = 'Cash Book Report'
    _inherit = 'report.custom_financial_reports.report_general_ledger'

    @api.model
    def get_report_data(self, options):
        # Reuse General Ledger logic but force Cash Journals
        cash_journals = self.env['account.journal'].search([
            ('type', '=', 'cash'),
            ('company_id', '=', self.env.company.id)
        ])
        options['journal_ids'] = cash_journals.ids
        
        accounts = cash_journals.mapped('default_account_id')
        options['account_ids'] = accounts.ids
        
        return super(CashBookReport, self).get_report_data(options)