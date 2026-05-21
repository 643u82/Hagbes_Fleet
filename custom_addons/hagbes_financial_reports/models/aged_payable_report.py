from odoo import models, api, fields, _
from odoo.tools.misc import format_date
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

class AgedPayableReport(models.AbstractModel):
    _name = 'report.custom_financial_reports.report_aged_payable'
    _description = 'Aged Payable Report'

    @api.model
    def _get_filter_values(self, options):
        date_to = options.get('date_to')
        if not date_to:
            date_to = fields.Date.today()
        else:
            date_to = fields.Date.from_string(date_to)
        
        target_move = options.get('target_move', 'posted')
        partner_ids = options.get('partner_ids', [])
        return date_to, target_move, partner_ids

    @api.model
    def _get_sql_query(self, date_to, target_move, partner_ids, company_id):
        state_cond = "AND am.state = 'posted'" if target_move == 'posted' else ""
        partner_cond = ""
        if partner_ids:
            partner_cond = "AND aml.partner_id IN %s"
        
        query = """
            SELECT
                aml.id as id,
                aml.partner_id as partner_id,
                p.name as partner_name,
                aml.date_maturity as date_maturity,
                aml.date as date,
                aml.name as name,
                am.name as move_name,
                am.id as move_id,
                aml.account_id as account_id,
                aml.amount_currency as amount_currency,
                aml.currency_id as currency_id,
                aml.balance as balance,
                aml.credit as credit,
                aml.debit as debit
            FROM account_move_line aml
            JOIN account_move am ON aml.move_id = am.id
            JOIN account_account acc ON aml.account_id = acc.id
            LEFT JOIN res_partner p ON aml.partner_id = p.id
            WHERE aml.company_id = %s
            AND acc.account_type = 'liability_payable'
            AND aml.date <= %s
            AND aml.reconciled = FALSE
            {state_cond}
            {partner_cond}
            ORDER BY aml.partner_id, aml.date_maturity
        """.format(state_cond=state_cond, partner_cond=partner_cond)
        
        return query, partner_cond

    @api.model
    def get_report_data(self, options):
        date_to, target_move, partner_ids = self._get_filter_values(options)
        company_id = self.env.company.id
        
        query, partner_cond = self._get_sql_query(date_to, target_move, partner_ids, company_id)
        
        params = [company_id, date_to]
        if partner_cond:
            params.append(tuple(partner_ids))
            
        self.env.cr.execute(query, tuple(params))
        results = self.env.cr.dictfetchall()
        
        partners = {}
        move_lines = []
        
        grand_total = {
            'diff0_sum': 0.0,
            'diff1_sum': 0.0,
            'diff2_sum': 0.0,
            'diff3_sum': 0.0,
            'diff4_sum': 0.0,
            'diff5_sum': 0.0,
            'total_credit': 0.0,
        }

        for res in results:
            partner_name = res['partner_name'] or 'Unknown Partner'
            if partner_name not in partners:
                partners[partner_name] = []
                if partner_name not in move_lines: # Keep order
                    move_lines.append(partner_name)

            # Calculate aging
            date_compare_mode = options.get('date_compare_mode', 'due_date')
            if date_compare_mode == 'invoice_date':
                due_date = res['date']
            else:
                due_date = res['date_maturity'] or res['date']
                
            days_overdue = (date_to - due_date).days
            
            # Initialize diffs
            res['diff0'] = 0.0 # Not due
            res['diff1'] = 0.0 # 0-30
            res['diff2'] = 0.0 # 31-60
            res['diff3'] = 0.0 # 61-90
            res['diff4'] = 0.0 # 91-120
            res['diff5'] = 0.0 # Older
            
             # Payable is Credit, we want positive numbers for the report usually
            amount = res['credit'] - res['debit'] # Balance is usually negative for payable? Let's check. 
            # If account type is liability_payable:
            # Vendor Bill: Credit increases (positive), Invoice: Debit increases
            # We want the amount to pay.
            # Usually verify by: if balance < 0 implies payable. 
            # Let's align with dynamic report logic:
            # dynamic report uses 'credit' field mostly.
            # Let's stick to balance logic but invert it for display if needed.
            # Actually, let's look at dynamic_accounts_report again. 
            # It uses: val['credit']. 
            # But what if there are debits (e.g. payments not reconciled)?
            # Standard Odoo aging uses amount_residual. 
            # For simplicity matching the reference:
            
            amount = res['balance'] * -1 # Make payable positive
            
            if days_overdue <= 0:
                res['diff0'] = amount
            elif days_overdue <= 30:
                res['diff1'] = amount
            elif days_overdue <= 60:
                res['diff2'] = amount
            elif days_overdue <= 90:
                res['diff3'] = amount
            elif days_overdue <= 120:
                res['diff4'] = amount
            else:
                res['diff5'] = amount

            res['amount'] = amount # For total
            
            # Formatting
            res['date'] = format_date(self.env, res['date'])
            res['date_maturity'] = format_date(self.env, res['date_maturity'])

            # Currency handling (simplified for now, using company currency for cols)
            currency = self.env['res.currency'].browse(res['currency_id']) if res['currency_id'] else self.env.company.currency_id
            res['currency_id'] = [currency.id, currency.name]
            
            account = self.env['account.account'].browse(res['account_id'])
            res['account_id'] = [account.id, account.code + ' ' + account.name]

            partners[partner_name].append(res)

        # Calculate totals per partner and grand total
        partner_totals = {}
        
        for partner, lines in partners.items():
            p_total = {
                'diff0_sum': sum(x['diff0'] for x in lines),
                'diff1_sum': sum(x['diff1'] for x in lines),
                'diff2_sum': sum(x['diff2'] for x in lines),
                'diff3_sum': sum(x['diff3'] for x in lines),
                'diff4_sum': sum(x['diff4'] for x in lines),
                'diff5_sum': sum(x['diff5'] for x in lines),
                'credit_sum': sum(x['amount'] for x in lines),
                'partner_id': lines[0]['partner_id'] if lines else False
            }
            partner_totals[partner] = p_total
            
            # Add to grand total
            grand_total['diff0_sum'] += p_total['diff0_sum']
            grand_total['diff1_sum'] += p_total['diff1_sum']
            grand_total['diff2_sum'] += p_total['diff2_sum']
            grand_total['diff3_sum'] += p_total['diff3_sum']
            grand_total['diff4_sum'] += p_total['diff4_sum']
            grand_total['diff5_sum'] += p_total['diff5_sum']
            grand_total['total_credit'] += p_total['credit_sum']

        # Format grand totals
        def fmt(val):
            return '{:,.2f}'.format(val)

        return {
            'date_at': format_date(self.env, date_to),
            'move_line': move_lines, # List of partner names in order
            'data': partners,        # Dict of {partner: [lines]}
            'total': partner_totals, # Dict of {partner: {totals}}
            'period_length': 30,
            
            'diff0_sum_display': fmt(grand_total['diff0_sum']),
            'diff1_sum_display': fmt(grand_total['diff1_sum']),
            'diff2_sum_display': fmt(grand_total['diff2_sum']),
            'diff3_sum_display': fmt(grand_total['diff3_sum']),
            'diff4_sum_display': fmt(grand_total['diff4_sum']),
            'diff5_sum_display': fmt(grand_total['diff5_sum']),
            'total_debit_display': fmt(grand_total['total_credit']), # Using 'debit' key for total col in template, but it is credit/payable
            'company_currency_symbol': self.env.company.currency_id.symbol,
        }
