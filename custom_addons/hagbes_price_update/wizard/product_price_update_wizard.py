from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError
import logging

_logger = logging.getLogger(__name__)


class ProductPriceUpdateWizard(models.TransientModel):
    _name = 'product.price.update.wizard'
    _description = 'Product Price Update Wizard'

     
    update_type = fields.Selection([
        ('fixed', 'Fixed Amount'),
        ('percentage', 'Percentage'),
        ('direct', 'Set New Price'),
        ('margin', 'By Margin')
    ], string='Update Type', required=True, default='percentage')
    
    # Update values
    fixed_value = fields.Float(
        string='Fixed Amount',
        digits='Product Price',
        help='Amount to add/subtract from current price'
    )
    percentage_value = fields.Float(
        string='Percentage',
        digits=(16, 2),
        help='Percentage to increase/decrease (use negative for decrease)'
    )
    direct_value = fields.Float(
        string='New Price',
        digits='Product Price',
        help='Set this exact price for selected products'
    )
    margin_percent = fields.Float(
        string='Target Margin %',
        digits=(16, 2),
        help='Target margin percentage based on cost price'
    )
    
    # Product selection
    product_ids = fields.Many2many(
        'product.product',
        string='Products',
        required=True
    )
    product_template_ids = fields.Many2many(
        'product.template',
        string='Product Templates'
    )
    
    # Filters
    category_ids = fields.Many2many(
        'product.category',
        string='Product Categories',
        help='Filter products by categories'
    )
    
    
    
    # Options
    apply_to_variants = fields.Boolean(
        string='Apply to All Variants',
        default=True,
        help='Apply price update to all product variants'
    )
    
    check_margin_limits = fields.Boolean(
        string='Check Margin Limits',
        default=True,
        help='Validate against minimum/maximum margin limits'
    )
    
    # Reason and notes
    reason = fields.Text(
        string='Reason for Update',
        required=True,
        default='Bulk price update'
    )
    
    # Preview and validation
    preview_lines = fields.One2many(
        'product.price.update.preview',
        'wizard_id',
        string='Preview'
    )
    
    show_preview = fields.Boolean(
        string='Show Preview',
        default=False
    )
    
    total_products = fields.Integer(
        string='Total Products',
        compute='_compute_totals'
    )
    
    total_price_increase = fields.Float(
        string='Total Price Increase',
        compute='_compute_totals',
        digits='Product Price'
    )

    @api.depends('preview_lines')
    def _compute_totals(self):
        for wizard in self:
            wizard.total_products = len(wizard.preview_lines)
            wizard.total_price_increase = sum(wizard.preview_lines.mapped('price_difference'))

    @api.onchange('category_ids')
    def _onchange_category_ids(self):
        """Filter products by selected categories"""
        # Populate either templates or product variants depending on `apply_to_variants`
        if not self.category_ids:
            # clear selections when no category
            self.product_template_ids = [(5, 0, 0)]
            self.product_ids = [(5, 0, 0)]
            return

        cat_ids = self.category_ids.ids
        if self.apply_to_variants:
            templates = self.env['product.template'].search([('categ_id', 'child_of', cat_ids)])
            self.product_template_ids = [(6, 0, templates.ids)]
            # Clear product_ids because templates are used
            self.product_ids = [(5, 0, 0)]
        else:
            products = self.env['product.product'].search([('product_tmpl_id.categ_id', 'child_of', cat_ids)])
            self.product_ids = [(6, 0, products.ids)]
            # Clear template selection when working on variants
            self.product_template_ids = [(5, 0, 0)]

    

    @api.onchange('product_template_ids')
    def _onchange_product_template_ids(self):
        """Update product variants when templates are selected"""
        if self.product_template_ids:
            variants = self.product_template_ids.mapped('product_variant_ids')
            # hide the product cat... here !
            self.product_ids = [(6, 0, variants.ids)]

    def action_preview(self):
        """Generate preview of price changes"""
        self.ensure_one()
        self._validate_inputs()
        
        # Clear existing preview lines
        self.preview_lines.unlink()
        
        preview_lines = []
        for product in self.product_ids:
            old_price = product.list_price
            new_price = self._calculate_new_price(product, old_price)
            
            markup_percent = 0
            if product.standard_price > 0:
                markup_percent = ((new_price - product.standard_price) / product.standard_price) * 100
            
            # Validate margin limits if enabled
            if self.check_margin_limits:
                self._validate_margin_limits(product, new_price)
            
            preview_lines.append((0, 0, {
                'product_id': product.id,
                'old_price': old_price,
                'new_price': new_price,
                'price_difference': new_price - old_price,
                'markup_percent': markup_percent,
                'margin_check_passed': self._check_margin_limits(product, new_price),
            }))
        
        self.preview_lines = preview_lines
        self.show_preview = True
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'product.price.update.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
            'context': self.env.context,
        }

    def action_update_prices(self):
        """Apply price updates to selected products"""
        self.ensure_one()
        self._validate_inputs()
        
        updated_products = []
        errors = []
        
        for product in self.product_ids:
            try:
                old_price = product.list_price
                new_price = self._calculate_new_price(product, old_price)
                
                # Validate margin limits if enabled
                if self.check_margin_limits:
                    self._validate_margin_limits(product, new_price)
                
                # Update the price
                product.write({'list_price': new_price})
                
                # Clear the 'needs_price_update' flag
                if product.product_tmpl_id.needs_price_update:
                    product.product_tmpl_id.write({'needs_price_update': False})

                # Create history record as sudo but record the real user in `updated_by`.
                self.env['product.price.history'].sudo().create({
                    'product_id': product.id,
                    'product_template_id': product.product_tmpl_id.id,
                    'old_price': old_price,
                    'new_price': new_price,
                    'reason': self.reason,
                    'update_type': 'bulk',
                    'updated_by': self.env.user.id,
                })

                
                updated_products.append(product.name)
                
            except Exception as e:
                errors.append(f"{product.name}: {str(e)}")
                _logger.error(f"Error updating price for {product.name}: {str(e)}")
        
        # Show results
        message = f"Successfully updated {len(updated_products)} products."
        if errors:
            message += f"\n\nErrors encountered:\n" + "\n".join(errors)
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Price Update Complete',
                'message': message,
                'type': 'success' if not errors else 'warning',
                'sticky': True,
            }
        }

    def _calculate_new_price(self, product, old_price):
        """Calculate new price based on update type"""
        if self.update_type == 'fixed':
            return old_price + self.fixed_value
        elif self.update_type == 'percentage':
            return old_price * (1 + self.percentage_value / 100)
        elif self.update_type == 'direct':
            return self.direct_value
        elif self.update_type == 'margin':
            if product.standard_price > 0:
                return product.standard_price / (1 - self.margin_percent / 100)
            else:
                raise UserError(f"Product {product.name} has no cost price set for margin calculation")
        # 'category_markup' option removed — use fixed/percentage/direct/margin only
        else:
            return old_price

    def _validate_inputs(self):
        """Validate wizard inputs"""
        if not self.product_ids:
            raise UserError("Please select at least one product to update.")
        
        if self.update_type == 'fixed' and self.fixed_value == 0:
            raise UserError("Please enter a fixed amount value.")
        elif self.update_type == 'percentage' and self.percentage_value == 0:
            raise UserError("Please enter a percentage value.")
        elif self.update_type == 'direct' and self.direct_value <= 0:
            raise UserError("Please enter a valid direct price value.")
        elif self.update_type == 'margin' and (self.margin_percent <= 0 or self.margin_percent >= 100):
            raise UserError("Please enter a valid margin percentage (0-100).")

    def _validate_margin_limits(self, product, new_price):
        """Validate new price against margin limits"""
        if not self._check_margin_limits(product, new_price):
            if product.standard_price > 0:
                current_margin = ((new_price - product.standard_price) / new_price) * 100
                raise ValidationError(
                    f"Product {product.name}: New price violates margin limits. "
                    f"Current margin: {current_margin:.2f}%, "
                    f"Allowed: {product.min_margin_percent:.2f}% - {product.max_margin_percent:.2f}%"
                )

    def _check_margin_limits(self, product, new_price):
        """Check if new price respects margin limits"""
        if not (product.min_margin_percent or product.max_margin_percent):
            return True
        
        if product.standard_price <= 0:
            return True
        
        margin = ((new_price - product.standard_price) / new_price) * 100
        
        if product.min_margin_percent and margin < product.min_margin_percent:
            return False
        if product.max_margin_percent and margin > product.max_margin_percent:
            return False
        
        return True

    # --- LIVE PREVIEW ON CHANGE ---
    @api.onchange(
        'product_ids', 'product_template_ids', 'category_ids',
        'fixed_value', 'percentage_value', 'direct_value', 'margin_percent',
        'apply_to_variants', 'check_margin_limits'
    )
    def _onchange_live_preview(self):
        # Only update preview_lines, do not touch selection fields!
        if self.product_ids or self.product_template_ids or self.category_ids :
            try:
                self.action_preview()
            except Exception as e:
                _logger.warning(f"Live preview error: {e}")

    # --- ALWAYS SHOW PREVIEW TAB ---
    # Remove or ignore any logic that sets show_preview to False after preview


