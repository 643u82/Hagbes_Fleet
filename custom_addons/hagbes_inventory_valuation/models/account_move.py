from odoo import models, fields

class AccountMove(models.Model):
    _inherit = 'account.move'
    
    stock_move_id = fields.Many2one(
        'stock.move',
        string='Stock Move',
        help='Stock move that generated this accounting entry'
    )
    
    is_stock_valuation_entry = fields.Boolean(
        string='Stock Valuation Entry',
        default=False,
        help='This entry was created for stock valuation'
    )
