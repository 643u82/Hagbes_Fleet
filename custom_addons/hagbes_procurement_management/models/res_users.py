from odoo import models, fields

class ResUsers(models.Model):
    _inherit = 'res.users'

    allowed_branch_ids = fields.Many2many(
        'account.analytic.account',
        string='Allowed Branches',
        domain="[('plan_id.name', '=', 'Branch')]"
    )

