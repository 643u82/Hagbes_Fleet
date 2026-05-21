from odoo import models, fields

class BackorderRemarkWizard(models.TransientModel):
    _name = "backorder.remark.wizard"
    _description = "Backorder Remark Wizard"

    picking_id = fields.Many2one("stock.picking", required=True, readonly=True)
    remark = fields.Text("Remark", required=True)

    def action_confirm_remark(self):
        """Save remark, enable backorder smart button, and update PO backorder count."""
        self.picking_id.backorder_remark = self.remark
        self.picking_id.has_backorder_remark = True

        # trigger recompute of backorder_move_count on related PO
        if self.picking_id.purchase_id:
            self.picking_id.purchase_id._compute_backorder_move_count()

        return {"type": "ir.actions.act_window_close"}


