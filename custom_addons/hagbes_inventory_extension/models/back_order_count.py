from email.policy import default

from odoo import models, fields,api
class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    backorder_move_count = fields.Integer(
        string="Backorder Moves",
        compute="_compute_backorder_move_count",
        default=0,
        store=True
    )

    @api.depends('picking_ids.move_ids_without_package.quantity', 'picking_ids.move_ids_without_package.product_uom_qty')
    def _compute_backorder_move_count(self):
        for order in self:
            count = 0
            # loop through all pickings linked to the PO
            for picking in order.picking_ids:
                for move in picking.move_ids_without_package:
                    demand = move.product_uom_qty
                    done = sum(line.quantity for line in move.move_line_ids)
                    if done < demand:
                        count += 1
            order.backorder_move_count = count

    def action_trigger_backorder(self):
        """Open the normal Odoo backorder confirmation wizard for the first picking of this PO that needs backorder."""
        self.ensure_one()
        pickings = self.picking_ids.filtered(
            lambda p: any(
                move.product_uom_qty > sum(line.quantity for line in move.move_line_ids)
                for move in p.move_ids_without_package
            )
        )
        if not pickings:
            return

        picking = pickings[0]  # take only the first incomplete picking
        print(picking.id)
        return {
            'name': 'Backorder',
            'type': 'ir.actions.act_window',
            'res_model': 'stock.backorder.confirmation',
            'view_mode': 'form',
            'view_id': self.env.ref('stock.view_backorder_confirmation').id,
            'target': 'new',
            'context': dict(
                default_pick_ids=[(4, picking.id)],
                button_validate_picking_ids=[picking.id]
            )
        }



