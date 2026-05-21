from odoo import models

class SaleAdvancePaymentInv(models.TransientModel):
    _inherit = "sale.advance.payment.inv"

    def _prepare_invoice_values(self, order, name, amount):
        res = super()._prepare_invoice_values(order, name, amount)

        # Get first sale order line with product
        so_lines = order.order_line.filtered(lambda l: l.product_id and l.product_uom_qty > 0)
        if not so_lines:
            return res

        main_line = so_lines[0]

        for line in res['invoice_line_ids']:
            if isinstance(line, tuple) and line[0] == 0:
                line_vals = line[2]

                # Copy product and quantity from original SO line
                line_vals['product_id'] = main_line.product_id.id
                line_vals['quantity'] = main_line.product_uom_qty
                line_vals['name'] = main_line.name  
        return res