from odoo import models, api, fields, _

class TrialBalanceReport(models.AbstractModel):
    _name = 'report.custom_financial_reports.report_trial_balance'
    _description = 'Trial Balance Report'

    @api.model
    def get_report_data(self, options):
        date_from = fields.Date.from_string(options.get('date_from'))
        date_to = fields.Date.from_string(options.get('date_to'))
        target_move = options.get('target_move', 'posted')
        journal_ids = options.get('journal_ids', [])

        # Base domain
        domain = [('company_id', '=', self.env.company.id)]
        if target_move == 'posted':
            domain.append(('parent_state', '=', 'posted'))
        if journal_ids:
            domain.append(('journal_id', 'in', journal_ids))

        # 1. Get Initial Balances (Before Date From)
        domain_init = domain + [('date', '<', date_from)]
        init_res = self.env['account.move.line'].read_group(
            domain_init, ['account_id', 'balance'], ['account_id']
        )
        initial_balances = {r['account_id'][0]: r['balance'] for r in init_res}

        # 2. Get Period Movements (Date From to Date To)
        domain_period = domain + [('date', '>=', date_from), ('date', '<=', date_to)]
        period_res = self.env['account.move.line'].read_group(
            domain_period, ['account_id', 'debit', 'credit', 'balance'], ['account_id']
        )
        
        period_data = {
            r['account_id'][0]: {
                'debit': r['debit'], 
                'credit': r['credit'], 
                'balance': r['balance']
            } for r in period_res
        }

        # 3. Merge Data
        # Rely on record rules for company filtering to avoid "Invalid field" errors if company_id is not searchable
        accounts = self.env['account.account'].search([], order='code')
        report_lines = []

        for account in accounts:
            init_bal = initial_balances.get(account.id, 0.0)
            p_data = period_data.get(account.id, {'debit': 0.0, 'credit': 0.0, 'balance': 0.0})
            
            end_bal = init_bal + p_data['balance']

            if init_bal == 0 and p_data['debit'] == 0 and p_data['credit'] == 0:
                continue

            report_lines.append({
                'id': account.id,
                'code': account.code,
                'name': account.name,
                'initial_balance': init_bal,
                'debit': p_data['debit'],
                'credit': p_data['credit'],
                'ending_balance': end_bal,
            })

        # Get all journals for the filter
        all_journals = self.env['account.journal'].search_read(
            [('company_id', '=', self.env.company.id)], 
            ['id', 'code', 'name']
        )

        return {
            'date_from': date_from,
            'date_to': date_to,
            'lines': report_lines,
            'company_name': self.env.company.name,
            'journals': all_journals,
        }

    @api.model
    def _get_report_values(self, docids, data=None):
        data = data or {}
        options = {
            'date_from': data.get('date_from'),
            'date_to': data.get('date_to'),
            'target_move': data.get('target_move', 'posted'),
            'journal_ids': data.get('journal_ids', []),
        }
        report_data = self.get_report_data(options)
        return {
            'doc_ids': docids,
            'data': report_data,
            'company': self.env.company,
        }