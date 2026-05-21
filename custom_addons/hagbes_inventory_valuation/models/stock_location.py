from odoo import models, fields, api

class StockLocation(models.Model):
    _inherit = 'stock.location'
    
    # Location-specific stock accounts
    valuation_in_account_id = fields.Many2one(
        'account.account',
        string='Stock Valuation Account (Incoming)',
        domain="[('deprecated', '=', False)]",
        help="Account used for incoming stock valuation at this location. Overrides category settings."
    )
    
    valuation_out_account_id = fields.Many2one(
        'account.account',
        string='Stock Valuation Account (Outgoing)',
        domain="[('deprecated', '=', False)]",
        help="Account used for outgoing stock valuation at this location. Overrides category settings."
    )
    
    stock_input_account_id = fields.Many2one(
        'account.account',
        string='Stock Input Account',
        domain="[('deprecated', '=', False)]",
        help="Account used for stock input at this location"
    )
    
    stock_output_account_id = fields.Many2one(
        'account.account',
        string='Stock Output Account',
        domain="[('deprecated', '=', False)]",
        help="Account used for stock output at this location"
    )
    
    use_custom_accounts = fields.Boolean(
        string='Use Custom Accounts',
        default=False,
        help="Use location-specific accounts instead of category defaults"
    )
    
    def get_stock_accounts(self, product_category=None):
        """Get stock accounts for this location"""
        self.ensure_one()
        accounts = {}
        
        if self.use_custom_accounts:
            accounts = {
                'stock_input_account': self.stock_input_account_id,
                'stock_output_account': self.stock_output_account_id,
                'valuation_in_account': self.valuation_in_account_id,
                'valuation_out_account': self.valuation_out_account_id,
            }
        elif product_category:
            accounts = product_category._get_stock_accounts()
            
        return accounts
