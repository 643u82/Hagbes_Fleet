# models/lost_sale_report.py
from odoo import models, fields, api, tools

class LostSaleReport(models.Model):
    _name = 'report.lost.sale'
    _description = 'Lost Sale Analysis'
    _auto = False  # SQL VIEW-backed
    _rec_name = 'date'

    # Dimensions (filters/group-by)
    date = fields.Datetime(readonly=True)
    date_date = fields.Date(string="Date", readonly=True)  # for grouping by day
    product_id = fields.Many2one('product.product', readonly=True)
    product_category_id = fields.Many2one('product.category', readonly=True)
    customer_id = fields.Many2one('res.partner', readonly=True)
    branch_id = fields.Many2one('account.analytic.account', readonly=True)
    warehouse_id = fields.Many2one('stock.warehouse', readonly=True)
    company_id = fields.Many2one('res.company', readonly=True)
    reason = fields.Selection([
        ('out_of_stock', 'Out of Stock'),
        ('no_replenishment', 'No Replenishment Rule'),
        ('partial_stock', 'Partial Stock'),
        ('other', 'Other')
    ], readonly=True)

    # Measures
    quantity_requested = fields.Float(readonly=True)
    quantity_lost = fields.Float(readonly=True)
    quantity_available = fields.Float(readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute(f"""
            CREATE OR REPLACE VIEW {self._table} AS (
                SELECT
                    ls.id,
                    ls.date,
                    ls.date::date AS date_date,
                    ls.product_id,
                    ls.product_category_id,
                    ls.customer_id,
                    ls.branch_id,
                    ls.warehouse_id,
                    ls.company_id,
                    ls.reason,
                    ls.quantity_requested,
                    ls.quantity_lost,
                    ls.quantity_available
                FROM lost_sale ls
            )
        """)