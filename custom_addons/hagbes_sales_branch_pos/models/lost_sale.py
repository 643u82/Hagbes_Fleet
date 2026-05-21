# models/lost_sale.py
from odoo import models, fields,api

class LostSale(models.Model):
    _name = 'lost.sale'
    _description = 'Lost Sale'
    _inherit = ['mail.thread', 'mail.activity.mixin'] 

    product_id = fields.Many2one('product.product', required=True)
    customer_id = fields.Many2one('res.partner', required=True)
    sale_order_id = fields.Many2one('sale.order')
    quantity_requested = fields.Float()
    quantity_available = fields.Float()
    quantity_lost = fields.Float( )
    branch_id = fields.Many2one(
            'account.analytic.account',
            string="Branch",
            readonly=True
        )
    product_category_id = fields.Many2one(
        'product.category',
        string="Product Category",
        related='product_id.categ_id',
        store=True,
        readonly=True
        )
    warehouse_id = fields.Many2one('stock.warehouse', string="Warehouse", readonly=True)
    company_id = fields.Many2one('res.company', string="Company", readonly=True)
    reason = fields.Selection([
        ('out_of_stock', 'Out of Stock'),
        ('no_replenishment', 'No Replenishment Rule'),
        ('partial_stock', 'Partial Stock'),
        ('other', 'Other')
    ], default='out_of_stock')
    branch_stock_info = fields.Text(
        string="Branch Availability Info",
        compute="_compute_branch_stock_info"
    )

    date = fields.Datetime(default=fields.Datetime.now)

    @api.depends('product_id')
    def _compute_branch_stock_info(self):
        StockQuant = self.env['stock.quant']
        for record in self:
            if not record.product_id:
                record.branch_stock_info = ""
                continue

            originating_warehouse = record.sale_order_id.warehouse_id if record.sale_order_id else None
            lines = []

            warehouses = self.env['stock.warehouse'].search([])

            for warehouse in warehouses:
                if warehouse == originating_warehouse:
                    continue

                quants = StockQuant.search([
                    ('product_id', '=', record.product_id.id),
                    ('location_id', 'child_of', warehouse.lot_stock_id.id),
                ])

                counted_qty = sum(quants.mapped('inventory_quantity'))

                if counted_qty > 0:
                    lines.append(f"{warehouse.name}: {counted_qty}")

            record.branch_stock_info = (
                "Not available in any warehouse."
                if not lines
                else "\n".join(lines)
            )

                
