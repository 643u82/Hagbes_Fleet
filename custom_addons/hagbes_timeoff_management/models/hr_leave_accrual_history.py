from odoo import models, fields

class HrLeaveAccrualHistory(models.Model):
    _name = 'hr.leave.accrual.history'
    _description = 'Leave Accrual History'

    employee_id = fields.Many2one('hr.employee', string='Employee', required=True)
    allocation_id = fields.Many2one('hr.leave.allocation', string='Leave Allocation', required=True)

    year_2_balance = fields.Float(string='Year -2 Balance', default=0.0)
    year_1_balance = fields.Float(string='Year -1 Balance', default=0.0)
    current_year_balance = fields.Float(string='Current Year Balance', default=0.0)

    added_this_month = fields.Float(string='Added This Month', default=0.0)
    total_balance = fields.Float(string='Total Balance', default=0.0)

    accrual_date = fields.Date(string='Accrual Date', required=True)
    note= fields.Text(string='Note')
    active = fields.Boolean(default=True)