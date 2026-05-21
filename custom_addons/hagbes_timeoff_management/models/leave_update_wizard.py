from odoo import models, fields, api

class LeaveUpdateWizard(models.TransientModel):
    _name = 'leave.update.wizard'
    _description = 'Update Leave Data Wizard'

    employee_id = fields.Many2one('hr.employee', string='Employee', readonly=True)
    emp_id = fields.Char(string='Employee ID', readonly=True)
    hired_date = fields.Date(string='Hired Date', readonly=True)
    email = fields.Char(string='Work Email', readonly=True)
    job_id = fields.Many2one('hr.job', string='Job Position', readonly=True)
    branch = fields.Char(string='Branch', readonly=True)
    work_phone = fields.Char(string='Phone Number', readonly=True)
    holiday_status_id = fields.Many2one('hr.leave.type', string='Leave Type', readonly=True)
    date_from = fields.Datetime(string='From', readonly=True)
    date_to = fields.Datetime(string='To', readonly=True)
    number_of_days = fields.Float(string='Requested Days', readonly=True)
    allocation_id = fields.Many2one('hr.leave.allocation', string="Allocation Record", readonly=True)

    year_2_balance = fields.Float()
    year_1_balance = fields.Float()
    current_year_balance = fields.Float()
    total_balance = fields.Float(compute="_compute_total_balance", readonly=True)

    deduct_from_salary = fields.Selection(
        [('yes', 'Deduct from Salary'), ('no', "Don't Deduct"), ('annual', 'Deduct from Annual Leave'),],
        string="Salary Deduction", default='annual'
    )
    salary_days_to_deduct = fields.Float(compute="_compute_salary_days", readonly=True)

    @api.model
    def fields_get(self, allfields=None, attributes=None):
        res = super().fields_get(allfields, attributes)
        current_year = fields.Date.context_today(self).year
        if 'year_2_balance' in res:
            res['year_2_balance']['string'] = f"{current_year - 2} Balance"
        if 'year_1_balance' in res:
            res['year_1_balance']['string'] = f"{current_year - 1} Balance"
        if 'current_year_balance' in res:
            res['current_year_balance']['string'] = f"{current_year} Balance"
        return res

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        leave_id = self._context.get('active_id')
        if leave_id:
            leave = self.env['hr.leave'].browse(leave_id)
            emp = leave.employee_id
            res.update({
                'employee_id': emp.id,
                'emp_id': emp.emp_id,
                'hired_date': emp.hired_date,
                'work_phone': emp.work_phone,
                'email': emp.work_email,
                'job_id': emp.job_id.id,
                'branch': emp.job_id.analytic_account_id.name if emp.job_id.analytic_account_id else '',
                'date_from': leave.date_from,
                'date_to': leave.date_to,
                'number_of_days': leave.number_of_days,
                'holiday_status_id': leave.holiday_status_id.id,
            })

            allocation = self.env['hr.leave.allocation'].search([
                ('employee_id', '=', emp.id),
                ('holiday_status_id', '=', leave.holiday_status_id.id),
                ('state', 'in', ['validate', 'done'])
            ], limit=1)
            if allocation:
                res.update({
                    'allocation_id': allocation.id,
                    'year_2_balance': allocation.year_2_balance,
                    'year_1_balance': allocation.year_1_balance,
                    'current_year_balance': allocation.current_year_balance,
                })
        return res

    @api.depends('year_2_balance','year_1_balance','current_year_balance')
    def _compute_total_balance(self):
        for rec in self:
            rec.total_balance = (rec.year_2_balance or 0) + \
                                (rec.year_1_balance or 0) + \
                                (rec.current_year_balance or 0)
            if rec.allocation_id:
                rec.allocation_id.number_of_days = rec.total_balance



    @api.depends('deduct_from_salary', 'number_of_days', 'year_2_balance', 'year_1_balance', 'current_year_balance',
                 'holiday_status_id')
    def _compute_salary_days(self):
        for rec in self:
            # Default to 0
            rec.salary_days_to_deduct = 0.0

            # If no deduction selected, skip calculation
            if rec.deduct_from_salary != 'yes':
                continue

            # Available balance (could be 0 if not allocated)
            available_balance = (rec.year_2_balance or 0) + \
                                (rec.year_1_balance or 0) + \
                                (rec.current_year_balance or 0)

            # Check if the leave type doesn't require allocation
            if rec.holiday_status_id and rec.holiday_status_id.requires_allocation == 'no':
                # This leave type doesn't track allocation, so deduct all days
                rec.salary_days_to_deduct = rec.number_of_days or 0.0
            else:
                # Deduct only excess beyond available balance
                extra_days = (rec.number_of_days or 0) - available_balance
                rec.salary_days_to_deduct = extra_days if extra_days > 0 else 0.0

    def action_update_leave(self):
        """Update hr.leave.allocation and hr.leave based on wizard input."""
        leave = self.env['hr.leave'].browse(self._context.get('active_id'))

        # Update allocation balances
        if self.allocation_id:
            self.allocation_id.write({
                'year_2_balance': self.year_2_balance,
                'year_1_balance': self.year_1_balance,
                'current_year_balance': self.current_year_balance,
                'number_of_days': self.total_balance,
            })

        # Update leave request salary deduction
        if self.deduct_from_salary == 'yes':
            leave.deduct_from_salary_days = leave.number_of_days
        else:
            leave.deduct_from_salary_days = 0

        return {'type': 'ir.actions.act_window_close'}

