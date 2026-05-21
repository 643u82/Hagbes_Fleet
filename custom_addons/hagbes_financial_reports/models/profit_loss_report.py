from odoo import models, api, fields, _
from dateutil.relativedelta import relativedelta

class ProfitLossReport(models.AbstractModel):
    _name = 'report.custom_financial_reports.report_profit_loss'
    _description = 'Profit and Loss Report'

    def _get_balance(self, date_from, date_to, account_types, target_move, journal_ids):
        """
        Calculate balance for a specific set of account types within a date range.
        Returns a float.
        """
        domain = [
            ('account_id.account_type', 'in', account_types),
            ('date', '>=', date_from),
            ('date', '<=', date_to),
            ('company_id', '=', self.env.company.id),
        ]
        
        if target_move == 'posted':
            domain.append(('move_id.state', '=', 'posted'))
        if journal_ids:
            domain.append(('journal_id', 'in', journal_ids))

        result = self.env['account.move.line'].read_group(domain, ['balance'], [])
        return result[0]['balance'] if result and result[0]['balance'] else 0.0

    def _get_pl_data(self, date_from, date_to, target_move, journal_ids):
        """
        Calculate the specific P&L lines requested.
        """
        # Helper to get balance (inverted for Income so it shows positive)
        def get_bal(types, invert=False):
            bal = self._get_balance(date_from, date_to, types, target_move, journal_ids)
            return -bal if invert else bal

        # 1. Sales Income (Income) - Invert to show positive
        sales_income = get_bal(['income'], invert=True)
        
        # 2. Cost of Sales (Direct Costs) - Normal Debit is positive
        cost_of_sales = get_bal(['expense_direct_cost'])
        
        # 3. Gross Profit
        gross_profit = sales_income - cost_of_sales

        # 4. Other Income - Invert
        other_income = get_bal(['income_other'], invert=True)

        # 5. Selling & Distribution Expenses
        # Standard Odoo doesn't have a specific type for this. 
        # You would typically use Analytic Accounts or Tags. 
        # For now, returning 0.0 as placeholder.
        selling_expenses = 0.0

        # 6. General and Admin Expenses (Standard Expenses + Depreciation)
        ga_expenses = get_bal(['expense', 'expense_depreciation'])

        # 7. Operating Profit
        operating_profit = gross_profit + other_income - selling_expenses - ga_expenses

        # 8. Finance Income
        finance_income = 0.0

        # 9. Finance Costs
        finance_costs = 0.0

        # 10. Profit Before Tax
        profit_before_tax = operating_profit + finance_income - finance_costs

        # 11. Business Income Tax
        income_tax_expense = 0.0

        # 12. Profit for the Year
        profit_for_year = profit_before_tax - income_tax_expense

        return {
            'sales_income': sales_income,
            'cost_of_sales': cost_of_sales,
            'gross_profit': gross_profit,
            'other_income': other_income,
            'selling_expenses': selling_expenses,
            'ga_expenses': ga_expenses,
            'operating_profit': operating_profit,
            'finance_income': finance_income,
            'finance_costs': finance_costs,
            'profit_before_tax': profit_before_tax,
            'income_tax_expense': income_tax_expense,
            'profit_for_year': profit_for_year,
        }

    @api.model
    def get_report_data(self, options):
        """
        Method called by the JS Client Action.
        """
        date_to = fields.Date.from_string(options['date_to'])
        if options.get('date_from'):
            date_from = fields.Date.from_string(options['date_from'])
        else:
            # Default to beginning of the year if not provided
            date_from = date_to.replace(day=1, month=1)

        target_move = options.get('target_move', 'posted')
        journal_ids = options.get('journal_ids', [])

        # Current Period Data
        current_data = self._get_pl_data(date_from, date_to, target_move, journal_ids)

        # Comparison Logic
        prev_data = {}
        has_comparison = False
        
        if options.get('comparison_option') != 'no_comparison':
            date_from_cmp = fields.Date.from_string(options.get('date_from_cmp'))
            date_to_cmp = fields.Date.from_string(options.get('date_to_cmp'))
            if date_from_cmp and date_to_cmp:
                prev_data = self._get_pl_data(date_from_cmp, date_to_cmp, target_move, journal_ids)
                has_comparison = True
        else:
            # Fill zeros if no comparison
            prev_data = {k: 0.0 for k in current_data}

        return {
            'company_name': self.env.company.name,
            'date_from': date_from,
            'date_to': date_to,
            'date_from_cmp': options.get('date_from_cmp'),
            'date_to_cmp': options.get('date_to_cmp'),
            'has_comparison': has_comparison,
            'current': current_data,
            'prev': prev_data,
        }

    @api.model
    def _get_report_values(self, docids, data=None):
        """
        Method called by the PDF Report Engine (QWeb).
        This fixes the AttributeError.
        """
        data = data or {}
        # Ensure dates are strings for the logic
        options = {
            'date_from': data.get('date_from'),
            'date_to': data.get('date_to'),
            'target_move': data.get('target_move', 'posted'),
            'journal_ids': data.get('journal_ids', []),
            'comparison_option': data.get('comparison_option', 'no_comparison'),
            'date_from_cmp': data.get('date_from_cmp'),
            'date_to_cmp': data.get('date_to_cmp'),
        }
        
        report_data = self.get_report_data(options)
        
        return {
            'doc_ids': docids,
            'data': report_data,
            'company': self.env.company,
            'current': report_data['current'],
            'prev': report_data['prev'],
        }


