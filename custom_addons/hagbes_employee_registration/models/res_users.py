from odoo import models, fields, api

class ResUsers(models.Model):
    _inherit = 'res.users'

    allowed_branch_ids = fields.Many2many(
        'account.analytic.account',
        string="Allowed Branches",
        domain=lambda self: [('id', 'in', self._get_branch_ids_from_jobs())],
    )

    default_branch_id = fields.Many2one(
        'account.analytic.account',
        string="Default Branch",
        domain=lambda self: [('id', 'in', self._get_branch_ids_from_jobs())],
    )

    def _get_branch_ids_from_jobs(self):
        branch_ids = self.env['hr.job'].search([]).mapped('analytic_account_id.id')
        return branch_ids if branch_ids else [False]  # return [False] to avoid empty domain issues
