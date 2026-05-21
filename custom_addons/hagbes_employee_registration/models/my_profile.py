from odoo import models, api

class ResUsers(models.Model):
    _inherit = 'res.users'

    @api.model
    def create(self, vals):
        user = super().create(vals)

        admin_group = self.env.ref('base.group_erp_manager')
        hr_group = self.env.ref('hr.group_hr_user')
        profile_group = self.env.ref('your_module_name.group_my_profile_user')

        # Assign profile group only if user is not admin or HR
        if not user.has_group('base.group_erp_manager') and not user.has_group('hr.group_hr_user'):
            user.groups_id = [(4, profile_group.id)]

        return user
