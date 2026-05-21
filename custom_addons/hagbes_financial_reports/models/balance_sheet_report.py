from odoo import models, api, _
from datetime import date, datetime
from dateutil.relativedelta import relativedelta


class BalanceSheetIFRS(models.AbstractModel):
    _name = 'report.custom_financial_reports.report_balance_sheet_ifrs'
    _description = 'IFRS Statement of Financial Position'

    def _get_domain(self, types, date_to, journal_ids=None, target_move='posted'):
        domain = [
            ('account_id.account_type', 'in', types),
            ('date', '<=', date_to),
            ('company_id', '=', self.env.company.id),
        ]
        if target_move == 'posted':
            domain.append(('move_id.state', '=', 'posted'))
        if journal_ids:
            domain.append(('journal_id', 'in', journal_ids))
        return domain

    def _balance(self, types, date_to, journal_ids=None, target_move='posted'):
        domain = [
            ('account_id.account_type', 'in', types),
            ('date', '<=', date_to),
            ('company_id', '=', self.env.company.id),
        ]
        
        if target_move == 'posted':
            domain.append(('move_id.state', '=', 'posted'))
            
        if journal_ids:
            domain.append(('journal_id', 'in', journal_ids))
            
        # Use read_group for efficient summation
        res = self.env['account.move.line'].read_group(domain, ['balance'], [])
        return res[0]['balance'] if res and res[0]['balance'] else 0.0

    @api.model
    def _get_report_values(self, docids, data=None):
        """
        Wizard-based report → ALWAYS use `data`, NEVER docids
        """
        data = data or {}

        # 1. Parse Filters
        date_to_str = data.get('date_to')
        if isinstance(date_to_str, (date, datetime)):
            date_to = date_to_str
        else:
            date_to = date.fromisoformat(str(date_to_str)) if date_to_str else date.today()

        comparison_option = data.get('comparison_option', 'no_comparison')
        comparison_date_str = data.get('comparison_date')
        
        journal_ids = data.get('journal_ids')
        target_move = data.get('target_move', 'posted')

        # 2. Determine Comparison Date
        date_compare = False
        if comparison_option == 'previous_period':
            # Previous Period usually implies Month-over-Month in operational reporting
            date_compare = date_to - relativedelta(months=1)
        elif comparison_option == 'same_last_year':
            date_compare = date_to - relativedelta(years=1)
        elif comparison_option == 'custom' and comparison_date_str:
            if isinstance(comparison_date_str, (date, datetime)):
                date_compare = comparison_date_str
            else:
                date_compare = date.fromisoformat(str(comparison_date_str))
            
        has_comparison = bool(date_compare)

        # 3. Build Line Data Helper
        def build_line(name, note, types):
            current = self._balance(types, date_to, journal_ids, target_move)
            previous = self._balance(types, date_compare, journal_ids, target_move) if has_comparison else 0.0
            
            diff = current - previous
            percent = False
            if has_comparison:
                if previous != 0:
                    percent = (diff / previous) * 100
                elif current != 0:
                    percent = 100.0 if current > 0 else -100.0
            
            return {
                'name': name,
                'note': note,
                'current': current,
                'previous': previous,
                'percent': percent,
            }

        # ASSETS
        nca = [
            ("Property, plant and equipment", "5", ['asset_fixed']),
            ("Intangible asset", "5", ['asset_non_current']),
            ("Right of use of Asset", "3.19", ['asset_fixed']), # Ensure account type matches
            ("Investment property", "6", ['asset_fixed']),
            ("Investment", "7", ['asset_non_current']),
        ]

        ca = [
            ("Inventories and Goods in Transit", "8", ['asset_inventory']),
            ("Trade and other receivables", "9", ['asset_receivable']),
            ("Related Parties - Receivable", "10.1", ['asset_receivable']),
            ("Cash and cash equivalents", "11", ['asset_cash', 'asset_bank']),
        ]

        nca_lines = [build_line(n, note, t) for n, note, t in nca]
        ca_lines = [build_line(n, note, t) for n, note, t in ca]

        # EQUITY
        equity = [
            ("Paid Up Capital", "12", ['equity']),
            ("Legal Reserve", "", ['equity']),
            ("Retained earnings", "", ['equity_unaffected']),
        ]
        equity_lines = [build_line(n, note, t) for n, note, t in equity]

        # LIABILITIES
        ncl = [
            ("Loans and borrowings", "13", ['liability_non_current']),
            ("Employee Benefits – severance", "15", ['liability_non_current']),
            ("Deferred Tax Liability", "24", ['liability_non_current']),
        ]
        
        cl = [
            ("Loans and borrowings", "13", ['liability_current']),
            ("Bank overdraft", "14", ['liability_credit_card']),
            ("Employee Benefits – annual leave", "15", ['liability_current']),
            ("Profit Tax Payable", "24.4", ['liability_current']),
            ("Trade and other payables", "", ['liability_payable']),
            ("Other Tax Payable", "17", ['liability_current']),
            ("Related Parties – Payable", "10.2", ['liability_payable']),
            ("Shareholders' account", "25", ['equity']),
        ]
        
        ncl_lines = [build_line(n, note, t) for n, note, t in ncl]
        cl_lines = [build_line(n, note, t) for n, note, t in cl]

        # 4. Calculate Totals
        def sum_key(lines, key):
            return sum(l[key] for l in lines)

        totals = {}
        for key in ['current', 'previous']:
            totals[f'nca_{key}'] = sum_key(nca_lines, key)
            totals[f'ca_{key}'] = sum_key(ca_lines, key)
            totals[f'assets_{key}'] = totals[f'nca_{key}'] + totals[f'ca_{key}']
            
            totals[f'equity_{key}'] = sum_key(equity_lines, key)
            
            totals[f'ncl_{key}'] = sum_key(ncl_lines, key)
            totals[f'cl_{key}'] = sum_key(cl_lines, key)
            totals[f'liabilities_{key}'] = totals[f'ncl_{key}'] + totals[f'cl_{key}']
            
            totals[f'el_{key}'] = totals[f'equity_{key}'] + totals[f'liabilities_{key}']

        return {
            'company': self.env.company,
            'date_to': date_to,
            'date_compare': date_compare,
            'has_comparison': has_comparison,
            'lines': {
                'non_current_assets': nca_lines,
                'current_assets': ca_lines,
                'equity': equity_lines,
                'non_current_liabilities': ncl_lines,
                'current_liabilities': cl_lines,
            },
            'totals': totals,
        }

    @api.model
    def get_report_data(self, options):
        """
        API for OWL Client Action.
        Returns JSON-serializable data structure with drill-down domains.
        """
        # 1. Parse Options
        date_to_str = options.get('date_to')
        date_to = date.fromisoformat(date_to_str) if date_to_str else date.today()
        
        comparison_option = options.get('comparison_option', 'no_comparison')
        comparison_date_str = options.get('comparison_date')
        journal_ids = options.get('journal_ids', [])
        target_move = options.get('target_move', 'posted')

        # 2. Determine Comparison Date
        date_compare = False
        if comparison_option == 'previous_period':
            date_compare = date_to - relativedelta(months=1)
        elif comparison_option == 'same_last_year':
            date_compare = date_to - relativedelta(years=1)
        elif comparison_option == 'custom' and comparison_date_str:
            date_compare = date.fromisoformat(comparison_date_str)
        
        has_comparison = bool(date_compare)

        # 3. Helper to build lines with domains
        def build_line_api(name, note, types, indent=1):
            current = self._balance(types, date_to, journal_ids, target_move)
            previous = self._balance(types, date_compare, journal_ids, target_move) if has_comparison else 0.0
            
            diff = current - previous
            percent = False
            if has_comparison:
                if previous != 0:
                    percent = (diff / previous) * 100
                elif current != 0:
                    percent = 100.0 if current > 0 else -100.0
            
            # Construct domain for drill-down (General Ledger)
            domain = self._get_domain(types, date_to, journal_ids, target_move)

            return {
                'id': str(hash(name)), # Unique ID for key
                'name': name,
                'note': note,
                'current': current,
                'previous': previous,
                'percent': percent,
                'indent': indent,
                'domain': domain,
                'action_model': 'account.move.line',
            }

        # Reuse the definitions from _get_report_values but return flat lists for easier JS rendering
        # or structured sections. Let's return structured sections.
        
        # We call the internal logic to get the raw data structure
        # For simplicity in this example, we re-invoke the logic or refactor. 
        # To keep it DRY, we will call _get_report_values and augment it, 
        # but _get_report_values returns formatted strings in some places or objects.
        # Let's just use the logic directly here for the API to ensure clean JSON.
        
        # (Logic duplicated from _get_report_values for clarity in this snippet, 
        # in production you would refactor the definitions into a shared property)
        
        nca = [("Property, plant and equipment", "5", ['asset_fixed']), ("Intangible asset", "5", ['asset_non_current']), ("Right of use of Asset", "3.19", ['asset_fixed']), ("Investment property", "6", ['asset_fixed']), ("Investment", "7", ['asset_non_current'])]
        ca = [("Inventories and Goods in Transit", "8", ['asset_inventory']), ("Trade and other receivables", "9", ['asset_receivable']), ("Related Parties - Receivable", "10.1", ['asset_receivable']), ("Cash and cash equivalents", "11", ['asset_cash', 'asset_bank'])]
        equity = [("Paid Up Capital", "12", ['equity']), ("Legal Reserve", "", ['equity']), ("Retained earnings", "", ['equity_unaffected'])]
        ncl = [("Loans and borrowings", "13", ['liability_non_current']), ("Employee Benefits – severance", "15", ['liability_non_current']), ("Deferred Tax Liability", "24", ['liability_non_current'])]
        cl = [("Loans and borrowings", "13", ['liability_current']), ("Bank overdraft", "14", ['liability_credit_card']), ("Employee Benefits – annual leave", "15", ['liability_current']), ("Profit Tax Payable", "24.4", ['liability_current']), ("Trade and other payables", "", ['liability_payable']), ("Other Tax Payable", "17", ['liability_current']), ("Related Parties – Payable", "10.2", ['liability_payable']), ("Shareholders' account", "25", ['equity'])]

        data = {
            'company_name': self.env.company.name,
            'currency': self.env.company.currency_id.name,
            'currency_symbol': self.env.company.currency_id.symbol,
            'date_to': date_to,
            'date_compare': date_compare,
            'has_comparison': has_comparison,
            'sections': [
                {'name': 'ASSETS', 'type': 'header'},
                {'name': 'Non-current assets', 'type': 'subheader', 'lines': [build_line_api(n, note, t) for n, note, t in nca]},
                {'name': 'Current assets', 'type': 'subheader', 'lines': [build_line_api(n, note, t) for n, note, t in ca]},
                {'name': 'EQUITY AND LIABILITIES', 'type': 'header'},
                {'name': 'Equity', 'type': 'subheader', 'lines': [build_line_api(n, note, t) for n, note, t in equity]},
                {'name': 'Non-current liabilities', 'type': 'subheader', 'lines': [build_line_api(n, note, t) for n, note, t in ncl]},
                {'name': 'Current liabilities', 'type': 'subheader', 'lines': [build_line_api(n, note, t) for n, note, t in cl]},
            ]
        }
        
        # Calculate totals for sections
        for section in data['sections']:
            if section.get('lines'):
                section['total_current'] = sum(l['current'] for l in section['lines'])
                section['total_previous'] = sum(l['previous'] for l in section['lines'])
        
        # Calculate Grand Totals
        assets_total = sum(s['total_current'] for s in data['sections'] if s['name'] in ['Non-current assets', 'Current assets'])
        assets_prev = sum(s['total_previous'] for s in data['sections'] if s['name'] in ['Non-current assets', 'Current assets'])
        
        el_total = sum(s['total_current'] for s in data['sections'] if s['name'] in ['Equity', 'Non-current liabilities', 'Current liabilities'])
        el_prev = sum(s['total_previous'] for s in data['sections'] if s['name'] in ['Equity', 'Non-current liabilities', 'Current liabilities'])

        data['totals'] = {
            'assets': {'current': assets_total, 'previous': assets_prev},
            'equity_liabilities': {'current': el_total, 'previous': el_prev}
        }

        return data