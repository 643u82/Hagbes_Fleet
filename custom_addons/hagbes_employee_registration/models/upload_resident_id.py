#adding a field to store resident ID document when registering an employee
from odoo import models, fields

class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    resident_id = fields.Binary(
        string='Resident ID Document',
        groups="hr.group_hr_user",
        attachment=True
    )
    resident_id_filename = fields.Char(string='Resident ID Filename')
# adding dufult password 