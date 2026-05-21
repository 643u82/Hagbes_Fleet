from odoo import models, fields, api

class EmployeeTermination(models.Model):
    _name = 'employee.termination'
    _description = 'Employee Termination'
    _order = 'termination_date desc'

    name = fields.Char(string="Termination Ref", required=True, default="New", copy=False, readonly=True)
    employee_id = fields.Many2one('hr.employee', string='Employee', required=True)
    termination_date = fields.Date(string='Termination Date', required=True)
    reason = fields.Text(string='Reason')
    termination_type = fields.Selection([
        ('shelf', 'On Shelf'),
        ('deadfile', 'Deadfile')
    ], string='Record Status', required=True, default='shelf')

    notes = fields.Text(string='Additional Notes')

    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('employee.termination') or 'New'
        return super().create(vals)
