from odoo import models, fields, api
from odoo.exceptions import UserError

class IssueReturnWizard(models.TransientModel):
    _name = 'exhibition.return.modal'
    _description = 'Issue Return Modal'

    issue_request_id = fields.Many2one('exhibition.requests', string='Modal', required=True)
    line_ids = fields.One2many('exhibition.return.modal.items', 'modal_id', string='Lines')
    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        exhibition_request = self.env['exhibition.requests'].browse(self.env.context.get('active_id'))
        if exhibition_request:
            res['issue_request_id'] = exhibition_request.id
            lines = []
            for line in exhibition_request.items_requested:
                if not line.product_id or line.quantity <= 0:
                    continue
                lines.append((0, 0, {
                    'product_id': line.product_id.id,
                    'uom_id': line.uom_id.id,
                    'original_qty': line.quantity,
                    'return_qty': line.quantity,
                }))
            res['line_ids'] = lines
        return res

    def action_confirm_return(self):
        self.ensure_one()
        issue = self.issue_request_id
        if issue.feeding_picking_id.state != 'done':
            raise UserError(
                "The original feeding transfer is not validated.\n"
                "Validate the feeding transfer first, then try again."
            )
        transit_location = self.env['stock.location'].search([
            ('usage', '=', 'internal'),
            ('name', '=', 'Exhibition Stock')
        ], limit=1)
        if not transit_location:
            raise UserError("Exhibition Issue transit location not found.")

        stock_location = issue.issuer_warehouse.lot_stock_id
        if not stock_location:
            raise UserError("Issuer warehouse stock location is not properly configured.")

        # Get internal picking type
        picking_type = self.env['stock.picking.type'].sudo().search([
            ('code', '=', 'internal'),
            ('warehouse_id', '=', issue.issuer_warehouse.id)
        ], limit=1)
        if not picking_type:
            raise UserError("No internal picking type found for this warehouse.")

        # Build stock moves based on quantities entered
        exhibition_request = self.env['exhibition.requests'].browse(self.env.context.get('active_id'))
        moves = []

        # Create a dictionary to quickly find request lines by product_id
        request_line_map = {line.product_id.id: line for line in exhibition_request.items_requested}

        for wizard_line in self.line_ids:
            if wizard_line.return_qty <= 0:
                continue

            # Match the wizard line to the original request line
            request_line = request_line_map.get(wizard_line.product_id.id)
            if not request_line:
                raise UserError(f"Product {wizard_line.product_id.display_name} not found in original request.")

            # Validate return quantity
            if wizard_line.return_qty > request_line.quantity:
                raise UserError(
                    f"Return qty for {wizard_line.product_id.display_name} "
                    f"cannot exceed original issued qty {request_line.quantity}."
                )

            # Build move line from request line data but override the qty with wizard qty
            moves.append((0, 0, {
                'product_id': request_line.product_id.id,
                'name': request_line.product_id.display_name,
                'product_uom': request_line.uom_id.id,
                'product_uom_qty': wizard_line.return_qty,
                'location_id': transit_location.id,
                'location_dest_id': stock_location.id,
            }))

        if not moves:
            raise UserError("No valid quantities to return.")

        # Create picking for the return
        picking = self.env['stock.picking'].create({
            'picking_type_id': picking_type.id,
            'origin': f"{issue.name} - Return",
            'location_id': transit_location.id,
            'location_dest_id': stock_location.id,
            'company_id': issue.company_id.id,
            'move_ids_without_package': moves,
        })

        # Auto-process the picking
        picking.action_confirm()
        picking.action_assign()
        for ml in picking.move_line_ids:
            ml.qty_done = ml.product_uom_qty
        picking.button_validate()

        # Update issue state
        issue.state = 'returned'
