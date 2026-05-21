from odoo import models, fields

class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    marriage_certificate = fields.Binary(
        string="Marriage Certificate",
        groups="hr.group_hr_user"
    )
    marriage_certificate_filename = fields.Char(
        string="Certificate Filename",
        groups="hr.group_hr_user"
    )
    children_ids = fields.One2many(
        'employee.children',
        'employee_id',
        string="Children",
        groups="hr.group_hr_user"
    )
    def unlink(self):
        raise KeyError("Deleting employees is not allowed.")

class EmployeeChildren(models.Model):
    _name = 'employee.children'
    _description = 'Employee Children'

    employee_id = fields.Many2one(
        'hr.employee',
        string='Employee',
        required=True,
        ondelete='cascade'
    )
    name = fields.Char(string='Child Name', required=True)
    birth_date = fields.Date(string='Birth Date')
