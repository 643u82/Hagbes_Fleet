from odoo import models, fields, api
from datetime import datetime
from odoo.exceptions import UserError,ValidationError
import logging

_logger = logging.getLogger(__name__)

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    branch_id = fields.Many2one(
        'account.analytic.account',
        string='Branch',
        domain=lambda self: self._get_branch_domain(),
        required=True
    )
    available_product_ids = fields.Many2many(
        'product.product',
        compute='_compute_available_product_ids',
        store=False
    )
    
    def _prepare_invoice(self):
        invoice_vals = super()._prepare_invoice()
        invoice_vals['branch_id'] = self.branch_id.id
        return invoice_vals
    
    @api.depends('warehouse_id')
    def _compute_available_product_ids(self):
        for order in self:
            product_ids = []
            # Always include services
            service_products = self.env['product.product'].search([('type', '=', 'service'), ('sale_ok', '=', True)])
            product_ids.extend(service_products.ids)

            # Add storable products available in the selected warehouse
            if order.warehouse_id:
                # Get all internal locations belonging to this warehouse
                internal_locations = self.env['stock.location'].search([
                    ('warehouse_id', '=', order.warehouse_id.id),
                    ('usage', '=', 'internal')
                ])
                if internal_locations:
                    quants = self.env['stock.quant'].search([
                        ('location_id', 'in', internal_locations.ids),
                        # ('quantity', '>', 0),
                    ])
                    storable_products = quants.mapped('product_id').filtered(lambda p: p.type != 'service')
                    product_ids.extend(storable_products.ids)

            order.available_product_ids = list(set(product_ids))

    
    @api.model
    def _get_branch_domain(self):
        user = self.env.user
        return [('id', 'in', user.allowed_branch_ids.ids)]
    @api.onchange('warehouse_id')
    def _onchange_warehouse_id(self):
        """Clear order lines when warehouse changes (optional, for consistency)"""
        if self.order_line:
            # Optional: warn or clear lines — depends on business logic
            pass

    @api.model
    def create(self, vals):
        if not vals.get('order_line'):
            raise ValidationError("You must add at least one product to the sales order.")

        self._check_pricelist_permission(vals)

        if vals.get('branch_id') and (not vals.get('name') or vals.get('name') == 'New'):
            try:
                # Get branch and year
                branch = self.env['account.analytic.account'].browse(vals['branch_id'])
                branch_code = branch.code or '00'
                year = str(datetime.now().year)[-2:]

                # Dynamic sequence code per branch/year
                seq_code = f'sale.order.{branch_code}.{year}'

                # Find or create the sequence
                sequence = self.env['ir.sequence'].sudo().search([('code', '=', seq_code)], limit=1)
                if not sequence:
                    sequence = self.env['ir.sequence'].sudo().create({
                        'name': f'Sales Order {branch_code} {year}',
                        'code': seq_code,
                        'prefix': '',          # We build prefix manually
                        'padding': 5,          # Ensure 5-digit numbers
                        'number_next': 1,
                        'number_increment': 1,
                        'implementation': 'standard',
                        'use_date_range': False,  # Set to True if you want yearly reset
                        'active': True,
                    })

                # Get next number from sequence
                next_number = sequence.next_by_id()
               

                # Convert to integer and format as 5-digit string
                formatted_number = f"{int(next_number):05d}"

                # Build final name
                vals['name'] = f"S{branch_code}{year}{formatted_number}"

            except Exception as e:
                raise ValidationError(f"Error generating sequence: {e}")

        return super(SaleOrder, self).create(vals)
class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    product_type = fields.Selection(related='product_id.type', readonly=True, store=False)



    def write(self, vals):
        if 'price_unit' in vals:
            raise UserError("You cannot modify the Unit Price of a sale order line.")
        return super(SaleOrderLine, self).write(vals)

    def _prepare_invoice(self):
        invoice_vals = super()._prepare_invoice()
        invoice_vals['branch_id'] = self.branch_id.id
        return invoice_vals
    def _prepare_invoice_line(self, **optional_values):
        invoice_line_vals = super()._prepare_invoice_line(**optional_values)
        if self.order_id.branch_id:
            invoice_line_vals['analytic_distribution'] ={
                self.order_id.branch_id.id: 100.0,
            }
        return invoice_line_vals