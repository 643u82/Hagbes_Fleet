from odoo import models, fields, api

class StockMove(models.Model):
    _inherit = 'stock.move'

    picking_type_code = fields.Selection(
        related='picking_id.picking_type_code',
        store=True,
        readonly=True
    )
    remark = fields.Selection([
            ('overage', 'Overage'),
            ('broken', 'Broken'),
            ('accessory_incomplete', 'Accessory Incomplete'),
            ('conform', 'Conform'),
        ], string='Remark')