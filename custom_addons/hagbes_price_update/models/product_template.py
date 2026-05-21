from odoo import models, fields, api


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    product_group_id = fields.Many2one(
        'product.group',
        string='Product Group',
        help='Product group for price management and categorization'
    )

    price_history_ids = fields.One2many(
        'product.price.history',
        'product_template_id',
        string='Price History'
    )
    
    price_history_count = fields.Integer(
        string='Price History Count',
        compute='_compute_price_history_count'
    )
    
    last_price_update = fields.Datetime(
        string='Last Price Update',
        compute='_compute_last_price_update'
    )
    
    min_margin_percent = fields.Float(
        string='Minimum Margin %',
        digits=(16, 2),
        help='Minimum allowed margin percentage for this product'
    )
    
    max_margin_percent = fields.Float(
        string='Maximum Margin %',
        digits=(16, 2),
        help='Maximum allowed margin percentage for this product'
    )

    current_markup_percent = fields.Float(
        string='Current Markup %',
        compute='_compute_markup_margin',
        digits=(16, 2),
        help='Current markup percentage over cost price'
    )
    
    current_margin_percent = fields.Float(
        string='Current Margin %',
        compute='_compute_markup_margin',
        digits=(16, 2),
        help='Current margin percentage'
    )

    needs_price_update = fields.Boolean(
        string="Needs Price Update",
        default=False,
        copy=False,
        help="If checked, this product has a new cost and is awaiting a sales price update. It will not be available for sale."
    )

    sale_ok = fields.Boolean(
        'Can be Sold', default=True,
        compute='_compute_sale_ok', store=True, readonly=False
    )

    @api.depends('price_history_ids')
    def _compute_price_history_count(self):
        for record in self:
            record.price_history_count = len(record.price_history_ids)

    @api.depends('price_history_ids.update_date')
    def _compute_last_price_update(self):
        for record in self:
            if record.price_history_ids:
                record.last_price_update = max(record.price_history_ids.mapped('update_date'))
            else:
                record.last_price_update = False

    @api.depends('list_price', 'standard_price')
    def _compute_markup_margin(self):
        for record in self:
            if record.standard_price > 0:
                # Markup = (Selling Price - Cost Price) / Cost Price * 100
                record.current_markup_percent = ((record.list_price - record.standard_price) / record.standard_price) * 100
                # Margin = (Selling Price - Cost Price) / Selling Price * 100
                record.current_margin_percent = ((record.list_price - record.standard_price) / record.list_price) * 100 if record.list_price > 0 else 0
            else:
                record.current_markup_percent = 0
                record.current_margin_percent = 0

    @api.onchange('product_group_id')
    def _onchange_product_group_id(self):
        if self.product_group_id and self.product_group_id.default_markup_percent:
            if self.standard_price > 0:
                # Calculate new selling price based on default markup
                markup_multiplier = 1 + (self.product_group_id.default_markup_percent / 100)
                self.list_price = self.standard_price * markup_multiplier

    @api.depends('needs_price_update')
    def _compute_sale_ok(self):
        """A product cannot be sold if it's waiting for a price update."""
        for template in self:
            template.sale_ok = not template.needs_price_update

    def write(self, vals):
        # Track price changes
        if 'list_price' in vals:
            for record in self:
                old_price = record.list_price
                new_price = vals['list_price']
                if old_price != new_price:
                    # Create history record for each variant
                    for variant in record.product_variant_ids:
                        self.env['product.price.history'].create_price_history(
                            variant.id,
                            old_price,
                            new_price,
                            reason='Price updated via form',
                            update_type='manual'
                        )
        
        # If price is updated, assume it no longer needs an update.
        if 'list_price' in vals and 'needs_price_update' not in vals:
            vals['needs_price_update'] = False

        return super().write(vals)

    def action_view_price_history(self):
        """Action to view price history"""
        self.ensure_one()
        return {
            'name': f'Price History - {self.name}',
            'type': 'ir.actions.act_window',
            'res_model': 'product.price.history',
            'view_mode': 'tree,form',
            'domain': [('product_template_id', '=', self.id)],
            'context': {'default_product_template_id': self.id},
        }


class ProductProduct(models.Model):
    _inherit = 'product.product'

    product_group_id = fields.Many2one(
        'product.group',
        related='product_tmpl_id.product_group_id',
        string='Product Group',
        store=True,
        readonly=False
    )
