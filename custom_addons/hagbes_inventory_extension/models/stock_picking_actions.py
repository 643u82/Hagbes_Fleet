from odoo import models, api,fields
from odoo.exceptions import UserError

class StockPicking(models.Model):
    _inherit = 'stock.picking'

    internal_issue = fields.Boolean(string="Internal Issue",default=False,help="Mark this picking as an internal issue")
    exhibition_issue = fields.Boolean(string="Internal exhibition", default=False, help="Mark this picking as an internal issue")
    inter_store_issue = fields.Boolean(string="Internal store", default=False, help="Mark this picking as an internal issue")
    backorder_remark = fields.Text("Backorder Remark")

    has_backorder_remark = fields.Boolean("Has Backorder Remark", default=False,store=True)

    purchase_order_state = fields.Selection(
        related='purchase_id.state',
        string="Purchase Order State",
        store=True,
        readonly=True,
    )
    def print_grn(self):
        return self.env.ref('hagbes_inventory_extension.grn_report').report_action(self)

    def button_validate(self):

        for picking in self:
            # --- Check if backorder is needed (less qty received)
            need_backorder = any(
                move.product_uom_qty > sum(line.quantity for line in move.move_line_ids)
                for move in picking.move_ids_without_package
            )
            print(picking.has_backorder_remark)
            if need_backorder and picking.picking_type_code == "incoming" and not picking.has_backorder_remark:
                # Open our custom backorder remark wizard instead of default
                return {
                    'name': 'Backorder Remark',
                    'type': 'ir.actions.act_window',
                    'res_model': 'backorder.remark.wizard',
                    'view_mode': 'form',
                    'target': 'new',
                    'context': {'default_picking_id': picking.id},
                }
            else:
                picking.has_backorder_remark=False


            # --- If no backorder needed → continue with normal Odoo flow
        res = super().button_validate()


        current_picking=self.origin
        for picking in self:
            if picking.origin and picking.state == 'done':
                # --- Handle interstock transferx
                transfer1 = self.env['interstock.transfer'].search([
                    ('name', '=', current_picking),
                    ('feeding_picking_id', '=', picking.id),
                    ('state', '=', 'approved')
                ], limit=1)
                if transfer1 and not transfer1.receiving_picking_id:
                    transfer1.state = 'ready'

                # --- Handle exhibition transfer
                transfer2 = self.env['exhibition.requests'].search([
                    ('name', '=', current_picking),
                    ('feeding_picking_id', '=', picking.id),
                    ('state', '=', 'approved')
                ], limit=1)
                if transfer2 and not transfer2.receiving_picking_id:
                    transfer2._create_receiving_transfer()
                    transfer2.state = 'done'

                # --- Reset only the relevant flag based on origin
                if picking.origin.startswith('ISN'):
                    picking.internal_issue = False
                elif picking.origin.startswith('EXN'):
                    picking.exhibition_issue = False
                elif picking.origin.startswith('TRF'):
                    picking.inter_store_issue = False
        # -------------------------------------------------------
        #           MRCV ISSUE HANDLING (Your Requested Part)
        # -------------------------------------------------------
        for picking in self:
            if picking.state != 'done':
                continue

            # Find the MRCV linked to this picking
            mrcv = self.env['mrcv.header'].sudo().search([
                ('feeding_picking_id', '=', picking.id)
            ], limit=1)

            if mrcv:
                # Update issued quantities on each MRCV line
                for move in picking.move_ids_without_package:
                    mrcv_line = self.env['mrcv.line'].sudo().search([
                        ('mrcv_id', '=', mrcv.id),
                        ('product_id', '=', move.product_id.id)
                    ], limit=1)

                    if mrcv_line:
                        mrcv_line.issued_qty = move.quantity

                # Mark MRCV as issued
                mrcv.state = 'issued'

        # -------------------------------------------------------

        return res

    def print_inter_store(self):
        self.ensure_one()
        # Find the related interstock.transfer
        transfer = self.env['interstock.transfer'].search(['|',('feeding_picking_id', '=', self.id),('receiving_picking_id', '=', self.id)], limit=1)
        if not transfer:
            raise UserError("No interstore transfer linked to this picking.")
        return self.env.ref('hagbes_inventory_extension.action_inter_store').report_action(transfer)

    def print_temporary_note(self):
        self.ensure_one()
        # Find the related interstock.transfer
        transfer = self.env['exhibition.requests'].search(
            [('feeding_picking_id', '=', self.id)],limit=1)
        if not transfer:
            raise UserError("No temporary transfer linked to this picking.")
        return self.env.ref('hagbes_inventory_extension.action_temporary_note').report_action(transfer)

    def print_issue_note(self):
        self.ensure_one()
        # Find the related interstock.transfer
        transfer = self.env['interstock.transfer'].search(
            ['|', ('feeding_picking_id', '=', self.id), ('receiving_picking_id', '=', self.id)], limit=1)
        if not transfer:
            raise UserError("No interstore transfer linked to this picking.")
        return self.env.ref('hagbes_inventory_extension.action_issue_note').report_action(transfer)

    def print_delivery_order(self):
        return self.env.ref('hagbes_inventory_extension.action_temporary_note').report_action(self)


    # def _process_backorder(self):
    #     """Override to block default popup and show custom wizard."""
    #     for picking in self:
    #         if any(move.product_uom_qty > move.quantity_done for move in picking.move_ids_without_package):
    #             return {
    #                 "name": "Backorder Remark",
    #                 "type": "ir.actions.act_window",
    #                 "res_model": "stock.backorder.remark.wizard",
    #                 "view_mode": "form",
    #                 "target": "new",
    #                 "context": {"default_picking_id": picking.id},
    #             }
    #     return super()._process_backorder()
