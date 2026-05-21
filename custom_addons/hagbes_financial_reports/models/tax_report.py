from odoo import models, api, fields, _

class TaxReport(models.AbstractModel):
    _name = 'report.custom_financial_reports.report_tax_report'
    _description = 'Tax Report'

    @api.model
    def get_report_data(self, options):
        date_from = fields.Date.from_string(options.get('date_from'))
        date_to = fields.Date.from_string(options.get('date_to'))
        target_move = options.get('target_move', 'posted')

        domain = [
            ('date', '>=', date_from),
            ('date', '<=', date_to),
            ('tax_line_id', '!=', False),
            ('company_id', '=', self.env.company.id)
        ]
        if target_move == 'posted':
            domain.append(('move_id.state', '=', 'posted'))

        # Group by Tax
        res = self.env['account.move.line'].read_group(
            domain, 
            ['tax_line_id', 'balance', 'tax_base_amount'], 
            ['tax_line_id']
        )

        lines = []
        for r in res:
            tax = self.env['account.tax'].browse(r['tax_line_id'][0])
            lines.append({
                'id': tax.id,
                'name': tax.name,
                'type': tax.type_tax_use, # Sale/Purchase
                'base': r['tax_base_amount'],
                'amount': r['balance'], # Usually negative for sales tax (Credit)
            })

        # Organize by Sale/Purchase
        sales_tax = [l for l in lines if l['type'] == 'sale']
        purchase_tax = [l for l in lines if l['type'] == 'purchase']

        return {
            'date_from': date_from,
            'date_to': date_to,
            'sales_tax': sales_tax,
            'purchase_tax': purchase_tax,
            'company_name': self.env.company.name,
        }

    @api.model
    def _get_report_values(self, docids, data=None):
        data = data or {}
        options = {
            'date_from': data.get('date_from'),
            'date_to': data.get('date_to'),
            'target_move': data.get('target_move', 'posted'),
        }
        report_data = self.get_report_data(options)
        return {
            'doc_ids': docids,
            'data': report_data,
            'company': self.env.company,
        }