from odoo import models, fields, api, _
from odoo.exceptions import UserError

class StockMove(models.Model):
    _inherit = 'stock.move'
    
    def _is_accounting_enabled(self):
        """Check if accounting is enabled for this move"""
        self.ensure_one()
        return (
            self.product_id.categ_id.property_valuation == 'real_time' and
            self.product_id.type == 'product' and
            self.state == 'done'
        )
    
    def _get_accounting_data_for_valuation(self):
        """Get accounting data for stock valuation"""
        self.ensure_one()
        
        if not self._is_accounting_enabled():
            return {}
        
        # Get accounts from category
        accounts = self.product_id.categ_id._get_stock_accounts()
        
        # Check for location-specific accounts
        if self.location_id.use_custom_accounts:
            location_accounts = self.location_id.get_stock_accounts()
            if location_accounts.get('stock_output_account'):
                accounts['stock_output_account'] = location_accounts['stock_output_account']
                
        if self.location_dest_id.use_custom_accounts:
            location_accounts = self.location_dest_id.get_stock_accounts()
            if location_accounts.get('stock_input_account'):
                accounts['stock_input_account'] = location_accounts['stock_input_account']
        
        return {
            'stock_input_account': accounts.get('stock_input_account'),
            'stock_output_account': accounts.get('stock_output_account'),
            'stock_valuation_account': accounts.get('stock_valuation_account'),
            'price_diff_account': accounts.get('price_diff_account'),
            'stock_journal': accounts.get('stock_journal'),
        }
    
    def _create_stock_valuation_entries(self):
        """Create accounting entries for stock valuation"""
        moves_to_account = self.filtered(lambda m: m._is_accounting_enabled())
        
        for move in moves_to_account:
            accounting_data = move._get_accounting_data_for_valuation()
            
            if not accounting_data.get('stock_journal'):
                continue
                
            # Create journal entry
            move_vals = move._prepare_stock_move_vals(accounting_data)
            if move_vals:
                account_move = self.env['account.move'].create(move_vals)
                account_move.action_post()
    
    def _prepare_stock_move_vals(self, accounting_data):
        """Prepare values for stock move accounting entry"""
        self.ensure_one()
        
        if not accounting_data.get('stock_valuation_account') or not accounting_data.get('stock_journal'):
            return False
        
        # Calculate move value
        move_value = self.product_qty * self.product_id.standard_price
        
        # Determine if this is incoming or outgoing
        is_incoming = self.location_dest_id.usage == 'internal' and self.location_id.usage != 'internal'
        is_outgoing = self.location_id.usage == 'internal' and self.location_dest_id.usage != 'internal'
        
        if not (is_incoming or is_outgoing):
            return False
        
        line_vals = []
        
        if is_incoming:
            # Debit stock valuation account
            line_vals.append({
                'name': f'Stock In: {self.product_id.name}',
                'account_id': accounting_data['stock_valuation_account'].id,
                'debit': move_value,
                'credit': 0,
                'product_id': self.product_id.id,
                'quantity': self.product_qty,
            })
            # Credit input account or expense account
            credit_account = accounting_data.get('stock_input_account') or self.product_id.categ_id.property_account_expense_categ_id
            if credit_account:
                line_vals.append({
                    'name': f'Stock In: {self.product_id.name}',
                    'account_id': credit_account.id,
                    'debit': 0,
                    'credit': move_value,
                    'product_id': self.product_id.id,
                    'quantity': self.product_qty,
                })
        
        elif is_outgoing:
            # Credit stock valuation account
            line_vals.append({
                'name': f'Stock Out: {self.product_id.name}',
                'account_id': accounting_data['stock_valuation_account'].id,
                'debit': 0,
                'credit': move_value,
                'product_id': self.product_id.id,
                'quantity': self.product_qty,
            })
            # Debit output account or income account
            debit_account = accounting_data.get('stock_output_account') or self.product_id.categ_id.property_account_income_categ_id
            if debit_account:
                line_vals.append({
                    'name': f'Stock Out: {self.product_id.name}',
                    'account_id': debit_account.id,
                    'debit': move_value,
                    'credit': 0,
                    'product_id': self.product_id.id,
                    'quantity': self.product_qty,
                })
        
        if not line_vals:
            return False
        
        return {
            'journal_id': accounting_data['stock_journal'].id,
            'date': self.date,
            'ref': f'Stock Move: {self.name}',
            'move_type': 'entry',
            'line_ids': [(0, 0, vals) for vals in line_vals],
        }
    
    def _action_done(self, cancel_backorder=False):
        """Override to create accounting entries"""
        result = super()._action_done(cancel_backorder=cancel_backorder)
        
        # Create stock valuation entries
        self._create_stock_valuation_entries()
        
        return result
