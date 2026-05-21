from odoo import models, fields

class StockWarehouse(models.Model):
    _inherit = 'stock.warehouse'

    branch_id = fields.Many2one('account.analytic.account', string='Company Branch', domain=[('plan_id', '=', 'Branch')])
