from odoo import models, fields, api
from odoo.exceptions import UserError

class SaleConfirmationWizard(models.TransientModel):
    _name = 'sale.confirmation.wizard'
    _description = 'Sale Confirmation Wizard'

    sale_order_id = fields.Many2one('sale.order', required=True)
    line_ids = fields.One2many('sale.confirmation.line', 'wizard_id', string="Shortages")

    @api.model
    def default_get(self, fields):
        res = super().default_get(fields)
        order = self.env['sale.order'].browse(self._context.get('active_id'))

       
        wizard_lines = []
        for line in order.order_line:
            if line.product_id.type == 'product':
                qty_available = line.product_id.qty_available
                if qty_available < line.product_uom_qty:
                    wizard_lines.append((0, 0, {
                        'product_id': line.product_id.id,
                        'requested': line.product_uom_qty,
                        'available': qty_available,
                        'shortage': line.product_uom_qty - qty_available
                    }))

        res['line_ids'] = wizard_lines
        res['sale_order_id'] = order.id
        return res

    def confirm_partial(self):
        for line in self.line_ids:
            product = line.product_id
            requested = line.requested
            available = line.available
            shortage = line.shortage

            # Find matching order line(s)
            order_lines = self.sale_order_id.order_line.filtered(lambda l: l.product_id.id == product.id)
            for order_line in order_lines:
                if available <= 0:
                    # Case: No stock → Remove line & register entire quantity as lost
                    order_line.unlink()
                    self.env['lost.sale'].create({
                        'product_id': product.id,
                        'customer_id': self.sale_order_id.partner_id.id,
                        'sale_order_id': self.sale_order_id.id,
                        'quantity_requested': requested,
                        'quantity_available': 0.0,
                        'quantity_lost':requested,
                        'branch_id':self.sale_order_id.branch_id.id,
                        'company_id':self.sale_order_id.company_id.id,
                        'warehouse_id':self.sale_order_id.warehouse_id.id,
                        
                        'reason': 'out_of_stock',
                    })

                elif shortage > 0:
                    # Case: Partial stock → Adjust qty and register shortage
                    order_line.product_uom_qty = available
                    self.env['lost.sale'].create({
                        'product_id': product.id,
                        'customer_id': self.sale_order_id.partner_id.id,
                        'sale_order_id': self.sale_order_id.id,
                        'quantity_requested': requested,
                        'quantity_available': available,
                        'quantity_lost':shortage,
                        'branch_id':self.sale_order_id.branch_id.id,
                        'company_id':self.sale_order_id.company_id.id,
                        'warehouse_id':self.sale_order_id.warehouse_id.id,
                        'reason': 'partial_stock',
                    })

        # Confirm the updated order
        self.sale_order_id._action_confirm()

    def mark_as_lost(self):
        for line in self.line_ids:
            self.env['lost.sale'].create({
                'product_id': line.product_id.id,
                'customer_id': self.sale_order_id.partner_id.id,
                'sale_order_id': self.sale_order_id.id,
                'quantity_requested': line.requested,
                'quantity_available': line.available,
                'quantity_lost':line.requested,
                'branch_id':self.sale_order_id.branch_id.id,
                'company_id':self.sale_order_id.company_id.id,
                'warehouse_id':self.sale_order_id.warehouse_id.id,
                'reason': 'out_of_stock',
            })

        self.sale_order_id.write({'state': 'lost'})