# from odoo import models, api, fields

# class ProfitLossReport(models.AbstractModel):
#     _name = 'report.custom_financial_reports.report_profit_loss'
#     _description = 'Custom Profit and Loss Report'

#     def _get_balance(self, account_types, date_from, date_to, company_id):
#         """
#         Get the balance for a date range.
#         Income is naturally Credit (-), Expense is Debit (+).
#         We return signed values appropriate for calculation (Income +, Expense -) usually,
#         but for the report display we might want positive numbers for both and handle signs in the template.
#         Here: Returns raw balance (Debit - Credit).
#         """
#         domain = [
#             ('account_id.account_type', 'in', account_types),
#             ('date', '>=', date_from),
#             ('date', '<=', date_to),
#             ('move_id.state', '=', 'posted'),
#             ('company_id', '=', company_id),
#         ]
#         read_group_res = self.env['account.move.line'].read_group(
#             domain, ['balance'], []
#         )
#         return read_group_res[0]['balance'] if read_group_res and read_group_res[0]['balance'] else 0.0

#     def _get_pl_data(self, date_from, date_to, company_id):
#         # 1. Sales Income (Income) - Credit is negative, we want positive for display
#         sales_income = -self._get_balance(['income'], date_from, date_to, company_id)
        
#         # 2. Cost of Sales (Direct Cost) - Debit is positive
#         cost_of_sales = self._get_balance(['expense_direct_cost'], date_from, date_to, company_id)
        
#         # 3. Gross Profit
#         gross_profit = sales_income - cost_of_sales

#         # 4. Other Income
#         other_income = -self._get_balance(['income_other'], date_from, date_to, company_id)

#         # 5. Selling & Distribution Expenses
#         # Note: Odoo doesn't strictly separate Selling from G&A by type. 
#         # You might need to use analytic accounts or tags here. 
#         # For now, I will use a placeholder 0.0 or you can define specific accounts.
#         selling_expenses = 0.0 

#         # 6. General and Admin Expenses (Standard Expenses + Depreciation)
#         # We subtract selling_expenses if they were included in the 'expense' type.
#         total_expenses = self._get_balance(['expense', 'expense_depreciation'], date_from, date_to, company_id)
#         ga_expenses = total_expenses - selling_expenses

#         # 7. Operating Profit
#         operating_profit = gross_profit + other_income - selling_expenses - ga_expenses

#         # 8. Finance Income
#         finance_income = 0.0 # Placeholder

#         # 9. Finance Costs
#         finance_costs = 0.0 # Placeholder

#         # 10. Profit Before Tax
#         profit_before_tax = operating_profit + finance_income - finance_costs

#         # 11. Business Income Tax
#         income_tax_expense = 0.0 # Placeholder

#         # 12. Profit for the Year
#         profit_for_year = profit_before_tax - income_tax_expense

#         return {
#             'sales_income': sales_income,
#             'cost_of_sales': cost_of_sales,
#             'gross_profit': gross_profit,
#             'other_income': other_income,
#             'selling_expenses': selling_expenses,
#             'ga_expenses': ga_expenses,
#             'operating_profit': operating_profit,
#             'finance_income': finance_income,
#             'finance_costs': finance_costs,
#             'profit_before_tax': profit_before_tax,
#             'income_tax_expense': income_tax_expense,
#             'profit_for_year': profit_for_year,
#         }

#     @api.model
#     def _get_report_values(self, docids, data=None):
#         company_id = data.get('company_id')
        
#         current_data = self._get_pl_data(data['date_from'], data['date_to'], company_id)
#         prev_data = self._get_pl_data(data['date_from_prev'], data['date_to_prev'], company_id)

#         return {
#             'doc_ids': docids,
#             'data': data,
#             'current': current_data,
#             'prev': prev_data,
#             'company': self.env['res.company'].browse(company_id),
#         }