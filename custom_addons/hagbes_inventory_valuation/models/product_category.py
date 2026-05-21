from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError

class ProductCategory(models.Model):
    _inherit = 'product.category'

    property_cost_method = fields.Selection([
        ('standard', 'Standard Price'),
        ('fifo', 'First In First Out (FIFO)'),
        ('average', 'Average Cost (AVCO)')
    ], string='Costing Method', 
       default='standard', 
       required=True,
       company_dependent=True,
       help="Standard Price: The cost price is manually updated on the product form.\nFIFO: The cost price is automatically updated based on the first in first out method.\nAverage Cost: The cost price is automatically updated based on the average cost method.")
    
    property_valuation = fields.Selection([
        ('manual_periodic', 'Manual'),
        ('real_time', 'Automated')
    ], string='Inventory Valuation', 
       default='manual_periodic', 
       required=True,
       company_dependent=True,
       help="Manual: Stock valuation is done manually\nAutomated: Stock moves generate accounting entries automatically")
    
    property_account_creditor_price_difference_categ = fields.Many2one(
        'account.account',
        string='Price Difference Account',
        company_dependent=True,
        domain="[('deprecated', '=', False)]",
        help="Account used for price differences when receiving products at different prices than standard cost"
    )
    
 
    property_account_income_categ_id = fields.Many2one(
        'account.account',
        string='Income Account',
        company_dependent=True,
        domain="[('deprecated', '=', False)]",
        help="Account used for income from this product category"
    )
    
    property_account_expense_categ_id = fields.Many2one(
        'account.account',
        string='Expense Account',
        company_dependent=True,
        domain="[('deprecated', '=', False)]",
        help="Account used for expenses from this product category"
    )
    

    removal_strategy_id = fields.Many2one(
        'product.removal',
        string='Force Removal Strategy',
        help="Defines the default method to select the lot/serial numbers when products are taken out of the stock"
    )

    property_stock_valuation_account_id = fields.Many2one(
        'account.account',
        string='Stock Valuation Account',
        company_dependent=True,
        domain="[('deprecated', '=', False)]",
        help="Account used for stock valuation entries. This account will hold the value of your stock."
    )
    
    property_stock_journal = fields.Many2one(
        'account.journal',
        string='Stock Journal',
        company_dependent=True,
        domain="[('type', '=', 'general')]",
        help="Journal used for stock valuation entries"
    )
    
    property_stock_account_input_categ_id = fields.Many2one(
        'account.account',
        string='Stock Input Account',
        company_dependent=True,
        domain="[('deprecated', '=', False)]",
        help="Account used for stock input (when receiving products)"
    )
    
    property_stock_account_output_categ_id = fields.Many2one(
        'account.account',
        string='Stock Output Account',
        company_dependent=True,
        domain="[('deprecated', '=', False)]",
        help="Account used for stock output (when delivering products)"
    )
    
    use_location_accounts = fields.Boolean(
        string='Set other input/output accounts on specific locations',
        default=False,
        help="Enable different stock accounts per location"
    )
    
    @api.constrains('property_valuation', 'property_stock_valuation_account_id')
    def _check_valuation_account(self):
        """Validate that automated valuation has required accounts"""
        for category in self:
            if category.property_valuation == 'real_time':
                if not category.property_stock_valuation_account_id:
                    raise ValidationError(_('Stock Valuation Account is required when using Automated valuation for category "%s".') % category.name)
                if not category.property_stock_journal:
                    raise ValidationError(_('Stock Journal is required when using Automated valuation for category "%s".') % category.name)
    
    @api.onchange('property_valuation')
    def _onchange_property_valuation(self):
        """Set default accounts when switching to automated"""
        if self.property_valuation == 'real_time':
            if not self.property_stock_journal:
                journal = self.env['account.journal'].search([
                    ('type', '=', 'general'),
                    ('code', '=', 'STJ')
                ], limit=1)
                if journal:
                    self.property_stock_journal = journal
    
    def get_product_accounts(self, fiscal_pos=None):
        """Get all product accounts including stock accounts"""
        accounts = {}
        
      
        if hasattr(super(), 'get_product_accounts'):
            accounts = super().get_product_accounts(fiscal_pos)
        
      
        accounts.update({
            'stock_input': self.property_stock_account_input_categ_id,
            'stock_output': self.property_stock_account_output_categ_id,
            'stock_valuation': self.property_stock_valuation_account_id,
            'price_diff': self.property_account_creditor_price_difference_categ,
            'stock_journal': self.property_stock_journal,
        })
        
        return accounts
    
    def _get_stock_accounts(self):
        """Get stock accounts for this category"""
        return {
            'stock_input_account': self.property_stock_account_input_categ_id,
            'stock_output_account': self.property_stock_account_output_categ_id,
            'stock_valuation_account': self.property_stock_valuation_account_id,
            'price_diff_account': self.property_account_creditor_price_difference_categ,
            'stock_journal': self.property_stock_journal,
        }
