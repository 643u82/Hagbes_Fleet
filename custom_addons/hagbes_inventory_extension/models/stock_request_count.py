from odoo import models, fields, api
from odoo.exceptions import UserError

class StockAdjustWizard(models.TransientModel):
    _name = 'stock.adjust.wizard'
    _description = 'Adjust Stock Quant'

    quant_ids = fields.Many2many('stock.quant', string="Quants")
    new_count = fields.Float(string="New Count", required=True)
    remark = fields.Text(string="Remark")
    user_id = fields.Many2one('res.users', string="User", default=lambda self: self.env.user, readonly=True)

    def action_apply_adjustment(self):
        """Apply adjustment and save remark/user permanently"""
        for quant in self.quant_ids:

            if quant.adjustment_count >= 3:
                # Close the wizard with a warning
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Adjustment Limit Reached',
                        'message': 'You cannot make more than 3 adjustments for this record.',
                        'type': 'warning',  # info, success, warning, danger
                        'sticky': False,  # auto close
                    }
                }

            quant.inventory_quantity = self.new_count
            quant.inventory_diff_quantity = self.new_count - quant.quantity
            quant.remark = self.remark
            quant.status = "reviewed"
            quant.review_confirmed_by = self.user_id.id
            quant.review_confirmed_date = fields.Datetime.now()
            # quant.action_apply_inventory()  # apply stock adjustment
            quant.adjustment_count += 1

        return {'type': 'ir.actions.act_window_close'}
