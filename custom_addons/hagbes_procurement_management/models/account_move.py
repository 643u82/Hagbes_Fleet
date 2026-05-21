from odoo import models, fields, api, _

class AccountMove(models.Model):
    _inherit = 'account.move'

    
    expected_currency_rate = fields.Float(string='Expected Currency Rate')

    foreign_payment_request_id = fields.Many2one(
        'foreign.payment.request',
        string='Foreign Payment Request',
        help='Related foreign payment request'
    )

    lc_id = fields.Many2one(
        'foreign.lc',
        string='Letter of Credit',
        help='Related letter of credit'
    )
    
    foreign_bank_process_id = fields.Many2one(
        'foreign.bank.process',
        string='Foreign Bank Process',
        help='Related foreign bank process'
    )

    is_foreign_procurement = fields.Boolean(
        string='Is Foreign Procurement',
        compute='_compute_is_foreign_procurement',
        store=True
    )

    # Exchange Rate Information
    foreign_exchange_rate = fields.Float(
        string='Foreign Exchange Rate',
        digits=(12, 6),
        help='Exchange rate used for foreign currency conversion'
    )

    foreign_exchange_difference = fields.Monetary(
        string='Exchange Rate Difference',
        currency_field='company_currency_id',
        help='Difference due to exchange rate fluctuation'
    )

    @api.depends('foreign_payment_request_id', 'lc_id', 'foreign_bank_process_id')
    def _compute_is_foreign_procurement(self):
        for move in self:
            move.is_foreign_procurement = bool(
                move.foreign_payment_request_id or 
                move.lc_id or 
                move.foreign_bank_process_id
            )

    def action_view_foreign_payment_request(self):
        if self.foreign_payment_request_id:
            return {
                'name': _('Foreign Payment Request'),
                'type': 'ir.actions.act_window',
                'res_model': 'foreign.payment.request',
                'res_id': self.foreign_payment_request_id.id,
                'view_mode': 'form',
                'target': 'current',
            }

    def action_view_lc(self):
        if self.lc_id:
            return {
                'name': _('Letter of Credit'),
                'type': 'ir.actions.act_window',
                'res_model': 'foreign.lc',
                'res_id': self.lc_id.id,
                'view_mode': 'form',
                'target': 'current',
            }
    
    def action_view_bank_process(self):
        if self.foreign_bank_process_id:
            return {
                'name': _('Foreign Bank Process'),
                'type': 'ir.actions.act_window',
                'res_model': 'foreign.bank.process',
                'res_id': self.foreign_bank_process_id.id,
                'view_mode': 'form',
                'target': 'current',
            }
    def refresh_invoice_currency_rate(self):
  
         return True


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    # Foreign Procurement Tracking
    foreign_payment_request_line_id = fields.Many2one(
        'foreign.payment.request.line',
        string='Payment Request Line',
        help='Related payment request line'
    )

    # Landed Cost Allocation
    is_landed_cost = fields.Boolean(
        string='Is Landed Cost',
        help='Indicates if this line represents landed costs'
    )

    landed_cost_type = fields.Selection([
        ('freight', 'Freight'),
        ('insurance', 'Insurance'),
        ('customs_duty', 'Customs Duty'),
        ('clearing_charges', 'Clearing Charges'),
        ('other', 'Other'),
    ], string='Landed Cost Type')


class AccountAnalyticAccount(models.Model):
    _inherit = 'account.analytic.account'

    # This field marks an analytic account as a branch.
    is_branch = fields.Boolean(string='Is Branch', default=False,
                               help="Mark this analytic account as a branch.")