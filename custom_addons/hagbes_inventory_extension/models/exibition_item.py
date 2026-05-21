from odoo import fields, models,api
class ExhibitionRequestsItem(models.Model):
    _name = 'exhibition.requests.items'
    _description = 'Exhibition Request Items'
    issued_id = fields.Many2one('exhibition.requests', required=True, ondelete='cascade')
    product_id = fields.Many2one('product.product', string="Product", required=True)
    quantity = fields.Float(string="Quantity", required=True)
    uom_id = fields.Many2one('uom.uom', required=True)

    @api.onchange('product_id')
    def _onchange_product_fill_uom(self):
        if self.product_id:
            self.uom_id = self.product_id.uom_id.id
    @api.onchange('product_id', 'quantity')
    def _onchange_product_id_set_location(self):
        if not self.product_id or not self. issued_id or not self.issued_id.issuer_warehouse:
            return
        warehouse_location = self.issued_id.issuer_warehouse.lot_stock_id
        quants = self.env['stock.quant'].sudo().search([
            ('product_id', '=', self.product_id.id),
            ('location_id', 'child_of', warehouse_location.id),
        ])
        if not quants:
            return {
                'warning': {
                    'title': 'No Stock Available',
                    'message': f"The product '{self.product_id.display_name}' is completely out of stock in the issuer warehouse."
                }
            }
        total_available_qty = sum(quants.mapped('quantity'))
        if self.quantity:
            if total_available_qty == 0:
                return {
                    'warning': {
                        'title': 'No Stock Available',
                        'message': f"The product '{self.product_id.display_name}' is completely out of stock in the issuer warehouse."
                    }
                }
            elif total_available_qty < self.quantity:
                return {
                    'warning': {
                        'title': 'Insufficient Stock',
                        'message': (
                            f"The product '{self.product_id.display_name}' has only {total_available_qty} units available, "
                            f"but you requested {self.quantity}. Please adjust the quantity or check availability."
                        )
                    }
                }
