from odoo import models, api, fields, _
from dateutil.relativedelta import relativedelta
from datetime import date

class CashFlowReport(models.AbstractModel):
    _name = 'report.custom_financial_reports.report_cash_flow'
    _description = 'Cash Flow Report'

    def _get_balance_movement(self, date_from, date_to, domain_extra, target_move, journal_ids):
        """Get movement (Debit - Credit) for the period."""
        domain = [
            ('date', '>=', date_from),
            ('date', '<=', date_to),
            ('company_id', '=', self.env.company.id),
        ] + domain_extra
        if target_move == 'posted':
            domain.append(('move_id.state', '=', 'posted'))
        if journal_ids:
            domain.append(('journal_id', 'in', journal_ids))

        result = self.env['account.move.line'].read_group(domain, ['balance'], [])
        return result[0]['balance'] if result and result[0]['balance'] else 0.0

    def _get_balance_at_date(self, date_at, domain_extra, target_move, journal_ids):
        """Get balance at a specific date."""
        domain = [
            ('date', '<=', date_at),
            ('company_id', '=', self.env.company.id),
        ] + domain_extra
        if target_move == 'posted':
            domain.append(('move_id.state', '=', 'posted'))
        if journal_ids:
            domain.append(('journal_id', 'in', journal_ids))
            
        result = self.env['account.move.line'].read_group(domain, ['balance'], [])
        return result[0]['balance'] if result and result[0]['balance'] else 0.0

    def _get_cash_flow_lines(self, date_from, date_to, target_move, journal_ids):
       
        pl_domain = [('account_id.account_type', 'in', ['income', 'income_other', 'expense', 'expense_depreciation', 'expense_direct_cost'])]
        net_pl_movement = self._get_balance_movement(date_from, date_to, pl_domain, target_move, journal_ids)
        profit_before_tax = -net_pl_movement

       
        dep_domain = [('account_id.account_type', '=', 'expense_depreciation')]
        depreciation = self._get_balance_movement(date_from, date_to, dep_domain, target_move, journal_ids)

    
        
        date_start = date_from - relativedelta(days=1)
        
        def get_wc_change(types):
            dom = [('account_id.account_type', 'in', types)]
            start = self._get_balance_at_date(date_start, dom, target_move, journal_ids)
            end = self._get_balance_at_date(date_to, dom, target_move, journal_ids)
            return start - end

        delta_ar = get_wc_change(['asset_receivable'])
        delta_inventory = get_wc_change(['asset_inventory'])
        delta_ap = get_wc_change(['liability_payable'])
        delta_other_tax = get_wc_change(['liability_current']) # Placeholder for "Other tax payables"

       
        tax_paid = 0.0 

       
        cash_generated_ops = profit_before_tax + depreciation + delta_ar + delta_inventory + delta_ap + delta_other_tax

        # Total Operating
        net_cash_operating = cash_generated_ops + tax_paid

        # Cash at Beginning and End
        cash_domain = [('account_id.account_type', 'in', ['asset_cash', 'asset_bank'])]
        cash_beginning = self._get_balance_at_date(date_from - relativedelta(days=1), cash_domain, target_move, journal_ids)
        cash_closing = self._get_balance_at_date(date_to, cash_domain, target_move, journal_ids)

        return {
            'profit_before_tax': profit_before_tax,
            'depreciation': depreciation,
            'delta_ar': delta_ar,
            'delta_inventory': delta_inventory,
            'delta_ap': delta_ap,
            'delta_other_tax': delta_other_tax,
            'cash_generated_ops': cash_generated_ops,
            'tax_paid': tax_paid,
            'net_cash_operating': net_cash_operating,
            'cash_beginning': cash_beginning,
            'cash_closing': cash_closing,
        }

    @api.model
    def get_report_data(self, options):
        # Handle date_to being string or date
        if isinstance(options['date_to'], str):
            date_to = fields.Date.from_string(options['date_to'])
        else:
            date_to = options['date_to']
            
        if options.get('date_from'):
            if isinstance(options['date_from'], str):
                date_from = fields.Date.from_string(options['date_from'])
            else:
                date_from = options['date_from']
        else:
            date_from = date_to.replace(day=1, month=1)
        
        target_move = options.get('target_move', 'posted')
        journal_ids = options.get('journal_ids', [])

        # Comparison Logic
        date_compare = False
        date_from_cmp = False
        has_comparison = False
        
        comparison_option = options.get('comparison_option', 'no_comparison')
        if comparison_option == 'previous_period':
            date_compare = date_to - relativedelta(months=1)
            date_from_cmp = date_compare.replace(day=1)
        elif comparison_option == 'same_last_year':
            date_compare = date_to - relativedelta(years=1)
            date_from_cmp = date_compare.replace(day=1, month=1)
        elif comparison_option == 'custom' and options.get('comparison_date'):
            if isinstance(options['comparison_date'], str):
                date_compare = fields.Date.from_string(options['comparison_date'])
            else:
                date_compare = options['comparison_date']
            date_from_cmp = date_compare.replace(day=1, month=1)

        if date_compare:
            has_comparison = True

        # Calculate Data
        current = self._get_cash_flow_lines(date_from, date_to, target_move, journal_ids)
        previous = self._get_cash_flow_lines(date_from_cmp, date_compare, target_move, journal_ids) if has_comparison else {}

        def build_line(name, key, note="", bold=False):
            val_curr = current.get(key, 0.0)
            val_prev = previous.get(key, 0.0) if has_comparison else 0.0
            
            percent = False
            if has_comparison:
                if val_prev != 0:
                    percent = ((val_curr - val_prev) / abs(val_prev)) * 100
                elif val_curr != 0:
                    percent = 100.0
            
            return {
                'id': str(hash(name + key)),
                'name': name,
                'note': note,
                'current': val_curr,
                'previous': val_prev,
                'percent': percent,
                'bold': bold,
            }

        # Construct Sections based on User Request
        op_lines = [
            build_line("Profit Before Tax", 'profit_before_tax'),
            build_line("Depreciation of property, plant and equipment", 'depreciation'),
            build_line("Depreciation - Investment property", 'dep_inv_prop'),
            build_line("Amortization - Intangible asset", 'amortization'), 
            build_line("Employee benefit obligation", 'emp_benefit'), 
            build_line("Severance - Finance charge", 'severance'), 
            build_line("Opening Balance Difference PPE", 'open_bal_ppe'), 
            build_line("Prior year adjustment", 'prior_year_adj'), 
            
            {'id': 'wc_header', 'name': 'Changes in working capital:', 'current': 0.0, 'previous': 0.0, 'percent': False, 'bold': True, 'note': ''},
            
            build_line("Payment of employee benefit during the year", 'pay_emp_benefit'), # Placeholder
            build_line("(Increase) decrease in trade and other receivables", 'delta_ar'),
            build_line("(Increase) decrease in inventories", 'delta_inventory'),
            build_line("Increase (decrease) in other tax payables", 'delta_other_tax'),
            build_line("Increase (decrease) in trade and other payables", 'delta_ap'),
            
            # Subtotal
            build_line("Cash generated from / (used in) operating activities", 'cash_generated_ops', bold=True),
            
            build_line("Business income tax paid and withholding tax", 'tax_paid'),
        ]

        # Summary Lines (Major Sections)
        summary_lines = [
            {'name': 'Cash and cash equivalents, beginning of period', 'current': current.get('cash_beginning', 0.0), 'previous': previous.get('cash_beginning', 0.0) if has_comparison else 0.0, 'bold': True, 'is_summary': True},
            {'name': 'Net increase in cash and cash equivalents', 'current': current.get('net_cash_operating', 0.0), 'previous': previous.get('net_cash_operating', 0.0) if has_comparison else 0.0, 'bold': True, 'is_summary': True},
            {'name': 'Cash and cash equivalents, closing balance', 'current': current.get('cash_closing', 0.0), 'previous': previous.get('cash_closing', 0.0) if has_comparison else 0.0, 'bold': True, 'is_summary': True},
        ]

        sections = [
            {
                'name': 'Cash flows from operating activities',
                'type': 'group', # Changed from header to group to match requested style (Bold, no BG)
                'lines': op_lines,
                'total_current': current.get('net_cash_operating', 0.0),
                'total_previous': previous.get('net_cash_operating', 0.0) if has_comparison else 0.0,
                'total_name': 'Net cash generated from / (used in) operating activities'
            }
        ]

        return {
            'company_name': self.env.company.name,
            'company_country': self.env.company.country_id.name,
            'company_vat': self.env.company.vat,
            'date_from': date_from,
            'date_to': date_to,
            'date_compare': date_compare,
            'has_comparison': has_comparison,
            'sections': sections,
            'summary_lines': summary_lines,
        }

    @api.model
    def _get_report_values(self, docids, data=None):
        """
        Required method for QWeb PDF report.
        Resolves AttributeError: 'report...' object has no attribute '_get_report_values'
        """
        data = data or {}
        options = {
            'date_from': data.get('date_from'),
            'date_to': data.get('date_to'),
            'comparison_option': data.get('comparison_option', 'no_comparison'),
            'comparison_date': data.get('comparison_date'),
            'target_move': data.get('target_move', 'posted'),
            'journal_ids': data.get('journal_ids', []),
        }
        
        report_data = self.get_report_data(options)
        
        return {
            'doc_ids': docids,
            'data': report_data,
            'company': self.env.company,
        }