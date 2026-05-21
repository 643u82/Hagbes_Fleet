from odoo import models, fields, api

class AccountMove(models.Model):
    _inherit = 'account.move'

    branch_id = fields.Many2one(
        'account.analytic.account',
        string='Branch',
        index=True
    )
