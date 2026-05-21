from odoo import models, api, fields, _

class BankBookReport(models.AbstractModel):
    _name = 'report.custom_financial_reports.report_bank_book'
    _description = 'Bank Book Report'
    _inherit = 'report.custom_financial_reports.report_general_ledger'

    @api.model
    def get_report_data(self, options):
        # Reuse General Ledger logic but force Bank Journals
        bank_journals = self.env['account.journal'].search([
            ('type', '=', 'bank'),
            ('company_id', '=', self.env.company.id)
        ])
        options['journal_ids'] = bank_journals.ids
        
        # Also filter accounts to only those used in these journals or default bank accounts
        # Ideally, we just pass the journals, and GL logic handles it.
        # However, GL logic usually iterates accounts. 
        # Let's find accounts linked to these journals.
        accounts = bank_journals.mapped('default_account_id')
        if not accounts:
             # Fallback: search lines in these journals to find relevant accounts
             pass
        
        options['account_ids'] = accounts.ids
        
        return super(BankBookReport, self).get_report_data(options)