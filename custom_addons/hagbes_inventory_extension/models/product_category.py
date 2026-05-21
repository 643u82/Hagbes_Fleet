from odoo import fields, models

class ProductCategory(models.Model):
    _inherit = 'product.category'  # Inherit the existing product.category model

    code = fields.Char(string='Category Code', copy=False,
                       help="A unique code for the product category.")
    _sql_constraints = [
        ('code_uniq', 'unique (code)', 'The category code must be unique!'),
    ]