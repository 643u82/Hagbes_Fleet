from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError

class EmployeeClearance(models.Model):
    _name = 'employee.clearance'
    _description = 'Employee Clearance'

    name = fields.Char(string='Clearance Name', required=True)
    employee_id = fields.Many2one('hr.employee', string='Employee', required=True)
    clearance_date = fields.Date(string='Clearance Date', default=fields.Date.context_today)
    status = fields.Selection([
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected')
    ], string='Status', default='pending')

    