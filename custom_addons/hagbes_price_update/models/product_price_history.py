from odoo import models, fields, api
from datetime import datetime


class ProductPriceHistory(models.Model):
    _name = 'product.price.history'
    _description = 'Product Price History'
    _order = 'update_date desc'
    _rec_name = 'display_name'

    product_id = fields.Many2one(
        'product.product',
        string='Product',
        required=True,
        ondelete='cascade'
    )
    product_template_id = fields.Many2one(
        'product.template',
        string='Product Template',
        required=True,
        ondelete='cascade'
    )
    old_price = fields.Float(
        string='Old Price',
        digits='Product Price',
        required=True
    )
    new_price = fields.Float(
        string='New Price',
        digits='Product Price',
        required=True
    )
    price_difference = fields.Float(
        string='Price Difference',
        compute='_compute_price_difference',
        store=True,
        digits='Product Price'
    )
    price_change_percent = fields.Float(
        string='Change %',
        compute='_compute_price_change_percent',
        store=True,
        digits=(16, 2)
    )
    updated_by = fields.Many2one(
        'res.users',
        string='Updated By',
        required=True,
        default=lambda self: self.env.user
    )
    update_date = fields.Datetime(
        string='Update Date',
        required=True,
        default=fields.Datetime.now
    )
    reason = fields.Text(
        string='Reason for Change'
    )
    update_type = fields.Selection([
        ('manual', 'Manual Update'),
        ('bulk', 'Bulk Update'),
        ('import', 'Import'),
        ('system', 'System Update')
    ], string='Update Type', default='manual')
    
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        related='product_id.currency_id',
        store=True
    )
    
    display_name = fields.Char(
        string='Display Name',
        compute='_compute_display_name',
        store=True
    )

    @api.depends('old_price', 'new_price')
    def _compute_price_difference(self):
        for record in self:
            record.price_difference = record.new_price - record.old_price

    @api.depends('old_price', 'new_price')
    def _compute_price_change_percent(self):
        for record in self:
            if record.old_price:
                record.price_change_percent = ((record.new_price - record.old_price) / record.old_price) * 100
            else:
                record.price_change_percent = 0.0

    @api.depends('product_id', 'update_date')
    def _compute_display_name(self):
        for record in self:
            if record.product_id and record.update_date:
                record.display_name = f"{record.product_id.name} - {record.update_date.strftime('%Y-%m-%d %H:%M')}"
            else:
                record.display_name = "Price History"

    @api.model
    def create_price_history(self, product_id, old_price, new_price, reason=None, update_type='manual'):
        """Helper method to create price history records"""
        product = self.env['product.product'].browse(product_id)
        if product.exists():
            return self.create({
                'product_id': product_id,
                'product_template_id': product.product_tmpl_id.id,
                'old_price': old_price,
                'new_price': new_price,
                'reason': reason or 'Price updated',
                'update_type': update_type,
            })
        return False
