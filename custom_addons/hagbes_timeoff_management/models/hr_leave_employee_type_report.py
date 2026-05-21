from odoo import api, fields, models, tools, _

class LeaveReport(models.Model):
    _name = "hr.leave.employee.type.report"
    _description = "Time Off Summary / Report"
    _auto = False
    _order = "date_from DESC, employee_id"

    employee_id = fields.Many2one('hr.employee', string="Employee", readonly=True)
    active_employee = fields.Boolean(readonly=True)
    number_of_days = fields.Float('Number of Days ', readonly=True, aggregator="sum")
    number_of_hours = fields.Float('Number of Hours', readonly=True, aggregator="sum")
    department_id = fields.Many2one('hr.department', string='Department', readonly=True)
    leave_type = fields.Many2one("hr.leave.type", string="Time Off Type", readonly=True)
    holiday_status = fields.Selection([
        ('taken', 'Taken'),
        ('left', 'Left'),
        ('planned', 'Planned')
    ])
    state = fields.Selection([
        ('cancel', 'Cancelled'),
        ('confirm', 'To Approve'),
        ('refuse', 'Refused'),
        ('validate1', 'Second Approval'),
        ('validate', 'Approved')
    ], string='Status', readonly=True)
    date_from = fields.Datetime('Start Date', readonly=True)
    date_to = fields.Datetime('End Date', readonly=True)
    company_id = fields.Many2one('res.company', string="Company", readonly=True)

    year_2_balance = fields.Float(readonly=True)
    year_1_balance = fields.Float(readonly=True)
    current_year_balance = fields.Float(readonly=True)
    total_balance = fields.Float(string="Total Balance", readonly=True)
    is_monthly_accrual = fields.Boolean(string="Monthly Accrual", readonly=True)
    gained_through_allocation = fields.Float(string="Gained Through Approved Allocation", readonly=True)
    branch_id = fields.Many2one('account.analytic.account', string="Branch", readonly=True)

    @api.model
    def write(self, vals):
        # Save changes back to hr_leave_allocation if possible
        # Example:
        allocation = self.env['hr.leave.allocation'].search([('id', '=', vals.get('id'))])
        if allocation:
            allocation.write(vals)
        return super(LeaveReport, self).write(vals)
    @api.model
    def fields_get(self, allfields=None, attributes=None):
        res = super(LeaveReport, self).fields_get(allfields, attributes)
        current_year = fields.Date.context_today(self).year
        if 'year_2_balance' in res:
            res['year_2_balance']['string'] = f"{current_year - 2} Balance"
        if 'year_1_balance' in res:
            res['year_1_balance']['string'] = f"{current_year - 1} Balance"
        if 'current_year_balance' in res:
            res['current_year_balance']['string'] = f"{current_year} Balance"
        return res

    @api.model
    def action_time_off_analysis(self):
        tools.drop_view_if_exists(self._cr, 'hr_leave_employee_type_report')
        # Allowed companies for the logged-in user
        allowed_companies = tuple(self.env.user.company_ids.ids)
        if not allowed_companies:
            allowed_companies = (0,)  # safety fallback
        self._cr.execute("""
                CREATE OR REPLACE VIEW hr_leave_employee_type_report AS (
                    SELECT
                        allocation.id AS id,
                        allocation.employee_id,
                        employee.active AS active_employee,

                        -- number_of_days = ONLY accrual allocations (no balances added again)
                        CASE 
                            WHEN allocation.is_monthly_accrual THEN allocation.number_of_days
                            ELSE 0
                        END AS number_of_days,

                        allocation.number_of_hours_display AS number_of_hours,
                        allocation.department_id,
                        allocation.holiday_status_id AS leave_type,
                        job.analytic_account_id AS branch_id,
                        'left' AS holiday_status,
                        allocation.state,
                        allocation.date_from,
                        allocation.date_to,
                        allocation.employee_company_id AS company_id,

                        -- keep year balances directly
                        allocation.year_2_balance,
                        allocation.year_1_balance,
                        allocation.current_year_balance,
                        allocation.is_monthly_accrual,

                        -- gained_through_allocation = non-monthly approved allocations
                        CASE 
                            WHEN NOT allocation.is_monthly_accrual THEN allocation.number_of_days
                            ELSE 0
                        END AS gained_through_allocation,

                        -- total_balance = accrual number_of_days + gained_through_allocation
                        (
                            CASE WHEN allocation.is_monthly_accrual THEN allocation.number_of_days ELSE 0 END
                            +
                            CASE WHEN NOT allocation.is_monthly_accrual THEN allocation.number_of_days ELSE 0 END
                        ) AS total_balance

                    FROM hr_leave_allocation allocation
                    INNER JOIN hr_employee employee ON allocation.employee_id = employee.id
                    LEFT JOIN hr_job job ON employee.job_id = job.id
                    WHERE allocation.state IN ('validate', 'approved')
                    AND allocation.employee_company_id IN %(allowed_companies)s
                )
            """, {'allowed_companies': allowed_companies})

        return {
            'name': _('Time Off Analysis by Employee and Time Off Type'),
            'type': 'ir.actions.act_window',
            'res_model': 'hr.leave.employee.type.report',
            'view_mode': 'pivot,graph',
            'views': [
                (self.env.ref('hagbes_timeoff_management.hr_leave_employee_type_report_pivot').id, 'pivot'),
                (self.env.ref('hagbes_timeoff_management.hr_leave_employee_type_report_graph').id, 'graph'),
            ],
            'target': 'current',
            'context': {},
        }


