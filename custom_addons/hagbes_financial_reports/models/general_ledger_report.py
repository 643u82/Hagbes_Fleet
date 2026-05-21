from odoo import models, api, fields, _
from odoo.tools import get_lang

class GeneralLedgerReport(models.AbstractModel):
    _name = 'report.custom_financial_reports.report_general_ledger'
    _description = 'General Ledger Report'

    def _get_account_move_lines(self, account_ids, date_from, date_to, target_move, journal_ids):
        domain = [
            ('account_id', 'in', account_ids),
            ('date', '>=', date_from),
            ('date', '<=', date_to),
            ('company_id', '=', self.env.company.id)
        ]
        if target_move == 'posted':
            domain.append(('move_id.state', '=', 'posted'))
        if journal_ids:
            domain.append(('journal_id', 'in', journal_ids))
            
        return self.env['account.move.line'].search(domain, order="date, move_name")

    def _get_initial_balance(self, account_id, date_from, target_move, journal_ids):
        domain = [
            ('account_id', '=', account_id),
            ('date', '<', date_from),
            ('company_id', '=', self.env.company.id)
        ]
        if target_move == 'posted':
            domain.append(('move_id.state', '=', 'posted'))
        if journal_ids:
            domain.append(('journal_id', 'in', journal_ids))

        result = self.env['account.move.line'].read_group(domain, ['balance'], [])
        return result[0]['balance'] if result and result[0]['balance'] else 0.0

    @api.model
    def get_report_data(self, options):
        date_from = fields.Date.from_string(options.get('date_from'))
        date_to = fields.Date.from_string(options.get('date_to'))
        target_move = options.get('target_move', 'posted')
        journal_ids = options.get('journal_ids', [])
        account_ids = options.get('account_ids', [])

        if not account_ids:
            # If no specific accounts selected, get all used accounts in period + those with opening balance
            # For simplicity, getting all active accounts
            # Rely on record rules for company filtering to avoid "Invalid field" errors if company_id is not searchable
            accounts = self.env['account.account'].search([], order='code')
            account_ids = accounts.ids
        else:
            accounts = self.env['account.account'].browse(account_ids)

        report_data = []
        
        for account in accounts:
            initial_balance = self._get_initial_balance(account.id, date_from, target_move, journal_ids)
            move_lines = self._get_account_move_lines([account.id], date_from, date_to, target_move, journal_ids)
            
            if not move_lines and initial_balance == 0:
                continue

            lines = []
            balance = initial_balance
            
            for line in move_lines:
                balance += line.balance
                lines.append({
                    'id': line.id,
                    'date': line.date,
                    'move_name': line.move_name,
                    'journal_code': line.journal_id.code,
                    'partner_name': line.partner_id.name,
                    'ref': line.ref,
                    'name': line.name,
                    'debit': line.debit,
                    'credit': line.credit,
                    'balance': balance,
                })

            debit_total = sum(line.debit for line in move_lines)
            credit_total = sum(line.credit for line in move_lines)

            report_data.append({
                'id': account.id,
                'code': account.code,
                'name': account.name,
                'initial_balance': initial_balance,
                'lines': lines,
                'ending_balance': balance,
                'debit': debit_total,
                'credit': credit_total,
            })

        return {
            'date_from': date_from,
            'date_to': date_to,
            'accounts': report_data,
            'company_name': self.env.company.name,
            'company_currency_id': self.env.company.currency_id.id,
        }

    @api.model
    def _get_report_values(self, docids, data=None):
        data = data or {}
        options = {
            'date_from': data.get('date_from'),
            'date_to': data.get('date_to'),
            'target_move': data.get('target_move', 'posted'),
            'journal_ids': data.get('journal_ids', []),
            'account_ids': data.get('account_ids', []),
        }
        report_data = self.get_report_data(options)
        return {
            'doc_ids': docids,
            'data': report_data,
            'company': self.env.company,
        }