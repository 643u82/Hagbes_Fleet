from odoo import models, fields

class ResUsers(models.Model):
    _inherit = 'res.users'

    must_change_password = fields.Boolean(
        string="Must Change Password", 
        default=True
    )
