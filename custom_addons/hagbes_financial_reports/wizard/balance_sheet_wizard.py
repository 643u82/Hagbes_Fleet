from odoo import models, fields, api

class BalanceSheetWizard(models.TransientModel):
    _name = 'custom.balance.sheet.wizard'
    _description = 'Balance Sheet Wizard'

    date_to = fields.Date(string='As of Date', required=True, default=fields.Date.context_today)
    comparison_option = fields.Selection([
        ('no_comparison', 'No Comparison'),
        ('previous_period', 'Previous Period'),
        ('same_last_year', 'Same Period Last Year'),
        ('custom', 'Specific Date')
    ], string='Comparison', default='no_comparison')
    comparison_date = fields.Date(string='Comparison Date')
    journal_ids = fields.Many2many('account.journal', string='Journals')
    target_move = fields.Selection([('posted', 'Posted Entries'), ('all', 'All Entries')], string='Target Moves', default='posted')
    
    preview_html = fields.Html(string='Report Preview', readonly=True, sanitize=False)

    @api.onchange('date_to', 'comparison_option', 'comparison_date', 'journal_ids', 'target_move')
    def _compute_preview(self):
        for record in self:
            if not record.date_to:
                record.preview_html = False
                continue
                
            data = {
                'date_to': record.date_to,
                'comparison_option': record.comparison_option,
                'comparison_date': record.comparison_date,
                'journal_ids': record.journal_ids.ids,
                'target_move': record.target_move,
            }
            
            # Fetch report data using the AbstractModel
            report_model = self.env['report.custom_financial_reports.report_balance_sheet_ifrs']
            report_values = report_model._get_report_values(docids=None, data=data)
            
            # Render the body template directly
            html = self.env['ir.qweb']._render('custom_financial_reports.report_balance_sheet_ifrs_body', report_values)
            record.preview_html = html

    def action_print_pdf(self):
        self.ensure_one()
        data = {
            'date_to': self.date_to,
            'comparison_option': self.comparison_option,
            'comparison_date': self.comparison_date,
            'journal_ids': self.journal_ids.ids,
            'target_move': self.target_move,
        }
        return self.env.ref('custom_financial_reports.action_report_balance_sheet').report_action(self, data=data)