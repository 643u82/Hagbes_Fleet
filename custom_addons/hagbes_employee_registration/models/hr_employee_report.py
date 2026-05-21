#reporting the privete data of the employee

from odoo import models,fields, api

class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    def print_private_report(self):
        return self.env.ref('hagbes_employee_registration.private_employee_report_action').report_action(self)


