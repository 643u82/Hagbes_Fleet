from odoo import fields, models, api
from odoo.exceptions import ValidationError

class InterstockTransferLine(models.Model):
    _name = 'request.items'
    _description = 'Requested Items for Inter-Stock Transfer'

    transfer_id = fields.Many2one('interstock.transfer', required=True, ondelete='cascade')
    product_id = fields.Many2one(
        'product.product',
        domain="[('id', 'in', available_product_ids)]"
    )   
    quantity = fields.Float(string="Quantity", required=True)
    uom_id = fields.Many2one('uom.uom', string="Unit of Measure", required=True)
    location_id = fields.Many2one('stock.location', string='Issuer Location')
    available_product_ids = fields.Many2many('product.product', compute='_compute_available_product_ids')

    # ------------------------------
    # Compute available products based on transfer warehouse
    # ------------------------------
    @api.depends('transfer_id', 'transfer_id.issuer_warehouse_id')
    def _compute_available_product_ids(self):
        for record in self:
            if record.transfer_id and record.transfer_id.issuer_warehouse_id:
                warehouse_loc = record.transfer_id.issuer_warehouse_id.lot_stock_id
                product_ids = self.env['stock.quant'].sudo().search([
                    ('location_id', 'child_of', warehouse_loc.id),
                    ('quantity', '>', 0)
                ]).mapped('product_id.id')
                record.available_product_ids = [(6, 0, product_ids)]
            else:
                record.available_product_ids = [(5, 0, 0)]

    # ------------------------------
    # Auto-fill UoM when product is selected
    # ------------------------------
    @api.onchange('product_id')
    def _onchange_product_fill_uom(self):
        if self.product_id:
            self.uom_id = self.product_id.uom_id.id

    # ------------------------------
    # Suggest stock location and validate quantity
    # ------------------------------
    @api.onchange('product_id', 'quantity')
    def _onchange_product_id_set_location(self):
        self.location_id = False  # Clear previous

        if not self.product_id or not self.transfer_id or not self.transfer_id.issuer_warehouse_id:
            return

        warehouse_loc = self.transfer_id.issuer_warehouse_id.lot_stock_id

        # Fetch quants in warehouse with stock > 0
        quants = self.env['stock.quant'].sudo().search([
            ('product_id', '=', self.product_id.id),
            ('location_id', 'child_of', warehouse_loc.id),
            ('quantity', '>', 0)
        ])

        if not quants:
            # Product has no stock, prevent location assignment
            return

        total_available_qty = sum(quants.mapped('quantity'))

        # Assign first location with sufficient stock
        sufficient_quant = quants.filtered(lambda q: q.quantity >= (self.quantity or 0))
        self.location_id = sufficient_quant[:1].location_id if sufficient_quant else quants[:1].location_id

        # Optional: warning if requested qty > available
        if self.quantity and total_available_qty < self.quantity:
            return {
                'warning': {
                    'title': 'Insufficient Stock',
                    'message': (
                        f"'{self.product_id.display_name}' has only {total_available_qty} units available, "
                        f"but you requested {self.quantity}."
                    )
                }
            }

    # ------------------------------
    # Enforce stock validation on create
    # ------------------------------
    @api.model
    def create(self, vals):
        product_id = vals.get('product_id')
        transfer_id = vals.get('transfer_id')
        requested_qty = vals.get('quantity')

        if product_id and transfer_id:
            transfer = self.env['interstock.transfer'].browse(transfer_id)
            warehouse = transfer.issuer_warehouse_id
            if warehouse:
                warehouse_loc = warehouse.lot_stock_id

                quants = self.env['stock.quant'].sudo().search([
                    ('product_id', '=', product_id),
                    ('location_id', 'child_of', warehouse_loc.id),
                    ('quantity', '>', 0)
                ])
                total_available_qty = sum(quants.mapped('quantity'))

                if requested_qty <= 0:
                    raise ValidationError("Quantity must be greater than zero.")

                if total_available_qty < requested_qty:
                    raise ValidationError(
                        f"Not enough stock for '{self.env['product.product'].browse(product_id).display_name}'.\n"
                        f"Requested: {requested_qty}, Available: {total_available_qty}"
                    )

                # Auto-assign location
                if not vals.get('location_id'):
                    sufficient_quant = quants.filtered(lambda q: q.quantity >= requested_qty)
                    if sufficient_quant:
                        vals['location_id'] = sufficient_quant[0].location_id.id
                    elif quants:
                        vals['location_id'] = quants[0].location_id.id

        return super().create(vals)

    # ------------------------------
    # Dynamic domain for product selection
    # Only include products that have stock > 0 in the issuer warehouse
    # ------------------------------
    @api.onchange('transfer_id')
    def _onchange_transfer_id_set_domain(self):
        if self.transfer_id and self.transfer_id.issuer_warehouse_id:
            warehouse_loc = self.transfer_id.issuer_warehouse_id.lot_stock_id
            # Only products with quantity > 0
            product_ids = self.env['stock.quant'].sudo().search([
                ('location_id', 'child_of', warehouse_loc.id),
                ('quantity', '>', 0)
            ]).mapped('product_id').ids

            return {
                'domain': {
                    'product_id': [('id', 'in', product_ids)]
                }
            }