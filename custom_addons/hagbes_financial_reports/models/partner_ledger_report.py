from odoo import models, api, fields, _

class PartnerLedgerReport(models.AbstractModel):
    _name = 'report.custom_financial_reports.report_partner_ledger'
    _description = 'Partner Ledger Report'

    @api.model
    def get_report_data(self, options):
        date_from = fields.Date.from_string(options.get('date_from'))
        date_to = fields.Date.from_string(options.get('date_to'))
        target_move = options.get('target_move', 'posted')
        partner_ids = options.get('partner_ids', [])
        account_type = options.get('account_type', ['asset_receivable', 'liability_payable'])

        domain = [
            ('date', '<=', date_to),
            ('account_id.account_type', 'in', account_type),
            ('company_id', '=', self.env.company.id)
        ]
        if target_move == 'posted':
            domain.append(('move_id.state', '=', 'posted'))
        if partner_ids:
            domain.append(('partner_id', 'in', partner_ids))
        else:
            domain.append(('partner_id', '!=', False))

        # Fetch all lines
        move_lines = self.env['account.move.line'].search(domain, order='partner_id, date, move_name')

        partners_data = {}
        
        for line in move_lines:
            pid = line.partner_id.id
            if pid not in partners_data:
                partners_data[pid] = {
                    'id': pid,
                    'name': line.partner_id.name,
                    'initial_balance': 0.0,
                    'lines': [],
                    'ending_balance': 0.0
                }
            
            # Check if line is initial balance (before date_from)
            if line.date < date_from:
                partners_data[pid]['initial_balance'] += line.balance
                partners_data[pid]['ending_balance'] += line.balance
            else:
                # Period line
                partners_data[pid]['lines'].append({
                    'id': line.id,
                    'date': line.date,
                    'move_name': line.move_name,
                    'account_code': line.account_id.code,
                    'ref': line.ref,
                    'name': line.name,
                    'debit': line.debit,
                    'credit': line.credit,
                    'balance': line.balance,
                })
                partners_data[pid]['ending_balance'] += line.balance

        # Post-process to calculate running balance for period lines
        report_lines = []
        for pid, p_data in partners_data.items():
            if not p_data['lines'] and p_data['initial_balance'] == 0:
                continue
                
            running_bal = p_data['initial_balance']
            for line in p_data['lines']:
                running_bal += line['balance']
                line['running_balance'] = running_bal
            
            report_lines.append(p_data)

        return {
            'date_from': date_from,
            'date_to': date_to,
            'partners': report_lines,
            'company_name': self.env.company.name,
        }

    @api.model
    def _get_report_values(self, docids, data=None):
        data = data or {}
        options = {
            'date_from': data.get('date_from'),
            'date_to': data.get('date_to'),
            'target_move': data.get('target_move', 'posted'),
            'partner_ids': data.get('partner_ids', []),
            'account_type': data.get('account_type', ['asset_receivable', 'liability_payable']),
        }
        report_data = self.get_report_data(options)
        return {
            'doc_ids': docids,
            'data': report_data,
            'company': self.env.company,
        }