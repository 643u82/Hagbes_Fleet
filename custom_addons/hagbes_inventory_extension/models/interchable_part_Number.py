from odoo import models, fields

class ProductInterchange(models.Model):
    _name = 'product.interchange'
    _description = 'Interchangeable Part Number'

    name = fields.Char(string="Part Number", required=True)
    _sql_constraints = [
        ('unique_part_number', 'unique(name)', 'Part Number must be unique!'),
    ]

    product_id = fields.Many2many(
        'product.template',
        'product_interchange_rel',
        'interchange_id',
        'product_id',
        string='Products'
    )

