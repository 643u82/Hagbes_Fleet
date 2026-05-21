from odoo import models, fields, api

class ProductTemplate(models.Model):
    _inherit = 'product.template'
    
    @api.depends('categ_id.property_valuation')
    def _compute_valuation(self):
        """Compute valuation method from category"""
        for product in self:
            product.valuation = product.categ_id.property_valuation or 'manual_periodic'
    
    valuation = fields.Selection([
        ('manual_periodic', 'Manual'),
        ('real_time', 'Automated')
    ], string='Inventory Valuation',
       compute='_compute_valuation',
       store=True,
       help="Inventory valuation method inherited from product category")
    
    @api.depends('categ_id.property_stock_valuation_account_id')
    def _compute_stock_valuation_account(self):
        """Compute stock valuation account from category"""
        for product in self:
            product.stock_valuation_account_id = product.categ_id.property_stock_valuation_account_id
    
    stock_valuation_account_id = fields.Many2one(
        'account.account',
        string='Stock Valuation Account',
        compute='_compute_stock_valuation_account',
        store=True,
        help="Account used for stock valuation (inherited from category)"
    )
    
    def get_product_accounts(self, fiscal_pos=None):
        """Get product accounts including stock accounts"""
        accounts = super().get_product_accounts(fiscal_pos) if hasattr(super(), 'get_product_accounts') else {}
        category_accounts = self.categ_id.get_product_accounts(fiscal_pos)
        accounts.update(category_accounts)
        return accounts
