from odoo import models, api, fields, _

class AgedReceivableReport(models.AbstractModel):
    _name = 'report.custom_financial_reports.report_aged_receivable'
    _description = 'Aged Receivable Report'

    def _get_aging_data(self, date_at, target_move):
        domain = [
            ('account_id.account_type', '=', 'asset_receivable'),
            ('parent_state', '=', 'posted' if target_move == 'posted' else 'draft'),
            ('date', '<=', date_at),
            ('company_id', '=', self.env.company.id),
            ('reconciled', '=', False)
        ]
        
        move_lines = self.env['account.move.line'].search(domain)
        partners = {}

        for line in move_lines:
            if line.amount_residual == 0:
                continue
                
            pid = line.partner_id.id or 0
            pname = line.partner_id.name or 'Unknown'
            
            if pid not in partners:
                partners[pid] = {'name': pname, '0-30': 0, '30-60': 0, '60-90': 0, '90+': 0, 'total': 0}
            
            due_date = line.date_maturity or line.date
            days_overdue = (date_at - due_date).days
            
            # Receivable is Debit, so positive.
            amount = line.amount_residual

            if days_overdue <= 0:
                partners[pid]['0-30'] += amount
            elif days_overdue <= 30:
                partners[pid]['0-30'] += amount
            elif days_overdue <= 60:
                partners[pid]['30-60'] += amount
            elif days_overdue <= 90:
                partners[pid]['60-90'] += amount
            else:
                partners[pid]['90+'] += amount
            
            partners[pid]['total'] += amount

        return partners

    @api.model
    def get_report_data(self, options):
        date_at = fields.Date.from_string(options.get('date_to')) or fields.Date.today()
        target_move = options.get('target_move', 'posted')
        
        partners_data = self._get_aging_data(date_at, target_move)
        
        report_lines = []
        for pid, data in partners_data.items():
            if data['total'] != 0:
                report_lines.append(data)
                
        return {
            'date_at': date_at,
            'lines': report_lines,
            'company_name': self.env.company.name,
        }

    @api.model
    def _get_report_values(self, docids, data=None):
        data = data or {}
        options = {
            'date_to': data.get('date_to'),
            'target_move': data.get('target_move', 'posted'),
        }
        report_data = self.get_report_data(options)
        return {
            'doc_ids': docids,
            'data': report_data,
            'company': self.env.company,
        }