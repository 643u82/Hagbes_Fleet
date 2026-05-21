from odoo import models

class BalanceSheetXlsx(models.AbstractModel):
    _name = 'report.custom_financial_reports.report_balance_sheet_xlsx_disabled'
    # _inherit = 'report.report_xlsx.abstract'

    def generate_xlsx_report(self, workbook, data, wizards):
        # Reuse the logic from the PDF report to get values
        report_model = self.env['report.custom_financial_reports.report_balance_sheet_ifrs']
        values = report_model._get_report_values(wizards.ids, data=data)
        
        sheet = workbook.add_worksheet('Balance Sheet')
        
        # Formats
        bold = workbook.add_format({'bold': True})
        header_fmt = workbook.add_format({'bold': True, 'align': 'center', 'bg_color': '#D3D3D3', 'border': 1})
        num_fmt = workbook.add_format({'num_format': '#,##0.00'})
        num_bold_fmt = workbook.add_format({'num_format': '#,##0.00', 'bold': True})
        pct_fmt = workbook.add_format({'num_format': '0.0%'})
        
        # Header
        company = values['company']
        sheet.merge_range('A1:E1', company.name, bold)
        sheet.merge_range('A2:E2', 'Statement of Financial Position', bold)
        sheet.merge_range('A3:E3', f"As at {values['date_to']}", bold)
        
        # Columns
        row = 4
        sheet.write(row, 0, 'Description', header_fmt)
        sheet.write(row, 1, 'Note', header_fmt)
        sheet.write(row, 2, 'Current', header_fmt)
        if values['has_comparison']:
            sheet.write(row, 3, 'Previous', header_fmt)
            sheet.write(row, 4, '% Change', header_fmt)
            
        row += 1
        
        def write_section(title, lines, total_key):
            nonlocal row
            sheet.write(row, 0, title, bold)
            row += 1
            for line in lines:
                sheet.write(row, 0, line['name'])
                sheet.write(row, 1, line['note'])
                sheet.write(row, 2, line['current'], num_fmt)
                if values['has_comparison']:
                    sheet.write(row, 3, line['previous'], num_fmt)
                    if line['percent'] is not False:
                        sheet.write(row, 4, line['percent'] / 100, pct_fmt)
                    else:
                        sheet.write(row, 4, 'n/a')
                row += 1
            
            # Total
            sheet.write(row, 0, f"Total {title}", bold)
            sheet.write(row, 2, values['totals'][total_key], num_bold_fmt)
            if values['has_comparison']:
                prev_key = total_key.replace('current', 'previous')
                sheet.write(row, 3, values['totals'][prev_key], num_bold_fmt)
            row += 2

        # Assets
        sheet.write(row, 0, 'ASSETS', bold)
        row += 1
        write_section('Non-current assets', values['lines']['non_current_assets'], 'nca_current')
        write_section('Current assets', values['lines']['current_assets'], 'ca_current')
        
        sheet.write(row, 0, 'TOTAL ASSETS', bold)
        sheet.write(row, 2, values['totals']['assets_current'], num_bold_fmt)
        row += 2
        
        # Equity & Liabilities
        sheet.write(row, 0, 'EQUITY AND LIABILITIES', bold)
        row += 1
        write_section('Equity', values['lines']['equity'], 'equity_current')
        write_section('Non-current liabilities', values['lines']['non_current_liabilities'], 'ncl_current')
        write_section('Current liabilities', values['lines']['current_liabilities'], 'cl_current')
        
        sheet.write(row, 0, 'TOTAL EQUITY AND LIABILITIES', bold)
        sheet.write(row, 2, values['totals']['el_current'], num_bold_fmt)