class ProductPriceUpdatePreview(models.TransientModel):
    _name = 'product.price.update.preview'
    _description = 'Price Update Preview Line'

    wizard_id = fields.Many2one(
        'product.price.update.wizard',
        string='Wizard',
        ondelete='cascade'
    )
    product_id = fields.Many2one(
        'product.product',
        string='Product',
        required=True
    )
    
    product_description = fields.Text(
        string='Product Description',
        related='product_id.description_sale'
    )
    product_group_id = fields.Many2one(
        'product.group',
        string='Product Group',
        related='product_id.product_group_id'
    )
    
    old_price = fields.Float(
        string='Current Selling Price',
        digits='Product Price'
    )
    new_price = fields.Float(
        string='New Selling Price',
        digits='Product Price'
    )
    price_difference = fields.Float(
        string='Difference',
        digits='Product Price'
    )
    
    markup_percent = fields.Float(
        string='Markup %',
        digits=(16, 2),
        help='Markup percentage over cost price'
    )
    
    margin_check_passed = fields.Boolean(
        string='Margin OK',
        default=True
    )
    
    currency_id = fields.Many2one(
        'res.currency',
        related='product_id.currency_id'
    )
    
    order_history_count = fields.Integer(
        string='Order History',
        compute='_compute_order_history_count'
    )
    
    @api.depends('product_id')
    def _compute_order_history_count(self):
        for line in self:
            if line.product_id:
                # Count sale order lines for this product
                order_lines = self.env['sale.order.line'].search([
                    ('product_id', '=', line.product_id.id),
                    ('order_id.state', 'in', ['sale', 'done'])
                ])
                line.order_history_count = len(order_lines)
            else:
                line.order_history_count = 0
    
    def action_view_order_history(self):
        """View order history for this product"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Order History - {self.product_id.name}',
            'res_model': 'sale.order.line',
            'view_mode': 'tree,form',
            'domain': [
                ('product_id', '=', self.product_id.id),
                ('order_id.state', 'in', ['sale', 'done'])
            ],
            'context': {'default_product_id': self.product_id.id}
        }
