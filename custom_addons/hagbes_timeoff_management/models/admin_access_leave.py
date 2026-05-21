from odoo import models, fields, api, _
from odoo.exceptions import ValidationError,UserError,AccessError
from datetime import datetime, timedelta, time, date
import pytz
import logging
_logger = logging.getLogger(__name__)
from odoo.tools.misc import format_date
from collections import defaultdict

class HrLeaveAdminWizard(models.TransientModel):
    _name = 'hr.leave.admin.wizard'
    _description = 'Admin Leave Request Wizard'

    employee_id = fields.Many2one(
        'hr.employee',
        string="Employee",
        required=True,
        domain=lambda self: self._get_employee_domain()
    )

    leave_balance_year_2 = fields.Float(string="Year -2 Balance", compute="_compute_admin_balances")
    leave_balance_year_1 = fields.Float(string="Year -1 Balance", compute="_compute_admin_balances")
    current_year_balance = fields.Float(string="Current Year Balance", compute="_compute_admin_balances")
    total_leave_balance = fields.Float(string="Total Balance", compute="_compute_admin_balances")

    admin_request_id = fields.Many2one('res.users', string='Admin Requester', readonly=True)

    holiday_status_id = fields.Many2one('hr.leave.type', string="Leave Type", required=True)
    request_unit_half = fields.Boolean('Half Day')
    request_date_from = fields.Datetime(string="Start Date", required=True)
    request_date_to = fields.Datetime(string="End Date", required=True)
    request_date_from_period = fields.Selection(
        selection=[('am', 'Morning'), ('pm', 'Afternoon')],
        string="Date Period Start",
        default='am',
    )
    number_of_days = fields.Float(string="Number of Days", compute="_compute_number_of_days", store=True)
    reason = fields.Text(string="Reason")
    attachment_ids = fields.One2many(
        'ir.attachment',
        'res_id',
        string="Attachments",
        domain=[('res_model', '=', 'hr.leave.admin.wizard')]
    )

    supported_attachment_ids = fields.Many2many(
        'ir.attachment',
        string="Attach File",
        compute='_compute_supported_attachment_ids',
    )

    # Count of attachments (optional, for display in view)
    supported_attachment_ids_count = fields.Integer(
        compute='_compute_supported_attachment_ids'
    )

    resource_calendar_id = fields.Many2one('resource.calendar', compute='_compute_resource_calendar_id', store=True,
                                         readonly=False, copy=False)

    @api.depends('employee_id')
    def _compute_admin_balances(self):
        for wizard in self:
            if not wizard.employee_id:
                wizard.leave_balance_year_2 = 0
                wizard.leave_balance_year_1 = 0
                wizard.current_year_balance = 0
                wizard.total_leave_balance = 0
                continue

            # Create a temporary hr.leave record and reuse the logic
            temp_leave = wizard.env['hr.leave'].new({
                'employee_id': wizard.employee_id.id,
            })
            temp_leave._compute_leave_balances()

            wizard.leave_balance_year_2 = temp_leave.leave_balance_year_2
            wizard.leave_balance_year_1 = temp_leave.leave_balance_year_1
            wizard.current_year_balance = temp_leave.current_year_balance
            wizard.total_leave_balance = temp_leave.total_leave_balance

    @api.model
    def fields_get(self, allfields=None, attributes=None):
        res = super(HrLeaveAdminWizard, self).fields_get(allfields, attributes)
        current_year = fields.Date.context_today(self).year
        if 'leave_balance_year_2' in res:
            res['leave_balance_year_2']['string'] = f"{current_year - 2} Balance"
        if 'leave_balance_year_1' in res:
            res['leave_balance_year_1']['string'] = f"{current_year - 1} Balance"
        if 'current_year_balance' in res:
            res['current_year_balance']['string'] = f"{current_year} Balance"
        if 'total_leave_balance' in res:
            res['total_leave_balance']['string'] = "Total Balance"
        return res

    @api.depends('employee_id')
    def _compute_resource_calendar_id(self):
        employees_by_dates = defaultdict(lambda: self.env['hr.employee'])
        for leave in self:
            if leave.employee_id and leave.request_date_from:
                employees_by_dates[leave.request_date_from] += leave.employee_id
        calendar_by_dates = {date_from: employees._get_calendars(date_from) for date_from, employees in
                             employees_by_dates.items()}
        for leave in self:
            calendar = False
            if leave.employee_id and leave.request_date_from:
                calendar = calendar_by_dates[leave.request_date_from][leave.employee_id.id]
            leave.resource_calendar_id = calendar or self.env.company.resource_calendar_id
    @api.model
    def default_get(self, fields_list):
        """Autofill default start and end date based on local timezone and working hours"""
        res = super().default_get(fields_list)

        user_tz = self.env.user.tz or 'UTC'
        local_tz = pytz.timezone(user_tz)
        now_local = datetime.now(local_tz)
        weekday = now_local.weekday()  # 0=Monday ... 5=Saturday

        # Default working hours
        start_time = time(8, 0)
        end_time = time(12, 30) if weekday == 5 else time(17, 0)

        start_local_naive = datetime.combine(now_local.date(), start_time)
        end_local_naive = datetime.combine(now_local.date(), end_time)

        # Convert to UTC
        start_utc = local_tz.localize(start_local_naive).astimezone(pytz.UTC)
        end_utc = local_tz.localize(end_local_naive).astimezone(pytz.UTC)

        res['request_date_from'] = start_utc.replace(tzinfo=None)
        res['request_date_to'] = end_utc.replace(tzinfo=None)

        return res

    @api.depends('request_date_from', 'request_date_to', 'request_unit_half', 'employee_id', 'holiday_status_id')
    def _compute_number_of_days(self):
        LeaveModel = self.env['hr.leave']
        for wizard in self:
            # Prepare temporary hr.leave record (not created yet)
            temp_leave = LeaveModel.new({
                'employee_id': wizard.employee_id.id,
                'holiday_status_id': wizard.holiday_status_id.id,
                'request_date_from': wizard.request_date_from,
                'request_date_to': wizard.request_date_to,
                'request_unit_half': wizard.request_unit_half,
            })
            # Call original _get_durations
            durations = temp_leave._get_durations()
            wizard.number_of_days = durations.get(temp_leave.id, (0.0, 0.0))[0]

    def _get_employee_domain(self):
        """Return all employees if the user is HR/Admin, else employees in the same branch excluding self."""
        user = self.env.user
        logged_emp = user.employee_id

        # Check if the user is admin/HR (you can adjust the group)
        if user.has_group('base.group_system'):
            return []  # No domain restriction → show all employees

        # If user has no linked employee, return empty
        if not logged_emp:
            return []

        # Restrict to same branch and exclude self
        return [
            ('branch_id', '=', logged_emp.branch_id.id),
            ('id', '!=', logged_emp.id)
        ]

    def action_submit(self):
        """Create leave on behalf of employee"""
        Leave = self.env['hr.leave'].sudo()
        admin_user = self.env.user
        current_employee = self.env.user.employee_id
        if not current_employee:
            raise ValidationError("You must have an Employee record linked to your user to create leave.")

        for wizard in self:
            if not wizard.employee_id:
                raise ValidationError("Please select an employee.")
            leave_vals = {
                'employee_id': wizard.employee_id.id,  # leave belongs to employee
                'holiday_status_id': wizard.holiday_status_id.id,
                'request_date_from': wizard.request_date_from,
                'request_date_to': wizard.request_date_to,
                'name': wizard.reason or 'Leave requested by Others',
                'request_unit_half': wizard.request_unit_half,
                'request_date_from_period': wizard.request_date_from_period,
                'user_id': wizard.employee_id.user_id.id or False,  # employee is owner
                'admin_request_id': admin_user.id,  # hidden audit
                'requested_by_uid': wizard.employee_id.user_id.id or False,
                'requested_by_id': current_employee.id
            }
            leave = Leave.with_context(admin_wizard=True).sudo().create(leave_vals)

            if wizard.attachment_ids:
                leave.message_post(attachment_ids=wizard.attachment_ids.ids)
            leave = leave.with_user(leave.user_id)
            leave.action_submit()

        return self._open_success_message_wizard("Leave Request created successfully!")
    def _open_success_message_wizard(self, message):
        return {
            'name': 'Success',
            'type': 'ir.actions.act_window',
            'res_model': 'success.message.wizard',
            'view_mode': 'form',
            'view_id': self.env.ref('hagbes_timeoff_management.view_success_message_wizard_form').id,
            'target': 'new',
            'context': {'default_message': message},
        }