from odoo import models, fields

class SaleConfirmationLine(models.TransientModel):
    _name = 'sale.confirmation.line'
    _description = 'Sale Confirmation Line'

    wizard_id = fields.Many2one('sale.confirmation.wizard')
    product_id = fields.Many2one('product.product', required=True)
    requested = fields.Float()
    available = fields.Float()
    shortage = fields.Float()
