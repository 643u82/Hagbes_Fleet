from odoo import models, fields, api, _
from odoo.exceptions import UserError

class ManualInventoryEntry(models.Model):
    _name = 'manual.inventory.entry'
    _description = 'Manual Inventory Entry'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Reference', required=True, copy=False, readonly=True, default=lambda self: _('New'))
    
    product_id = fields.Many2one('product.product', string='Product', domain="[('type', 'in', ['product', 'consu'])]")
    part_number = fields.Char(string='Part Number / Default Code')
    product_name = fields.Char(string='Product Name')
    product_category_id = fields.Many2one('product.category', string='Product Category')
    
    procurement_type = fields.Selection([
        ('local', 'Local Purchase'),
        ('foreign', 'Foreign Purchase')
    ], string='Purchase Type', required=True, default='local')
    
    warehouse_id = fields.Many2one('stock.warehouse', string='Warehouse', required=True)
    location_id = fields.Many2one('stock.location', string='Location', required=True, domain="[('usage', '=', 'internal')]")
    
    warehouse_cost = fields.Float(string='Warehouse Cost (Standard Price)', required=True)
    selling_price = fields.Float(string='Selling Price (List Price)', required=True)
    quantity = fields.Float(string='Quantity', required=True, default=1.0)
    remark = fields.Text(string='Remark')
    
    state = fields.Selection([
        ('draft', 'Draft'),
        ('done', 'Done')
    ], string='Status', readonly=True, copy=False, index=True, tracking=True, default='draft')
    
    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            self.part_number = self.product_id.default_code
            self.product_name = self.product_id.name
            self.product_category_id = self.product_id.categ_id.id
            self.warehouse_cost = self.product_id.standard_price
            self.selling_price = self.product_id.list_price
            
    @api.onchange('part_number')
    def _onchange_part_number(self):
        if self.part_number and not self.product_id:
            product = self.env['product.product'].search([('default_code', '=', self.part_number)], limit=1)
            if product:
                self.product_id = product.id
                self._onchange_product_id()

    @api.onchange('warehouse_id')
    def _onchange_warehouse_id(self):
        if self.warehouse_id:
            self.location_id = self.warehouse_id.lot_stock_id.id
                
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('manual.inventory.entry') or _('New')
        return super().create(vals_list)

    def action_apply(self):
        self.ensure_one()
        if self.state != 'draft':
            return
            
        if self.quantity <= 0.0:
            raise UserError(_("Quantity must be greater than zero."))
            
        product = self.product_id
        if not product:
            if self.part_number:
                product = self.env['product.product'].search([('default_code', '=', self.part_number)], limit=1)
                
            if not product:
                if not self.product_name:
                    raise UserError(_('Please provide a Product Name to create a new product.'))
                if not self.product_category_id:
                    raise UserError(_('Please select a Product Category for the new product.'))
                
                # Create the product. Odoo typically uses `type='product'` for storable in 18
                product_vals = {
                    'name': self.product_name,
                    'default_code': self.part_number,
                    'list_price': self.selling_price,
                    'type': 'product',
                    'categ_id': self.product_category_id.id,
                }
                product = self.env['product.product'].create(product_vals)
                self.product_id = product.id
            else:
                self.product_id = product.id
                
        # Update list_price (Selling Price)
        product.list_price = self.selling_price
        
        # Find the inventory adjustment location
        inventory_location = self.env['stock.location'].search([
            ('usage', '=', 'inventory'),
            ('company_id', 'in', [self.env.company.id, False])
        ], limit=1)
        
        if not inventory_location:
            raise UserError(_("No Inventory location found for the company."))        
        move_vals = {
            'name': f'Manual Intake: {self.name}',
            'product_id': product.id,
            'product_uom': product.uom_id.id,
            'product_uom_qty': self.quantity,
            'location_id': inventory_location.id,
            'location_dest_id': self.location_id.id,
            'price_unit': self.warehouse_cost,
            'company_id': self.env.company.id,
        }
        
        move = self.env['stock.move'].create(move_vals)
        move._action_confirm()
        
        if not move.move_line_ids:
            move.move_line_ids = [(0, 0, {
                'product_id': product.id,
                'location_id': inventory_location.id,
                'location_dest_id': self.location_id.id,
                'quantity': self.quantity,
                'product_uom_id': product.uom_id.id,
            })]
        else:
            move.move_line_ids.write({'quantity': self.quantity})
            
        move.picked = True
        move._action_done()
        
        self.state = 'done'
