from odoo import models, fields

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'
    
    group_stock_valuation_automatic = fields.Boolean(
        string='Automatic Stock Valuation',
        implied_group='stock_account.group_inventory_valuation',
        help="Enable automatic stock valuation with accounting integration"
    )
    
    default_stock_valuation = fields.Selection([
        ('manual_periodic', 'Manual'),
        ('real_time', 'Automated')
    ], string='Default Inventory Valuation',
       default='manual_periodic',
       config_parameter='hagbes_inventory_valuation.default_stock_valuation',
       help="Default valuation method for new product categories")
