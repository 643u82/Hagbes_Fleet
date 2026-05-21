from odoo import models, fields, api
class IssueReturnWizardLine(models.TransientModel):
    _name = 'exhibition.return.modal.items'
    _description = 'exhibition return modal items'

    modal_id = fields.Many2one('exhibition.return.modal', required=True)
    product_id = fields.Many2one('product.product', string='Product', readonly=True)
    uom_id = fields.Many2one('uom.uom', string='Unit of Measure', readonly=True)
    original_qty = fields.Float(string='Issued Quantity', readonly=True)
    return_qty = fields.Float(string='Return Quantity', required=True)
