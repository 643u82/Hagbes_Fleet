from odoo import models, fields

class HrLeaveExpiryHistory(models.Model):
    _name = 'hr.leave.expiry.history'
    _description = 'Expired Leave History'

    employee_id = fields.Many2one('hr.employee', string='Employee', required=True)
    allocation_id = fields.Many2one('hr.leave.allocation', string='Leave Allocation', required=True)

    expired_year = fields.Integer(string='Year Expired', required=True)  # e.g., 2023
    expired_balance = fields.Float(string='Expired Balance', default=0.0)

    expiry_date = fields.Date(string='Expiry Date', required=True)
    active = fields.Boolean(default=True)