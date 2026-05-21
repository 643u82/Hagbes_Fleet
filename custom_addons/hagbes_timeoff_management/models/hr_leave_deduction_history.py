from odoo import models, fields

class HrLeaveDeductionHistory(models.Model):
    _name = 'hr.leave.deduction.history'
    _description = 'Leave Deduction History'
    _order = 'deducted_on desc'
    _rec_name = 'leave_id'

    leave_id = fields.Many2one(
        'hr.leave',
        string='Leave Request',
        required=True,
        ondelete='cascade'
    )
    employee_id = fields.Many2one(
        'hr.employee',
        string='Employee',
        required=True
    )
    allocation_id = fields.Many2one(
        'hr.leave.allocation',
        string='Leave Allocation',
        required=True
    )
    deducted_days = fields.Float(
        string='Deducted Days',
        required=True
    )
    deducted_on = fields.Datetime(
        string='Deducted On',
        required=True,
        default=fields.Datetime.now
    )

    # --- Balances before deduction ---
    year_2_before = fields.Float(string='Year-2 Before')
    year_1_before = fields.Float(string='Year-1 Before')
    current_before = fields.Float(string='Current Year Before')
    total_before = fields.Float(string='Total Before')

    # --- Balances after deduction ---
    year_2_after = fields.Float(string='Year-2 After')
    year_1_after = fields.Float(string='Year-1 After')
    current_after = fields.Float(string='Current Year After')
    total_after = fields.Float(string='Total After')
    active = fields.Boolean(default=True)