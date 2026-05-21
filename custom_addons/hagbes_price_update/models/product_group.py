from odoo import models, fields, api

class ProductCategory(models.Model):
    _inherit = 'product.category'

    default_markup_percent = fields.Float(
        string='Default Markup %',
        digits=(16, 2),
        help='Default markup percentage for products in this category. '
             'This will be used to suggest a selling price based on the cost.'
    )

class ProductGroup(models.Model):
    _name = 'product.group'
    _description = 'Product Group'
    _order = 'name'

    name = fields.Char(
        string='Group Name',
        required=True,
        translate=True
    )
    code = fields.Char(
        string='Group Code',
        required=True
    )
    description = fields.Text(
        string='Description',
        translate=True
    )
    active = fields.Boolean(
        string='Active',
        default=True
    )
    parent_id = fields.Many2one(
        'product.group',
        string='Parent Group',
        ondelete='cascade'
    )
    child_ids = fields.One2many(
        'product.group',
        'parent_id',
        string='Child Groups'
    )
    product_count = fields.Integer(
        string='Products Count',
        compute='_compute_product_count'
    )
    default_markup_percent = fields.Float(
        string='Default Markup %',
        digits=(16, 2),
        help='Default markup percentage for products in this group'
    )

    @api.depends('name', 'code')
    def name_get(self):
        result = []
        for group in self:
            name = f"[{group.code}] {group.name}"
            result.append((group.id, name))
        return result

    @api.depends()
    def _compute_product_count(self):
        for group in self:
            group.product_count = self.env['product.product'].search_count([
                ('product_group_id', '=', group.id)
            ])

    def action_view_products(self):
        """Return action to view products belonging to this group"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Products',
            'res_model': 'product.product',  
            'view_mode': 'tree,form',
            'domain': [('product_group_id', '=', self.id)],
            'context': {'default_product_group_id': self.id},
        }
