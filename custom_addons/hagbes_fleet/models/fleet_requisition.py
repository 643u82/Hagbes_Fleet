# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import AccessError, ValidationError, UserError
import logging

_logger = logging.getLogger(__name__)


class FleetRequisition(models.Model):
    _name = 'fleet.requisition'
    _description = 'Vehicle Requisition Form'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'approval.integration.mixin']
    _order = 'date_of_request desc, id desc'

    def _auto_init(self):
        """Preserve legacy text traveller data before creating the M2O column."""
        cr = self.env.cr
        cr.execute(
            """
            SELECT data_type
              FROM information_schema.columns
             WHERE table_name = %s
               AND column_name = 'traveller'
            """,
            [self._table],
        )
        column = cr.fetchone()
        if column and column[0] not in ('integer', 'bigint'):
            cr.execute(
                """
                UPDATE fleet_requisition
                   SET traveller_names = COALESCE(NULLIF(traveller_names, ''), traveller)
                 WHERE traveller IS NOT NULL
                   AND COALESCE(traveller_names, '') = ''
                """
            )
            legacy_column = 'traveller_legacy'
            cr.execute(
                """
                SELECT 1
                  FROM information_schema.columns
                 WHERE table_name = %s
                   AND column_name = %s
                """,
                [self._table, legacy_column],
            )
            suffix = 1
            while cr.fetchone():
                legacy_column = 'traveller_legacy_%s' % suffix
                cr.execute(
                    """
                    SELECT 1
                      FROM information_schema.columns
                     WHERE table_name = %s
                       AND column_name = %s
                    """,
                    [self._table, legacy_column],
                )
                suffix += 1
            cr.execute(
                'ALTER TABLE "%s" RENAME COLUMN "traveller" TO "%s"'
                % (self._table, legacy_column)
            )
        return super()._auto_init()

    # ─── Identification ───────────────────────────────────────────────────────
    name = fields.Char(
        string='Reference',
        readonly=True,
        copy=False,
        default='New',
        index=True,
    )
    date_of_request = fields.Date(
        string='Date of Request',
        default=fields.Date.today,
        readonly=True,
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    department_id = fields.Many2one(
        'hr.department',
        string='Department',
        default=lambda self: self._get_department_for_user(self.env.user.id),
        readonly=True,
        index=True,
    )

    can_edit_requester = fields.Boolean(compute='_compute_can_edit_requester')

    @api.depends_context('uid')
    def _compute_can_edit_requester(self):
        is_fmo = self.env.user.has_group('hagbes_fleet.group_fmo')
        is_manager = self.env.user.has_group('hagbes_fleet.group_fleet_manager')
        is_admin = self.env.user.has_group('hagbes_fleet.group_fleet_admin') or self.env.user.has_group('base.group_system')
        for record in self:
            record.can_edit_requester = is_fmo or is_manager or is_admin

    def _get_department_for_user(self, user_id):
        if not user_id:
            return self.env['hr.department']
        user = self.env['res.users'].sudo().browse(user_id)
        employee = user.employee_id
        if not employee:
            employee = self.env['hr.employee'].sudo().search([('user_id', '=', user_id)], limit=1)
        return employee.department_id if employee else self.env['hr.department']

    @api.onchange('request_by')
    def _onchange_request_by_department(self):
        for rec in self:
            request_by = rec.request_by

            # FIX: Never call getattr(rec, fname) over all Many2one fields during onchange.
            # Doing so materialises '_unknown' proxy objects that the OWL web client cannot
            # serialise, producing the RPC_ERROR: AttributeError '_unknown' object has no attribute 'id'.

            # FIX: Extract .id safely before use; never pass an ORM recordset to department_id.
            request_by_id = request_by.id if request_by else False
            if not request_by_id:
                rec.department_id = False
            else:
                dept = rec._get_department_for_user(request_by_id)
                # FIX: Always assign integer id or False to Many2one, never an ORM record.
                rec.department_id = dept.id if dept else False


    # Traveler sync methods removed as traveller_ids is now the primary field

    # ─── Trip Details ─────────────────────────────────────────────────────────
    date_from = fields.Datetime(
        string='Date From',
        required=True,
        tracking=True,
        default=fields.Datetime.now,
    )
    date_to = fields.Datetime(
        string='Date To',
        required=True,
        tracking=True,
    )
    purpose = fields.Text(
        string='Purpose',
        required=True,
    )
    traveller_ids = fields.Many2many(
        'res.users',
        'fleet_requisition_traveller_rel',
        'requisition_id',
        'user_id',
        string='Travellers',
        default=lambda self: [(6, 0, [self.env.user.id])],
        tracking=True,
        help='Select travellers from registered users.',
    )

    traveller_count = fields.Integer(
        string='Number of Travellers',
        compute='_compute_traveller_count',
        store=True,
        readonly=True,
    )

    @api.depends('traveller_ids')
    def _compute_traveller_count(self):
        for rec in self:
            rec.traveller_count = len(rec.traveller_ids)
    destination_branch_id = fields.Many2one(
        'account.analytic.account',
        string='Destination (Branch)',
        index=True,
        help='Select a registered company branch as destination.',
    )

    additional_destination = fields.Char(
        string='Additional Destination',
        size=256,
        help='Optional free-form destination for non-branch locations (government offices, customer sites, temporary work areas).',
    )

    @api.onchange('destination_branch_id', 'additional_destination')
    def _onchange_destination_parts_sync_legacy(self):
        """Keep legacy `destination` Char compatible with structured branch+additional inputs."""
        for rec in self:
            parts = []
            if rec.destination_branch_id:
                parts.append(rec.destination_branch_id.name or '')

            if rec.additional_destination:
                parts.append(rec.additional_destination)

            if parts:
                # If both branch and additional are given: "Branch - Additional"
                if rec.destination_branch_id and rec.additional_destination:
                    rec.destination = '%s - %s' % (rec.destination_branch_id.name, rec.additional_destination)
                else:
                    rec.destination = ' '.join([p for p in parts if p]).strip()
            else:
                # Let the user provide legacy destination manually if neither structured field is set.
                rec.destination = rec.destination or False


    # Legacy compatibility field used by existing reports/analytics and trip planning.
    # Kept as Char to avoid breaking existing integrations.
    destination = fields.Char(
        string='Destination',
        required=True,
        size=256,
    )

    request_by = fields.Many2one(
        'res.users',
        string='Requested By',
        default=lambda self: self.env.user,
        required=True,
        tracking=True,
        index=True,
    )

    # ─── Workflow / Stage ─────────────────────────────────────────────────────
    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('submitted', 'Submitted'),
            ('approved', 'Approved'),
            ('assigned', 'Assigned'),
            ('completed', 'Completed'),
            ('rejected', 'Rejected'),
            ('cancelled', 'Cancelled'),
        ],
        string='Status',
        default='draft',
        tracking=True,
        copy=False,
        index=True,
    )

    approved_by = fields.Many2one(
        'res.users',
        string='Approved By',
        readonly=True,
        copy=False,
    )
    approved_date = fields.Datetime(
        string='Approved Date',
        readonly=True,
        copy=False,
    )

    is_dept_manager_approved = fields.Boolean(string='Dept Manager Approved', default=False, copy=False)
    is_team_leader_approved = fields.Boolean(string='Team Leader Approved', default=False, copy=False)

    reject_reason = fields.Text(string='Rejection Reason', copy=False)


    # ─── Department Approval ──────────────────────────────────────────────────
    dept_approved_by = fields.Many2one(
        'res.users',
        string='Dept. Approved By',
        readonly=True,
        copy=False,
    )
    dept_approved_date = fields.Datetime(
        string='Dept. Approval Date',
        readonly=True,
        copy=False,
    )



    # ─── FMO Officer Approval ─────────────────────────────────────────────────
    fmo_approved_by = fields.Many2one(
        'res.users',
        string='FMO Approved By',
        readonly=True,
        copy=False,
    )
    fmo_approved_date = fields.Datetime(
        string='FMO Approval Date',
        readonly=True,
        copy=False,
    )

    # ─── Property Validation ──────────────────────────────────────────────────
    requires_property_validation = fields.Boolean(
        string='Requires Property Validation',
        default=False,
        tracking=True,
        help='Future-proofing field for Asset module integration.'
    )

    # ─── Vehicle Assignment ───────────────────────────────────────────────────
    # Note: Department Managers (group_dept_manager) are deliberately NOT in
    # the groups list below, so these fields are hidden from approvers. The
    # requester (group_fleet_requester) keeps visibility of the assigned
    # vehicle once the request moves past the dept-approval stage.
    vehicle_id = fields.Many2one(
        'hagbes.fleet.vehicle',
        string='Vehicle',
        tracking=True,
        copy=False,
        index=True,
        groups='hagbes_fleet.group_fleet_requester,'
               'hagbes_fleet.group_fmo,'
               'hagbes_fleet.group_fleet_manager,'
               'hagbes_fleet.group_fleet_admin',
    )
    vehicle_plate_number = fields.Char(
        string='Plate Number',
        related='vehicle_id.plate_number',
        readonly=True,
        groups='hagbes_fleet.group_fleet_requester,'
               'hagbes_fleet.group_fmo,'
               'hagbes_fleet.group_fleet_manager,'
               'hagbes_fleet.group_fleet_admin',
    )
    vehicle_driver_name = fields.Char(
        string='Driver',
        related='vehicle_id.driver',
        readonly=True,
        groups='hagbes_fleet.group_fleet_requester,'
               'hagbes_fleet.group_fmo,'
               'hagbes_fleet.group_fleet_manager,'
               'hagbes_fleet.group_fleet_admin',
    )
    assigned_by = fields.Many2one(
        'res.users',
        string='Assigned By',
        readonly=True,
        copy=False,
    )
    assigned_date = fields.Datetime(
        string='Assignment Date',
        readonly=True,
        copy=False,
    )

    # ─── Allocation ───────────────────────────────────────────────────────────
    allocation_id = fields.Many2one(
        'hagbes.fleet.allocation',
        string='Allocation',
        readonly=True,
        copy=False,
        index=True,
    )
    trip_id = fields.Many2one(
        'fleet.trip',
        string='Trip',
        readonly=True,
        copy=False,
    )
    allocated_by = fields.Many2one(
        'res.users',
        string='Allocated By',
        readonly=True,
        copy=False,
    )
    allocated_date = fields.Datetime(
        string='Allocation Date',
        readonly=True,
        copy=False,
    )

    # ─── Rejection Fields ─────────────────────────────────────────────────────
    rejected_by = fields.Many2one(
        'res.users',
        string='Rejected By',
        readonly=True,
        copy=False,
        tracking=True,
    )
    rejected_date = fields.Datetime(
        string='Rejected Date',
        readonly=True,
        copy=False,
        tracking=True,
    )
    rejection_reason = fields.Text(
        string='Rejection Reason',
        readonly=True,
        copy=False,
        tracking=True,
    )

    # ─── Permission Fields (Computed) ─────────────────────────────────────────
    can_submit = fields.Boolean(compute='_compute_permissions')
    can_dept_approve = fields.Boolean(compute='_compute_permissions')
    can_team_leader_approve = fields.Boolean(compute='_compute_permissions')

    can_fmo_approve = fields.Boolean(compute='_compute_permissions')  # FMO dispatch action
    can_fleet_approve = fields.Boolean(compute='_compute_permissions')  # Fleet Officer assign vehicle action
    can_reject = fields.Boolean(compute='_compute_permissions')
    can_allocate = fields.Boolean(compute='_compute_permissions')
    can_cancel = fields.Boolean(compute='_compute_permissions')

    @api.depends('state', 'request_by', 'traveller_ids')
    @api.depends_context('uid')
    def _compute_permissions(self):
        """
        Compute role-based permissions for clean workflow stages.
        """
        user = self.env.user
        is_fmo = user.has_group('hagbes_fleet.group_fmo')
        is_dept_manager = user.has_group('hagbes_fleet.group_dept_manager')
        is_team_leader = user.has_group('hagbes_fleet.group_team_leader')
        is_fleet_manager = user.has_group('hagbes_fleet.group_fleet_manager')
        is_admin = user.has_group('hagbes_fleet.group_fleet_admin') or user.has_group('base.group_system')

        for rec in self:
            # Initialize all permission flags to avoid stale values.
            rec.can_submit = False
            rec.can_cancel = False
            rec.can_dept_approve = False
            rec.can_team_leader_approve = False
            rec.can_fmo_approve = False
            rec.can_fleet_approve = False
            rec.can_reject = False
            rec.can_allocate = False
            rec.can_cancel = False

            # Employee/Requester: Can submit and cancel in draft stage
            if rec.state == 'draft' and (rec.request_by == user or is_fleet_manager or is_admin):
                rec.can_submit = True
                rec.can_cancel = True

            # Department Manager: approve/reject in submitted stage
            if rec.state == 'submitted' and (is_dept_manager or is_admin):
                rec.can_dept_approve = True
                rec.can_reject = True

            # Team Leader: approve/reject in submitted stage
            if rec.state == 'submitted' and (is_team_leader or is_admin):
                rec.can_team_leader_approve = True
                rec.can_reject = True

            # Fleet Officer: assign vehicle after EITHER dept or team leader approval
            if rec.state in ('dept_approved', 'team_leader_approved') and (is_fmo or is_admin):
                rec.can_fleet_approve = True
                rec.can_reject = True

            # FMO: dispatch/assign in assigned stage (can reject before confirm)
            if rec.state == 'assigned' and (is_fmo or is_admin):
                rec.can_reject = True

            # Rejection state: No actions allowed after rejection
            if rec.state == 'rejected':
                rec.can_submit = False
                rec.can_cancel = False
                rec.can_dept_approve = False
                rec.can_team_leader_approve = False
                rec.can_fmo_approve = False
                rec.can_fleet_approve = False
                rec.can_reject = False
                rec.can_allocate = False


    # =========================================================================
    # Computed helpers
    # =========================================================================

    # Traveler name validation constraint removed

    @api.constrains('date_from', 'date_to')
    def _check_dates(self):
        for req in self:
            if req.date_from and req.date_to:
                if req.date_to < req.date_from:
                    raise ValidationError(_('The "Date To" cannot be earlier than the "Date From".'))
                if req.date_from.date() < fields.Date.context_today(req):
                    raise ValidationError(_('The "Date From" cannot be in the past.'))

    @api.constrains('date_from', 'department_id', 'purpose')
    def _check_no_duplicate(self):
        """Prevent duplicate requests: same department + same date + same purpose."""
        for rec in self:
            domain = [
                ('id', '!=', rec.id),
                ('department_id', '=', rec.department_id.id),
                ('date_from', '=', rec.date_from),
                ('purpose', '=ilike', rec.purpose),
                ('state', 'not in', ['rejected', 'cancelled']),
            ]
            duplicate = self.search(domain, limit=1)
            if duplicate:
                raise ValidationError(
                    _('Duplication detected! A request with the same department, date, and purpose already exists (Ref: %s).') % duplicate.name
                )

    # =========================================================================
    # ORM Overrides
    # =========================================================================

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('fleet.requisition') or 'New'

            # Always fix request_by for non-admin requesters
            request_by_id = vals.get('request_by') or self.env.user.id
            if not self.env.su:
                if not self.env.user.has_group('hagbes_fleet.group_fmo') and \
                   not self.env.user.has_group('hagbes_fleet.group_fleet_manager') and \
                   not self.env.user.has_group('base.group_system') and \
                   not self.env.user.has_group('hagbes_fleet.group_fleet_admin'):
                    request_by_id = self.env.user.id
                    vals['request_by'] = request_by_id
            vals.setdefault('traveller_ids', [(6, 0, [request_by_id])])

            # Department is owned by the requester employee/org record.
            department = self._get_department_for_user(request_by_id)
            vals['department_id'] = department.id or False

        recs = super().create(vals_list)
        return recs

    def write(self, vals):
        """Override write to handle department synchronization and security."""
        # Handle department sync when request_by changes
        if 'request_by' in vals and not self.env.context.get('allow_department_sync'):
            department = self._get_department_for_user(vals['request_by'])
            vals['department_id'] = department.id if department else False

        # Allow workflow updates when context flag is set
        if self.env.context.get('allow_workflow'):
            return super().write(vals)

        # Prevent editing after rejection for all users except admins
        for rec in self:
            if rec.state == 'rejected':
                # Allow admins to edit rejected requisitions
                if not self.env.user.has_group('hagbes_fleet.group_fleet_admin') and \
                   not self.env.user.has_group('base.group_system'):
                    # Only allow editing rejection-related fields by Department Managers
                    allowed_fields = {'rejection_reason', 'rejected_by', 'rejected_date'}
                    if not self.env.user.has_group('hagbes_fleet.group_dept_manager') or \
                       not set(vals.keys()).issubset(allowed_fields):
                        raise AccessError(_('Rejected requisitions cannot be edited.'))

        # Field-level restrictions for regular requesters after submission
        if not self.env.su:
            for rec in self:
                # Regular requesters can only edit specific fields after submission
                if rec.state not in ('draft', 'rejected') and \
                   self.env.user.has_group('hagbes_fleet.group_fleet_requester') and \
                   not self.env.user.has_group('hagbes_fleet.group_fmo') and \
                   not self.env.user.has_group('hagbes_fleet.group_fleet_admin'):

                    # Allow only limited field edits for requesters
                    allowed_requester_fields = {
                        'traveller_ids',
                        'purpose',
                        'destination',
                        'destination_branch_id',
                        'additional_destination',
                        'notes',
                    }

                    if not set(vals.keys()).issubset(allowed_requester_fields):
                        raise AccessError(_('You cannot edit core requisition details after submission. Only purpose, destination, and notes can be modified.'))

        res = super().write(vals)
        return res

    def unlink(self):
        for rec in self:
            if rec.state not in ('draft', 'rejected', 'cancelled'):
                if not rec._is_fleet_manager():
                    raise AccessError(_('Only a Fleet Manager can delete a requisition that is in progress.'))
        return super().unlink()

    # =========================================================================
    # Professional Workflow Actions
    # =========================================================================



    def action_approve(self):
        """Approve requisition using OR-based rule: dept manager OR team leader."""
        for rec in self:
            if rec.state != 'submitted':
                raise UserError(_('Only submitted requisitions can be approved.'))

            user = self.env.user
            is_dept_manager = user.has_group('hagbes_fleet.group_dept_manager') or user.has_group('base.group_system') or user.has_group('hagbes_fleet.group_fleet_admin')
            is_team_leader = user.has_group('hagbes_fleet.group_team_leader') or user.has_group('base.group_system') or user.has_group('hagbes_fleet.group_fleet_admin')

            if not (is_dept_manager or is_team_leader):
                raise AccessError(_('Only Department Managers or Team Leaders can approve.'))

            # Prevent double approvals
            if rec.state == 'approved':
                raise UserError(_('This requisition has already been approved.'))

            rec.with_context(allow_workflow=True).write({
                'state': 'approved',
                'approved_by': user.id,
                'approved_date': fields.Datetime.now(),
                'is_dept_manager_approved': bool(is_dept_manager),
                'is_team_leader_approved': bool(is_team_leader),
                # keep legacy fields for backward compatibility, if they exist in DB/views
                'dept_approved_by': user.id if is_dept_manager else False,
                'dept_approved_date': fields.Datetime.now() if is_dept_manager else False,
                'team_leader_approved_by': user.id if is_team_leader else False,
                'team_leader_approved_date': fields.Datetime.now() if is_team_leader else False,
            })
            rec.message_post(body=_('Requisition approved.'))

    def action_reject(self, reason):
        """Reject requisition with mandatory reason."""

        for rec in self:
            # Security & State validation depending on state
            if rec.state == 'submitted':
                if not self.env.user.has_group('hagbes_fleet.group_dept_manager') and \
                   not self.env.user.has_group('hagbes_fleet.group_fleet_admin') and \
                   not self.env.user.has_group('base.group_system'):
                    raise AccessError(_('Only Department Managers can reject requisitions in Submitted state.'))
            elif rec.state in ('dept_approved', 'team_leader_approved'):
                if not self.env.user.has_group('hagbes_fleet.group_team_leader') and \
                   not self.env.user.has_group('hagbes_fleet.group_fleet_admin') and \
                   not self.env.user.has_group('base.group_system') and \
                   not self.env.user.has_group('hagbes_fleet.group_fmo'):
                    raise AccessError(_('Only Team Leaders or Fleet Officers can reject requisitions in Approved state.'))
            else:
                raise UserError(_('Requisitions in state %s cannot be rejected.') % rec.state)
            
            # Reason validation
            if not reason or not reason.strip():
                raise UserError(_('Rejection reason is required.'))
            
            if len(reason.strip()) < 10:
                raise UserError(_('Please provide a more detailed rejection reason (minimum 10 characters).'))
            
            # Process rejection
            rec.with_context(allow_workflow=True).write({
                'state': 'rejected',
                'rejected_by': self.env.user.id,
                'rejected_date': fields.Datetime.now(),
                'rejection_reason': reason.strip(),
            })
            
            # Post chatter message
            chatter_msg = _(
                'Request Rejected\n'
                'Rejected By: %s\n'
                'Reason: %s'
            ) % (self.env.user.name, reason.strip())
            rec.message_post(body=chatter_msg)



    def action_fleet_approve(self):
        """Fleet Officer: Assign vehicle, create allocation and trip, and transition to trip planning."""
        self.ensure_one()
        if self.state != 'approved':
            raise UserError(_('Only approved requisitions can be assigned vehicles.'))

        
        if not self.vehicle_id:
            raise UserError(_('Please select a vehicle to assign to this requisition before confirming.'))

        # Advance the state
        self.with_context(allow_workflow=True).write({'state': 'assigned'})
        self.message_post(body=_('Vehicle assignment initiated.'))

        # Check if an allocation already exists for this requisition
        allocation = self.env['hagbes.fleet.allocation'].search([
            ('request_id', '=', self.id),
            ('state', 'not in', ('completed', 'cancelled')),
        ], limit=1)
        
        if not allocation:
            # Try to find the driver from the vehicle or traveller
            driver_id = False
            if self.vehicle_id and self.vehicle_id.driver:
                # Search for employee by name (case-insensitive)
                driver = self.env['hr.employee'].search([('name', '=ilike', self.vehicle_id.driver.strip())], limit=1)
                if not driver:
                    driver = self.env['hr.employee'].search([('name', 'ilike', self.vehicle_id.driver.strip())], limit=1)
                if driver:
                    driver_id = driver.id
            
            if not driver_id and self.traveller_ids:
                for user in self.traveller_ids:
                    employee = user.employee_id
                    if employee and 'driver' in (employee.job_id.name or '').lower():
                        driver_id = employee.id
                        break

            if not driver_id:
                raise UserError(_('A driver could not be automatically determined. Please ensure the vehicle has a driver set, or one of the travellers is a driver.'))

            # Create the allocation programmatically
            allocation = self.env['hagbes.fleet.allocation'].create({
                'request_id': self.id,
                'vehicle_id': self.vehicle_id.id,
                'driver_id': driver_id,
                'company_id': self.company_id.id,
                'allocation_date': self.date_from or fields.Datetime.now(),
                'return_date': self.date_to,
                'state': 'draft',
            })
            
            # Link back to requisition
            self.with_context(allow_workflow=True).write({
                'allocation_id': allocation.id
            })

        # At this point we have an allocation. Confirm it to create the Trip!
        if allocation.state == 'draft':
            action = allocation.action_assign_vehicle()
            # Ensure we open Trip Planning (no auto-start)
            return action
        elif allocation.trip_id:
            # If already confirmed and trip exists, open the trip in planning context
            return {
                'name': _('Trip Planning'),
                'type': 'ir.actions.act_window',
                'res_model': 'fleet.trip',
                'view_mode': 'form',
                'target': 'current',
                'res_id': allocation.trip_id.id,
            }
        else:
            # Fallback
            return {
                'name': _('Fleet Allocation'),
                'type': 'ir.actions.act_window',
                'res_model': 'hagbes.fleet.allocation',
                'res_id': allocation.id,
                'view_mode': 'form',
                'target': 'current',
            }


    def action_fmo_approve(self):
        """Deprecated: Keep to prevent broken views temporarily."""
        return self.action_fleet_approve()

    # =========================================================================
    # Legacy Workflow Callbacks (from hagbes_approval_workflow)
    # =========================================================================

    def _on_approval_approved(self):
        """Callback when entire approval flow is finished.

        Regression guard:
        - Do NOT move the requisition to state 'assigned' unless the operational chain exists.
        - An allocation must exist and be confirmed (draft -> action_assign_vehicle) so it creates/links a trip.
        """
        for rec in self:
            # Find any operational allocation linked to this requisition.
            allocation = self.env['hagbes.fleet.allocation'].search([
                ('request_id', '=', rec.id),
                ('state', 'in', ('draft', 'assigned', 'in_progress')),
            ], limit=1)

            if not allocation:
                _logger.warning(
                    "Approval approved for requisition %s, but no allocation exists. Keeping requisition state (%s).",
                    rec.id, rec.state
                )
                continue

            # If allocation is still in draft, confirm it (creates/links trip and returns Start Trip action).
            if allocation.state == 'draft':
                allocation.action_assign_vehicle()

            # Reload after action_assign_vehicle side effects.
            allocation = self.env['hagbes.fleet.allocation'].browse(allocation.id)

            # Ensure trip is linked; action_assign_vehicle should create trip if missing.
            if not allocation.trip_id:
                _logger.error(
                    "Allocation %s for requisition %s has no linked trip after confirmation. Keeping requisition state (%s).",
                    allocation.id, rec.id, rec.state
                )
                continue

            # Now it's safe to mark requisition as assigned.
            if rec.state != 'assigned':
                rec.with_context(allow_workflow=True).write({
                    'state': 'assigned',
                    'fmo_approved_by': self.env.user.id,
                    'fmo_approved_date': fields.Datetime.now(),
                })
                rec.message_post(body=_('Request assigned.'))


    def _on_approval_rejected(self):
        """Callback when any step is rejected."""
        for rec in self:
            rec.with_context(allow_workflow=True).write({'state': 'rejected'})

    def _get_approval_request_vals(self):
        self.ensure_one()
        flow = self._get_approval_flow('fleet_requisition')
        return {
            'flow_id': flow.id,
            'res_model': self._name,
            'res_id': self.id,
            'requested_by': self.request_by.id or self.env.user.id,
            'module_name': 'hagbes_fleet',
        }

    def _set_waiting_approval_state(self):
        self.write({'state': 'submitted'})

    def action_submit(self):
        """Requester submits a draft requisition for department approval."""
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_('Only draft requests can be submitted.'))
            
            department = rec.department_id
            if not department:
                raise UserError(_('Your employee profile is not linked to a department.'))
            
            # Use sudo() to allow state transition for users with restricted write access
            # We explicitly check that only the requester or an authorized manager can submit
            if not (rec.request_by == self.env.user or self._is_fleet_manager()):
                raise AccessError(_('You can only submit your own requests.'))

            rec.sudo()._trigger_approval()
            rec.message_post(body=_('Request submitted for approval.'))
            
            # Fix 12: Minimal SMS notification to Department Manager
            if rec.department_id.manager_id.user_id.partner_id.mobile:
                rec._send_approval_sms(rec.department_id.manager_id.user_id.partner_id)

    def _send_approval_sms(self, partner):
        """Send a simple SMS notification for approval."""
        body = _("New Fleet Requisition %s needs your approval.") % self.name
        self.env['sms.api'].sudo()._send_sms(partner.mobile, body)

    def action_resubmit(self):
        """Rejected → Draft: Allow requesters to resubmit after fixing issues."""
        for rec in self:
            if rec.state != 'rejected':
                raise UserError(_('Only rejected requests can be resubmitted.'))
            rec.write({
                'state': 'draft',
                'reject_reason': False,
                'rejection_reason': False,
                'rejected_by': False,
                'rejected_date': False,
            })
            rec.message_post(body=_('Requisition resubmitted.'))

    def action_cancel(self):
        """Cancel a requisition before it reaches operational execution."""
        for rec in self:
            if rec.state in ('assigned', 'dispatched', 'completed'):
                raise UserError(_('You cannot cancel a request in the "%s" stage.') % rec.state)
            if rec.trip_id and rec.trip_id.state not in ('completed', 'cancelled'):
                raise UserError(_('You cannot cancel a requisition with an active trip.'))
            rec.write({'state': 'cancelled'})

    def action_create_allocation(self):
        """FMO Approved → Allocated: Open allocation form with default values."""
        self.ensure_one()
        if self.state != 'assigned':
            raise UserError(_('Only assigned requests can be allocated.'))
        if not self.vehicle_id:
            raise UserError(_('Please assign a vehicle before creating an allocation.'))
            
        return {
            'name': _('Create Allocation'),
            'type': 'ir.actions.act_window',
            'res_model': 'hagbes.fleet.allocation',
            'view_mode': 'form',
            'target': 'current',
            'context': {
                'default_request_id': self.id,
                'default_vehicle_id': self.vehicle_id.id,
                'default_company_id': self.company_id.id,
            }
        }

    def action_complete(self):
        """Deprecated completion action.

        Enterprise refactor: requisition completion is synchronized from
        `hagbes.fleet.allocation` / `fleet.trip` lifecycle.
        """
        raise UserError(_('Completion is managed by the Allocation/Trip lifecycle. Open the related allocation and complete it there.'))

    def _sync_from_allocation_state(self, new_allocation_state, old_requisition_state=None):
        """Synchronize requisition operational status from allocation transitions.

        Controlled mapping only; does not trigger reverse writes.
        """
        self.ensure_one()

        # Centralized state mapping from allocation to requisition
        # This ensures only valid requisition states are written
        # Direct synchronization is dangerous - always map through this dictionary
        allocation_to_requisition_map = {
            'draft': 'assigned',           # Allocation draft means requisition approved but not operational
            'assigned': 'assigned',              # Vehicle assigned to requisition
            'in_progress': 'assigned',         # Trip in progress - requisition remains assigned
            'returned': 'assigned',            # Vehicle returned - requisition still assigned
            'completed': 'completed',           # Trip completed - requisition completed
            'cancelled': 'cancelled',           # Allocation cancelled - requisition cancelled
        }
        target_state = allocation_to_requisition_map.get(new_allocation_state)
        
        # Defensive protection: validate target state exists in requisition selection
        if not target_state:
            _logger.warning(
                'Invalid allocation state mapping: %s -> None. Skipping synchronization for requisition %s',
                new_allocation_state, self.id
            )
            return

        # Validate target state is actually valid for requisition model
        # Use proper ORM approach for field metadata access
        valid_requisition_states = [state[0] for state in self._fields['state'].selection]
        if target_state not in valid_requisition_states:
            _logger.error(
                'CRITICAL: Invalid target state %s for requisition %s. Allocation state was %s.',
                target_state, self.id, new_allocation_state
            )
            return

        # Allow only operational transitions after FMO approval.
        if self.state in ('rejected', 'cancelled', 'completed'):
            _logger.info(
                'Skipping state synchronization for completed requisition %s (current state: %s)',
                self.id, self.state
            )
            return

        if target_state != self.state:
            self.write({'state': target_state})
            self.message_post(
                body=_('Requisition operational state synchronized to %s.') % 
                dict(self._fields['state'].selection).get(target_state, target_state)
            )
            _logger.info(
                'Requisition %s state synchronized: %s -> %s (from allocation state: %s)',
                self.id, self.state, target_state, new_allocation_state
            )


    def action_open_allocation_form(self):
        """FMO Approved → Assigned (operational execution): open allocation form.

        Enterprise rule: `fleet.requisition` owns the business workflow state;
        `hagbes.fleet.allocation` owns vehicle dispatch execution.
        """
        self.ensure_one()
        if self.state != 'assigned':
            raise UserError(_('Only assigned requests can be assigned to an allocation.'))

        # Prevent duplicate operational allocations for the same requisition.
        existing = self.env['hagbes.fleet.allocation'].search([
            ('request_id', '=', self.id),
            ('state', 'in', ['assigned', 'dispatched', 'in_progress']),
        ], limit=1)
        if existing:
            raise UserError(_('An active allocation (%s) already exists for this requisition.') % existing.name)

        ctx = {
            'default_request_id': self.id,
            'default_company_id': self.company_id.id,
            'default_vehicle_id': self.vehicle_id.id if self.vehicle_id else False,
        }

        return {
            'name': _('Fleet Allocation'),
            'type': 'ir.actions.act_window',
            'res_model': 'hagbes.fleet.allocation',
            'view_mode': 'form',
            'target': 'current',
            'context': ctx,
        }

    def action_assign_vehicle(self):
        """Deprecated: kept for backward compatibility.

        Live operational assignment must open `hagbes.fleet.allocation`.
        """
        return self.action_open_allocation_form()

    def action_allocate(self):
        """Deprecated alias for legacy buttons."""
        return self.action_open_allocation_form()


    # Approval Logic Integration
    # =========================================================================

    def action_approve(self):
        """Approve the current step of the approval request with strict state validation."""
        self.ensure_one()
        if self.state in ['assigned', 'dispatched', 'completed', 'rejected', 'cancelled']:
            raise UserError(_('You cannot approve a request that is already %s.') % self.state)
        
        # Find the pending approval request
        request = self.env['approval.request'].sudo().search([
            ('res_model', '=', self._name),
            ('res_id', '=', self.id),
            ('status', '=', 'pending'),
        ], order='id desc', limit=1)
        
        if not request:
            raise UserError(_('No pending approval request found for this requisition.'))
        
        # Security check: Does the user have permission to approve the current step?
        if not request.current_step_id.can_user_approve(self.env.user):
            raise AccessError(_('You do not have permission to approve the current step.'))

        # Use the approval request's native processing with context
        return request.with_context(action_type='approve').process_action()

    def action_reject(self):
        """Reject the current step of the approval request with strict state validation."""
        self.ensure_one()
        if self.state in ['assigned', 'dispatched', 'completed', 'rejected', 'cancelled']:
            raise UserError(_('You cannot reject a request that is already %s.') % self.state)
            
        request = self.env['approval.request'].sudo().search([
            ('res_model', '=', self._name),
            ('res_id', '=', self.id),
            ('status', '=', 'pending'),
        ], order='id desc', limit=1)
        
        if not request:
            raise UserError(_('No pending approval request found for this requisition.'))

        # Security check
        if not request.current_step_id.can_user_reject(self.env.user):
            raise AccessError(_('You do not have permission to reject the current step.'))

        return request.with_context(action_type='reject').process_action()

    def _is_fleet_manager(self):
        user = self.env.user
        return (
            self.env.su
            or user.has_group('base.group_system')
            or user.has_group('hagbes_fleet.group_fleet_admin')
            or user.has_group('hagbes_fleet.group_fleet_manager')
            or user.has_group('hagbes_fleet.group_fmo')
        )

    def _check_fleet_manager(self):
        if not self._is_fleet_manager():
            raise AccessError(_('Only Fleet Managers can perform this operation.'))

    def _check_dept_manager(self):
        user = self.env.user
        if not (
            self.env.su
            or user.has_group('base.group_system')
            or user.has_group('hagbes_fleet.group_fleet_admin')
            or user.has_group('hagbes_fleet.group_dept_manager')
        ):
            raise AccessError(_('Only Department Managers can perform this operation.'))

    @api.model
    def _cron_approval_reminder(self):
        """Daily check for pending approvals. Escalate after 48 hours."""
        threshold = fields.Datetime.subtract(fields.Datetime.now(), hours=48)
        pending_requests = self.search([
            ('state', '=', 'submitted'),
            ('create_date', '<', threshold)
        ])
        for req in pending_requests:
            req.message_post(body=_('Approval Reminder: This request has been pending for over 48 hours.'))
            # Escalate to Fleet Admin
            admin_group = self.env.ref('hagbes_fleet.group_fleet_admin')
            for admin in admin_group.users:
                req.activity_schedule(
                    'mail.mail_activity_data_todo',
                    user_id=admin.id,
                    summary=_('Approval Escalation: %s') % req.name,
                    note=_('Requisition %s is pending approval for more than 48 hours.') % req.name
                )
