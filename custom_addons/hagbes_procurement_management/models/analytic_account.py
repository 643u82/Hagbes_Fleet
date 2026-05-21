from odoo import models, fields, api, _

class AccountAnalyticAccount(models.Model):
    _inherit = 'account.analytic.account'

    # Branch Classification
    is_branch = fields.Boolean(
        string='Is Branch',
        default=False,
        help="Mark this analytic account as a branch for foreign procurement tracking."
    )

    # Branch Details
    branch_code = fields.Char(
        string='Branch Code',
        help='Unique code for the branch'
    )

    branch_manager_id = fields.Many2one(
        'res.users',
        string='Branch Manager',
        help='Manager responsible for this branch'
    )

    # Location Information
    branch_address = fields.Text(string='Branch Address')
    
    branch_city = fields.Char(string='City')
    
    branch_country_id = fields.Many2one(
        'res.country',
        string='Country'
    )

    # Contact Information
    branch_phone = fields.Char(string='Phone')
    branch_email = fields.Char(string='Email')

    # Foreign Procurement Statistics
    foreign_purchase_count = fields.Integer(
        compute='_compute_foreign_procurement_stats',
        string='Foreign Purchases'
    )

    total_foreign_procurement_amount = fields.Monetary(
        compute='_compute_foreign_procurement_stats',
        string='Total Foreign Procurement',
        currency_field='currency_id'
    )

    active_payment_requests = fields.Integer(
        compute='_compute_foreign_procurement_stats',
        string='Active Payment Requests'
    )

    @api.depends('is_branch')
    def _compute_foreign_procurement_stats(self):
        for branch in self:
            if branch.is_branch:
                # Foreign Purchase Orders
                foreign_pos = self.env['purchase.order'].search([
                    ('branch_id', '=', branch.id),
                    ('order_type', '=', 'foreign')
                ])
                branch.foreign_purchase_count = len(foreign_pos)
                branch.total_foreign_procurement_amount = sum(po.amount_total for po in foreign_pos)

                # Active Payment Requests
                active_requests = self.env['foreign.payment.request'].search([
                    ('branch_id', '=', branch.id),
                    ('state', 'not in', ['paid', 'rejected', 'cancelled'])
                ])
                branch.active_payment_requests = len(active_requests)
            else:
                branch.foreign_purchase_count = 0
                branch.total_foreign_procurement_amount = 0
                branch.active_payment_requests = 0

    def action_view_foreign_purchases(self):
        return {
            'name': _('Foreign Purchase Orders'),
            'type': 'ir.actions.act_window',
            'res_model': 'purchase.order',
            'view_mode': 'tree,form',
            'domain': [('branch_id', '=', self.id), ('order_type', '=', 'foreign')],
            'context': {'default_branch_id': self.id}
        }

    def action_view_payment_requests(self):
        return {
            'name': _('Payment Requests'),
            'type': 'ir.actions.act_window',
            'res_model': 'foreign.payment.request',
            'view_mode': 'tree,form',
            'domain': [('branch_id', '=', self.id)],
            'context': {'default_branch_id': self.id}
        }
