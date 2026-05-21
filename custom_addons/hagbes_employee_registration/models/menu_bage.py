from odoo import models

class IrUiMenu(models.Model):
    _inherit = 'ir.ui.menu'

    def _set_menu_counter(self):
        res = super()._set_menu_counter()
        # Attach counter to your retirement menu
        retirement_menu = self.env.ref('hagbes_employee_registration.retirement_menu', raise_if_not_found=False)
        if retirement_menu:
            res[retirement_menu.id] = self.env['employee.retirement'].search_count([])
        return res
