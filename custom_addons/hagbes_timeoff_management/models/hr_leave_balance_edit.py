from odoo import models, fields, api, _
from odoo.exceptions import ValidationError,UserError
class HrLeaveBalanceEdit(models.Model):
    _name = "hr.leave.balance.edit"
    _description = "Editable Leave Balance"

    employee_id = fields.Many2one('hr.employee', string="Employee")
    leave_type = fields.Many2one("hr.leave.type", string="Time Off Type")
    year_2_balance = fields.Float(string="Year 2 Balance")
    year_1_balance = fields.Float(string="Year 1 Balance")
    current_year_balance = fields.Float(string="Current Year Balance")
    total_balance = fields.Float(string="Total Balance")
    gained_through_allocation = fields.Float(string="Gained Through Approved Allocation")
    number_of_days = fields.Float(string="Number of Days")

    @api.model
    def fetch_data(self):
        self.env.cr.execute("""
                SELECT employee_id, leave_type, year_2_balance, year_1_balance,
                       current_year_balance, total_balance, gained_through_allocation,
                       number_of_days
                FROM hr_leave_employee_type_report
            """)
        rows = self.env.cr.dictfetchall()
        records = []
        for row in rows:
            records.append((0, 0, row))
        return records
    def write(self, vals):
        res = super().write(vals)
        for rec in self:
            allocation = self.env['hr.leave.allocation'].search([
                ('employee_id', '=', rec.employee_id.id),
                ('holiday_status_id', '=', rec.leave_type.id)
            ])
            allocation.write({
                'year_2_balance': rec.year_2_balance,
                'year_1_balance': rec.year_1_balance,
                'current_year_balance': rec.current_year_balance,
            })
        return res
