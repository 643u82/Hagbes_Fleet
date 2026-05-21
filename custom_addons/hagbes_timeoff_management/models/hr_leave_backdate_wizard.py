from odoo import models, fields, api
from odoo.exceptions import ValidationError
from datetime import datetime, time, timedelta, date
import pytz
class HrLeaveBackdateWizard(models.TransientModel):
    _name = 'hr.leave.backdate.wizard'
    _description = 'Backdate Leave Wizard'

    employee_id = fields.Many2one(
        'hr.employee',
        string="Employee",
        required=True,
        domain=lambda self: self._get_employee_domain()
    )
    holiday_status_id = fields.Many2one('hr.leave.type', string="Leave Type", required=True)
    request_unit_half = fields.Boolean('Half Day', readonly=False)
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
        domain=[('res_model', '=', 'hr.leave.backdate.wizard')]
    )

    # Computed field for UI-friendly display in form
    supported_attachment_ids = fields.Many2many(
        'ir.attachment',
        string="Attach File",
        compute='_compute_supported_attachment_ids',
        inverse='_inverse_supported_attachment_ids'
    )

    # Count of attachments (optional, for display in view)
    supported_attachment_ids_count = fields.Integer(
        compute='_compute_supported_attachment_ids'
    )

    @api.constrains('request_date_from')
    def _check_backdate_request(self):
        """Prevent requesting leave for a past date (before today)."""
        for leave in self:
            if leave.request_date_from:
                # Compare only the date part
                if leave.request_date_from.date() > date.today():
                    raise ValidationError("You can request leave only for a past dates.")
    @api.depends('attachment_ids')
    def _compute_supported_attachment_ids(self):
        for record in self:
            record.supported_attachment_ids = record.attachment_ids
            record.supported_attachment_ids_count = len(record.attachment_ids)

    def _inverse_supported_attachment_ids(self):
        for record in self:
            record.attachment_ids = record.supported_attachment_ids

    def _get_employee_domain(self):
        """Return employees in the same branch as the logged-in employee,
           but exclude the logged-in employee from the domain."""

        user = self.env.user
        logged_emp = user.employee_id

        if not logged_emp:
            return []  # No employee record → no filtering

        return [
            ('branch_id', '=', logged_emp.branch_id.id),
            ('id', '!=', logged_emp.id)  # exclude logged-in employee
        ]

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        user_tz = self.env.user.tz or 'UTC'
        local_tz = pytz.timezone(user_tz)

        # Current local datetime
        now_local = datetime.now(local_tz)
        weekday = now_local.weekday()  # 0=Mon ... 5=Sat

        # Default start/end time
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
    @api.onchange('request_unit_half')
    def _onchange_half_day(self):
        """Adjust dates and period when half-day is selected/deselected"""
        if self.request_unit_half:
            self.number_of_days = 0.5
            self.request_date_to = self.request_date_from
            if not self.request_date_from_period:
                self.request_date_from_period = 'am'  # ✅ Use 'am', not 'morning'
        else:
            self.request_date_from_period = False
            self.number_of_days = 1.0

    from datetime import datetime, time, timedelta

    @api.depends('request_date_from', 'request_date_to', 'request_unit_half', 'request_date_from_period')
    def _compute_number_of_days(self):
        """Compute number of days for the wizard, including half-day support"""
        WORK_START_MORNING = time(8, 0)
        WORK_END_MORNING = time(12, 0)
        WORK_START_AFTERNOON = time(13, 0)
        WORK_END_AFTERNOON = time(17, 0)

        def round_half_day(value):
            return round(value * 2) / 2

        for wizard in self:
            if not wizard.request_date_from or not wizard.request_date_to:
                wizard.number_of_days = 0.0
                continue

            # If half-day checkbox is selected, always 0.5
            if wizard.request_unit_half:
                wizard.number_of_days = 0.5
                return

            # Otherwise calculate full duration
            total_days = 0.0
            start = wizard.request_date_from
            end = wizard.request_date_to
            current_day = start.date()

            while current_day <= end.date():
                # Saturday → always full day
                if current_day.weekday() == 5:
                    total_days += 1.0
                    current_day += timedelta(days=1)
                    continue

                # Default working hours
                day_start_dt = datetime.combine(current_day, WORK_START_MORNING)
                day_end_dt = datetime.combine(current_day, WORK_END_AFTERNOON)

                # Adjust for first and last day
                if current_day == start.date():
                    day_start_dt = start
                if current_day == end.date():
                    day_end_dt = end

                # Compute morning and afternoon blocks
                day_total = 0.0
                blocks = [
                    (WORK_START_MORNING, WORK_END_MORNING),
                    (WORK_START_AFTERNOON, WORK_END_AFTERNOON)
                ]
                for block_start, block_end in blocks:
                    block_start_dt = datetime.combine(current_day, block_start)
                    block_end_dt = datetime.combine(current_day, block_end)

                    latest_start = max(day_start_dt, block_start_dt)
                    earliest_end = min(day_end_dt, block_end_dt)
                    overlap_seconds = (earliest_end - latest_start).total_seconds()

                    if overlap_seconds >= (block_end_dt - block_start_dt).total_seconds():
                        day_total = 1.0
                        break
                    elif overlap_seconds > 0:
                        day_total += 0.5

                total_days += day_total
                current_day += timedelta(days=1)

            wizard.number_of_days = round_half_day(total_days)

    @api.constrains('request_date_from', 'request_date_to', 'request_unit_half')
    def _check_half_day_on_saturday_wizard(self):
        Leave = self.env['hr.leave']
        for wizard in self:
            if wizard.request_unit_half:
                temp_leave = Leave.new({
                    'request_date_from': wizard.request_date_from,
                    'request_unit_half': wizard.request_unit_half,
                })
                temp_leave._check_half_day_on_saturday()

    def action_submit(self):
        """Create hr.leave record for backdated leave"""
        Leave = self.env['hr.leave'].sudo()
        current_employee = self.env.user.employee_id
        if not current_employee:
            raise ValidationError("You must have an Employee record linked to your user to create backdated leave.")

        for wizard in self:
            leave_vals = {
                'employee_id': wizard.employee_id.id,
                'holiday_status_id': wizard.holiday_status_id.id,
                'request_date_from': wizard.request_date_from,
                'request_date_to': wizard.request_date_to,
                'name': wizard.reason or 'Backdate Leave',
                'is_backdate': True,
                'requested_by_id': current_employee.id,
                'request_unit_half': wizard.request_unit_half,
                'request_date_from_period': wizard.request_date_from_period,

            }
            leave = Leave.create(leave_vals)
            leave.sudo().write({
                'user_id': self.env.uid,
            })
            if wizard.attachment_ids:
                leave.message_post(attachment_ids=wizard.attachment_ids.ids)

        return self._open_success_message_wizard("Backdated Request created successfully!")

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