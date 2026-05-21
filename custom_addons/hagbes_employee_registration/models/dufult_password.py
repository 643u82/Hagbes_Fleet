from odoo import models, api, SUPERUSER_ID

class ResUsers(models.Model):
    _inherit = 'res.users'

    @api.model
    def create(self, vals):
        password = vals.pop('password', None)
        user = super().create(vals)

        # Safely assign password after creation
        if not password:
            password = '12345'
        user.sudo().write({'password': password})

        return user
