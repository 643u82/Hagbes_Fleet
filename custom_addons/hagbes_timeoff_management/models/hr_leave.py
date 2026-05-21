from odoo import models, fields, api, _
from odoo.exceptions import ValidationError,UserError,AccessError
from datetime import datetime, timedelta, time, date
import pytz
import logging
_logger = logging.getLogger(__name__)
from odoo.tools.misc import format_date


class HolidaysRequest(models.Model):
    _inherit = 'hr.leave'

    is_backdate = fields.Boolean(string="Is Backdate", default=False)
    requested_by_id = fields.Many2one('hr.employee', string="Requested By", readonly=True, tracking=True)
    requested_by_uid = fields.Many2one(
        'res.users',
        string="Requested By",
        readonly=True,
        tracking=True,
        default=lambda self: self.env.user
    )

    request_balance_type = fields.Selection(
        [('within_balance', 'Within Balance'),
         ('exceeds_balance', 'Exceeds Balance'),
         ('no_balance', 'No Balance')],
        string="Leave Request Type",
        compute='_compute_request_balance_type',
        store=True
    )
    active = fields.Boolean(default=True)
    request_date_from = fields.Datetime(string="Start DateTime", required=True)
    request_date_to = fields.Datetime(string="End DateTime", required=True)
    approval_request_id = fields.Many2one('approval.request', string="Approval Request", readonly=True)
    step_progress = fields.Html(string="Approval Progress", compute='_compute_step_progress')
    state = fields.Selection(selection_add=[
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected')
    ], string='Status',tracking=True)
    deduct_from_salary_days = fields.Float(string="Days to Deduct from Salary")
    can_approve = fields.Boolean(
        string="Can Approve", compute="_compute_can_approve", store=False
    )
    employee_branch_id = fields.Many2one(
        'account.analytic.account',
        string="Employee Branch",
        related='employee_id.branch_id',
        store=True,
        readonly=True,
    )

    leave_balance_year_2 = fields.Float(
        string="Year -2 Balance",
        compute="_compute_leave_balances"
    )
    leave_balance_year_1 = fields.Float(
        string="Year -1 Balance",
        compute="_compute_leave_balances"
    )
    current_year_balance = fields.Float(
        string="Current Year Balance",
        compute="_compute_leave_balances"
    )
    total_leave_balance = fields.Float(
        string="Total Balance",
        compute="_compute_leave_balances"
    )

    leave_balance_labels = fields.Char(
        string="Leave Year Labels",
        compute="_compute_leave_labels",
        store=False
    )
    admin_request_id = fields.Many2one('res.users', string='Admin Requester', readonly=True)


    @api.depends('employee_id')
    def _compute_leave_balances(self):
        Allocation = self.env['hr.leave.allocation'].sudo()
        today = fields.Date.context_today(self)
        current_year = today.year
        year_1 = current_year - 1
        year_2 = current_year - 2

        for record in self:
            # default zeros
            year2_balance = 0.0
            year1_balance = 0.0
            current_balance = 0.0

            if not record.employee_id:
                record.leave_balance_year_2 = 0.0
                record.leave_balance_year_1 = 0.0
                record.current_year_balance = 0.0
                record.total_leave_balance = 0.0
                continue

            # Search validated (or relevant) allocations for this employee
            allocations = Allocation.search([
                ('employee_id', '=', record.employee_id.id),
                ('state', 'in', ['validate', 'done']),  # adapt if you use 'validate' only
            ])

            for alloc in allocations:
                # 1) If allocation has explicit per-year fields (custom), prefer them
                y2 = getattr(alloc, 'year_2_balance', None)
                y1 = getattr(alloc, 'year_1_balance', None)
                cy = getattr(alloc, 'current_year_balance', None)
                if y2 is not None or y1 is not None or cy is not None:
                    # Some modules store per-year balances on the allocation
                    if y2:
                        year2_balance += float(y2)
                    if y1:
                        year1_balance += float(y1)
                    if cy:
                        current_balance += float(cy)
                    # skip the date-based counting for this allocation
                    continue

                # 2) Otherwise fall back to date-based bucket by year
                # allocation may have date_from (Date/Datetime) or we use create_date
                alloc_date = getattr(alloc, 'date_from', False) or getattr(alloc, 'create_date', False)
                alloc_year = None
                if alloc_date:
                    # alloc_date may be a datetime or date or string, normalize safely
                    try:
                        if hasattr(alloc_date, 'year'):
                            alloc_year = alloc_date.year
                        else:
                            # if it's string, try to parse (rare)
                            alloc_year = fields.Date.from_string(str(alloc_date)).year
                    except Exception:
                        alloc_year = None

                # amount to add: prefer numeric number_of_days fields
                amount = None
                if hasattr(alloc, 'number_of_days') and alloc.number_of_days is not None:
                    amount = float(alloc.number_of_days)
                elif hasattr(alloc, 'number_of_days_display') and alloc.number_of_days_display is not None:
                    amount = float(alloc.number_of_days_display)
                else:
                    # fallback: maybe allocations use remaining_leaves or other field
                    # try common field names, otherwise skip
                    for candidate in ('remaining_leaves', 'number_of_days_display', 'number_of_days'):
                        if hasattr(alloc, candidate) and getattr(alloc, candidate) is not None:
                            amount = float(getattr(alloc, candidate))
                            break

                if amount is None:
                    # nothing meaningful to add from this allocation
                    continue

                # If alloc_year unknown, try to use allocation's holiday_status_id year? else put to current
                if alloc_year is None:
                    alloc_year = current_year

                if alloc_year == year_2:
                    year2_balance += amount
                elif alloc_year == year_1:
                    year1_balance += amount
                elif alloc_year == current_year:
                    current_balance += amount
                else:
                    # If allocation from other years (older), you may decide where to put it.
                    # Here we ignore older than year_2; or you could put older into year_2 bucket:
                    if alloc_year < year_2:
                        year2_balance += amount

            # assign computed values
            record.leave_balance_year_2 = year2_balance
            record.leave_balance_year_1 = year1_balance
            record.current_year_balance = current_balance
            record.total_leave_balance = year2_balance + year1_balance + current_balance

    @api.model
    def fields_get(self, allfields=None, attributes=None):
        res = super(HolidaysRequest, self).fields_get(allfields, attributes)
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


    def action_intermediate_approval(self):
        for leave in self:
            leave.state = 'pending'  # your custom intermediate state
            leave.message_post(
                body=f"Leave moved to {leave.state} by {self.env.user.name}"
            )
        return True
    @api.depends("approval_request_id", "approval_request_id.approver_ids")
    def _compute_can_approve(self):
        uid = self.env.user.id
        for leave in self:
            leave.approval_request_id._compute_current_approvers()  # Force compute
            approvers = leave.approval_request_id.approver_ids.mapped("id")
            leave.can_approve = (
                    leave.state not in ("approved", "rejected") and uid in approvers
            )
            _logger.debug(
                f"[DEBUG CAN_APPROVE] Leave {leave.id} - State: {leave.state}, Approvers: {approvers}, UID: {uid}, Can Approve? {leave.can_approve}")

    def action_open_update_wizard(self, *args, **kwargs):
        return {
            'name': 'Update Leave Data',
            'type': 'ir.actions.act_window',
            'res_model': 'leave.update.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'active_id': self.id},
        }
    @api.depends('employee_id', 'holiday_status_id', 'number_of_days')
    def _compute_request_balance_type(self):
        for leave in self:
            # Get validated allocation for this employee and leave type
            allocation = self.env['hr.leave.allocation'].search([
                ('employee_id', '=', leave.employee_id.id),
                ('holiday_status_id', '=', leave.holiday_status_id.id),
                ('state', '=', 'validate')
            ], limit=1)

            if not allocation or allocation.number_of_days <= 0:
                leave.request_balance_type = 'no_balance'
            elif leave.number_of_days <= allocation.number_of_days:
                leave.request_balance_type = 'within_balance'
            else:
                leave.request_balance_type = 'exceeds_balance'


    @api.constrains('request_date_from', 'request_date_to', 'request_unit_half')
    def _check_half_day_on_saturday(self):
        for leave in self:
            if leave.request_unit_half:
                if leave.request_date_from and leave.request_date_from.weekday() == 5:  # Saturday
                    raise ValidationError(_("You cannot request half-day leave on Saturdays."))

    @api.onchange('request_date_from', 'request_date_to')
    def _onchange_request_times(self):
        allowed_times = {
            'weekdays': [time(8, 0), time(12, 0), time(13, 0), time(17, 0)],
            'saturday': [time(8, 0), time(12, 30)]
        }

        now = datetime.now()

        for leave in self:
            if not leave.request_date_from or not leave.request_date_to:
                return

            start_time = leave.request_date_from.time()
            end_time = leave.request_date_to.time()

            start_day = leave.request_date_from.weekday()
            end_day = leave.request_date_to.weekday()

            # Prevent selecting past dates
            if self.env.context.get('admin_wizard'):
                return

            if leave.request_date_from.date() < now.date():
                leave.request_date_from = False
                return {
                    'warning': {
                        'title': "Invalid Date",
                        'message': "Leave cannot start in the past."
                    }
                }

    def _get_durations(self, check_leave_type=True, resource_calendar=None):
        def round_half_day(value):
            return round(value * 2) / 2

        result = {}
        WORK_START_MORNING = time(8, 0)
        WORK_END_MORNING = time(12, 0)
        WORK_START_AFTERNOON = time(13, 0)
        WORK_END_AFTERNOON = time(17, 0)

        for leave in self:
            start = leave.request_date_from or leave.date_from
            end = leave.request_date_to or leave.date_to
            calendar = resource_calendar or leave.resource_calendar_id

            if not start or not end:
                result[leave.id] = (0.0, 0.0)
                continue

            total_days = 0.0
            current_day = start.date()

            while current_day <= end.date():
                day_start_dt = datetime.combine(current_day, WORK_START_MORNING)
                day_end_dt = datetime.combine(current_day, WORK_END_AFTERNOON)

                # Saturday → always full day
                if current_day.weekday() == 5:
                    total_days += 1.0
                    current_day += timedelta(days=1)
                    continue

                # Skip non-working days using calendar
                work_hours = calendar.get_work_hours_count(day_start_dt, day_end_dt,
                                                           compute_leaves=True) if calendar else 8
                if work_hours <= 0:
                    current_day += timedelta(days=1)
                    continue

                # Half-day fixed → only count if working day
                if leave.request_unit_half:
                    total_days += 0.5
                    current_day += timedelta(days=1)
                    continue

                # Determine actual day start/end
                day_start = start if current_day == start.date() else day_start_dt
                day_end = end if current_day == end.date() else day_end_dt

                work_blocks = [
                    (WORK_START_MORNING, WORK_END_MORNING),
                    (WORK_START_AFTERNOON, WORK_END_AFTERNOON)
                ]

                day_total = 0.0
                for block_start, block_end in work_blocks:
                    block_start_dt = datetime.combine(current_day, block_start)
                    block_end_dt = datetime.combine(current_day, block_end)

                    latest_start = max(day_start, block_start_dt)
                    earliest_end = min(day_end, block_end_dt)
                    overlap_seconds = (earliest_end - latest_start).total_seconds()

                    # Original logic preserved
                    if overlap_seconds >= ((block_end_dt - block_start_dt).total_seconds()):
                        day_total = 1.0  # Full day
                        break
                    elif overlap_seconds > 0:
                        day_total += 0.5  # Half day

                total_days += day_total
                current_day += timedelta(days=1)

            result[leave.id] = (round_half_day(total_days), 0.0)

        return result

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)

        user_tz = self.env.user.tz or 'UTC'
        local_tz = pytz.timezone(user_tz)

        now_local = datetime.now(local_tz)
        weekday = now_local.weekday()  # 0=Mon, ..., 5=Sat

        # Default start time
        start_time = time(8, 0)
        # Default end time: half-day or full-day
        end_time = time(12, 30) if weekday == 5 else time(17, 0)

        # Combine with today's date (naive)
        start_local_naive = datetime.combine(now_local.date(), start_time)
        end_local_naive = datetime.combine(now_local.date(), end_time)

        # Localize then convert to UTC
        start_utc = local_tz.localize(start_local_naive).astimezone(pytz.UTC)
        end_utc = local_tz.localize(end_local_naive).astimezone(pytz.UTC)

        res['request_date_from'] = start_utc.replace(tzinfo=None)
        res['request_date_to'] = end_utc.replace(tzinfo=None)

        # If half-day, adjust end to half-day duration (4 hours)
        if res.get('request_unit_half'):
            half_day_end = datetime.combine(now_local.date(), time(12, 0))
            res['request_date_to'] = local_tz.localize(half_day_end).astimezone(pytz.UTC).replace(tzinfo=None)

        return res

    def _check_pending_request(self, employee_id):
        pending = self.search([
            ('employee_id', '=', employee_id),
            ('state', '=', 'pending')
        ], limit=1)

        if pending:
            raise ValidationError(_(
                "You already have a pending leave request. "
                "Please wait for the previous request to be approved or rejected."
            ))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:

            # -------------------------------------------
            # 🚫 VALIDATION: Prevent duplicate pending requests
            # -------------------------------------------
            employee_id = vals.get('employee_id')
            if employee_id:
                pending_exist = self.env['hr.leave'].search_count([
                    ('employee_id', '=', employee_id),
                    ('state', 'in', ['pending', 'confirm', 'draft']),
                ])
                if pending_exist:
                    raise ValidationError(
                        _("You already have a pending leave request. "
                          "Please wait until it is approved or rejected.")
                    )
            # -------------------------------------------

            # Set default requester
            if 'requested_by_id' not in vals or not vals.get('requested_by_id'):
                if vals.get('employee_id'):
                    vals['requested_by_id'] = vals['employee_id']

        # Now proceed with actual creation
        leaves = super().create(vals_list)

        if not self.env.context.get('admin_wizard'):
            leaves.action_submit()  # ← Auto-submit ONLY for normal users

        return leaves

    def _check_validity(self):
        """
        Override default allocation check:
        - Skip validation at request stage
        - Deduction will be handled later at approval step
        """
        # If approval flow is active for this leave type → skip validation
        for leave in self:
            if leave.holiday_status_id.requires_allocation != 'no':
                # Just bypass the original check
                # (do nothing here)
                continue
        return True

    def action_submit(self):
        self.ensure_one()

        flow = self.env['approval.flow'].search([
            ('request_model_id.model', '=', 'hr.leave'),
            ('active', '=', True),
            ('company_id', '=', self.company_id.id)
        ], limit=1)
        if not flow:
            raise UserError("No approval flow defined for Leave!")

        # Get first step
        first_step = self.env['approval.step'].search([
            ('flow_id', '=', flow.id)
        ], order='sequence asc', limit=1)
        if not first_step:
            raise UserError("No steps defined for this approval flow.")

        # Create approval request
        approval_req = self.env['approval.request'].create({
            'flow_id': flow.id,
            'res_model': self._name,
            'module_name': 'leave',
            'res_id': self.id,
            'requested_by': self.create_uid.id,
            'current_step_id': first_step.id,
            'status': 'pending',
        })

        self.write({
            'state': 'pending',  # Use standard Odoo state
            'approval_request_id': approval_req.id
        })

        approval_req.process_action()

        self.message_post(
            body="Leave Request submitted for approval",
            message_type="notification",
            subtype_xmlid="mail.mt_note"
        )
        message = "Leave request submitted successfully!"
        return self._open_success_message_wizard(message)


    def action_approve(self, comment=''):
        self.ensure_one()
        if not self.approval_request_id:
            raise UserError("No approval request linked to this Leave.")

        # Process workflow
        self.approval_request_id.with_context(action_type='approve', comment=comment).process_action()
        self._sync_state_from_approval()
        self.message_post(body=_("Leave Request approved by %s" % self.env.user.name))
        if self.state == 'approved' and self.holiday_status_id.requires_allocation == 'yes':
            total_days_to_deduct = self.number_of_days or 0.0

            # Call allocation method to handle deduction + history
            remaining = self.env['hr.leave.allocation'].sudo().deduct_leave_days(self, total_days_to_deduct)

            # Handle unpaid leave
            self.deduct_from_salary_days = remaining if remaining > 0 else 0.0

            # Final approval
            self._validate_leave_request()
        message = "Leave request approved successfully!"
        return self._open_success_message_wizard(message)

    def _check_approval_update(self, state):
        """Bypass Odoo's default approval security checks because we use a custom approval flow."""
        return True

    def action_reject(self, comment=''):
        self.ensure_one()
        try:
            if not self.approval_request_id:
                raise UserError("No approval request linked to this leave.")

            self.approval_request_id.with_context(
                action_type='reject', comment=comment
            ).process_action()
            self._sync_state_from_approval()
            self.message_post(body=_("Leave Request rejected by %s" % self.env.user.name))

            message = "Leave request rejected."
            return self._open_success_message_wizard(message)

        except (UserError, AccessError) as e:
            return {"success": False, "error": str(e)}

    def _sync_state_from_approval(self):
        if not self.approval_request_id:
            return
        status = self.approval_request_id.status
        if status == 'approved':
            self.state = 'approved'
        elif status == 'rejected':
            self.state = 'rejected'
        elif status == 'pending':
            self.state = 'pending'
        else:
            self.state = 'draft'

    def _compute_step_progress(self):
        for rec in self:
            rec.step_progress = rec.approval_request_id.step_progress if rec.approval_request_id else "<span>No approval steps yet.</span>"

    def write(self, values):
        # Temporarily remove the check by bypassing the original _compute_state validation
        # This completely disables the "already begun" restriction
        # SUDO to fully bypass
        return super(HolidaysRequest, self.sudo()).write(values)

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

    @api.constrains('date_from', 'date_to', 'employee_id')
    def _check_date(self):
            """Only normal leave should be checked for overlap.
               Backdate leave can overlap without restriction.
            """

            for holiday in self:

                # 🔥 Skip overlap validation for backdate leave
                if holiday.is_backdate:
                    continue

                # 🔍 Search for overlapping normal leaves
                overlapping = self.search([
                    ('employee_id', '=', holiday.employee_id.id),
                    ('id', '!=', holiday.id),
                    ('state', 'in', ['pending', 'approved']),  # consider these as conflicts
                    ('date_from', '<', holiday.date_to),
                    ('date_to', '>', holiday.date_from),
                    ('is_backdate', '=', False),  # 🔥 ignore backdate leaves
                ])

                if not overlapping:
                    continue

                # ❌ If conflicts → raise error
                conflicts = []
                for rec in overlapping:
                    conflicts.append(
                        f"{rec.employee_id.name} - "
                        f"from {format_date(self.env, rec.date_from)} to {format_date(self.env, rec.date_to)} "
                        f"- {rec.state.capitalize()}"
                    )

                raise ValidationError(
                    "This leave overlaps with another normal leave:\n" +
                    "\n".join(conflicts)
                )

    @api.constrains('request_date_from', 'request_date_to', 'number_of_days')
    def _check_zero_duration(self):
            for leave in self:
                # Skip if dates not set
                if not leave.request_date_from or not leave.request_date_to:
                    continue

                # When Odoo has calculated number_of_days
                if leave.number_of_days is not None and leave.number_of_days <= 0:
                    raise ValidationError(
                        _("You cannot request 0-day leave. Please choose a valid start and end time.")
                    )



