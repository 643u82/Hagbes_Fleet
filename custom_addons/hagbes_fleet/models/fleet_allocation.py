# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
import logging

_logger = logging.getLogger(__name__)


class HagbesFleetAllocation(models.Model):
    _name = 'hagbes.fleet.allocation'
    _description = 'Fleet Allocation'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'allocation_date desc, id desc'

    # ─── Identification ───────────────────────────────────────────────────────
    name = fields.Char(
        string='Allocation Reference',
        readonly=True,
        copy=False,
        default='New',
        index=True,
        required=True,
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )

    # ─── Core Relationships ───────────────────────────────────────────────────
    request_id = fields.Many2one(
        'fleet.requisition',
        string='Requisition',
        required=True,
        ondelete='restrict',
        index=True,
        tracking=True,
    )
    vehicle_id = fields.Many2one(
        'hagbes.fleet.vehicle',
        string='Vehicle',
        required=True,
        ondelete='restrict',
        index=True,
        tracking=True,
    )
    driver_id = fields.Many2one(
        'hr.employee',
        string='Driver',
        required=True,
        ondelete='restrict',
        index=True,
        tracking=True,
        # Domain filter applied in views: [('job_id.name', 'ilike', 'driver')]
        # This ensures only employees with 'driver' in job title can be selected
        # Case-insensitive search allows: Driver, Senior Driver, Assistant Driver, etc.
        # Future recommendation: Add is_driver boolean field for better performance
    )

    # ─── Allocation Details ───────────────────────────────────────────────────
    assigned_odometer = fields.Float(
        string='Assigned Odometer',
        digits=(10, 2),
        help='Odometer reading at the time of allocation',
    )
    planned_distance = fields.Float(
        string='Planned Distance (KM)',
        digits=(10, 2),
        help='Expected trip distance in kilometers',
    )
    fuel_estimate = fields.Float(
        string='Fuel Estimate (L)',
        digits=(10, 2),
        help='Estimated fuel required in liters',
    )
    allocation_date = fields.Datetime(
        string='Allocation Date',
        required=True,
        default=fields.Datetime.now,
        tracking=True,
        index=True,
    )
    return_date = fields.Datetime(
        string='Return Date',
        tracking=True,
        help='Date and time when the vehicle was returned',
    )

    # ─── State Management ─────────────────────────────────────────────────────
    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('assigned', 'Assigned'),
            ('in_progress', 'In Progress'),
            ('returned', 'Returned'),
            ('completed', 'Completed'),
            ('cancelled', 'Cancelled'),
        ],
        string='Status',
        default='draft',
        required=True,
        tracking=True,
        copy=False,
        index=True,
    )


    # ─── Related Records ──────────────────────────────────────────────────────
    trip_id = fields.Many2one(
        'fleet.trip',
        string='Linked Trip',
        readonly=True,
        copy=False,
        ondelete='set null',
    )
    trip_log_ids = fields.One2many(
        'hagbes.fleet.trip.log',
        'allocation_id',
        string='Trip Logs',
        help='Trip logs associated with this allocation',
    )
    append_request_ids = fields.One2many(
        'hagbes.fleet.allocation.append',
        'allocation_id',
        string='Append Requests',
        help='Extension requests for this allocation',
    )

    # =========================================================================
    # SQL Constraints
    # =========================================================================

    _sql_constraints = [
        ('check_return_date_after_allocation', 
         'CHECK (return_date IS NULL OR return_date >= allocation_date)',
         'Return date must be after allocation date.'),
        ('check_positive_planned_distance',
         'CHECK (planned_distance IS NULL OR planned_distance >= 0)',
         'Planned distance must be positive.'),
        ('check_positive_fuel_estimate',
         'CHECK (fuel_estimate IS NULL OR fuel_estimate >= 0)',
         'Fuel estimate must be positive.'),
    ]

    # =========================================================================
    # Constraints
    # =========================================================================

    @api.constrains('return_date', 'allocation_date')
    def _check_return_date(self):
        """Ensure return_date is after allocation_date."""
        for rec in self:
            if rec.return_date and rec.allocation_date:
                if rec.return_date < rec.allocation_date:
                    raise ValidationError(
                        _('Return date must be after allocation date.')
                    )

    @api.constrains('driver_id')
    def _check_driver_validity(self):
        """
        Driver validation now handled by domain filter.
        Only license expiry check remains since domain ensures job position contains 'driver'.
        """
        for rec in self:
            if rec.driver_id and rec.driver_id.license_expiry and rec.driver_id.license_expiry < fields.Date.today():
                raise ValidationError(_('Driver %s has an expired license (Expiry: %s).') % (rec.driver_id.name, rec.driver_id.license_expiry))

    @api.onchange('vehicle_id')
    def _onchange_vehicle_id(self):
        """Auto-populate assigned odometer from vehicle's current odometer."""
        if self.vehicle_id:
            self.assigned_odometer = self.vehicle_id.odometer

    @api.constrains('vehicle_id', 'state')
    def _check_unique_active_allocation(self):
        """
        Python constraint to enforce unique active allocation per vehicle.
        Blocks double allocations for all operational states: assigned, dispatched, and in progress.
        """
        for rec in self:
            if rec.state in ('assigned', 'in_progress'):
                domain = [
                    ('id', '!=', rec.id),
                    ('vehicle_id', '=', rec.vehicle_id.id),
                    ('state', 'in', ('assigned', 'in_progress')),
                ]

                duplicate = self.search(domain, limit=1)
                if duplicate:
                    raise ValidationError(
                        _('Vehicle "%s" already has an active allocation (Ref: %s in state "%s"). '
                          'Please return that allocation before creating a new one.')
                        % (rec.vehicle_id.name, duplicate.name, duplicate.state)
                    )

    # =========================================================================
    # ORM Overrides
    # =========================================================================

    @api.model_create_multi
    def create(self, vals_list):
        """Generate sequence reference on creation."""
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('hagbes.fleet.allocation') or 'New'
        records = super().create(vals_list)
        for rec in records:
            if rec.request_id:
                rec.request_id.with_context(allow_workflow=True).write({
                    'allocation_id': rec.id,
                    'allocated_by': rec.create_uid.id,
                    'allocated_date': rec.allocation_date,
                })
            rec.message_post(
                body=_('Allocation created: Vehicle %s assigned to driver %s for requisition %s.')
                % (rec.vehicle_id.name, rec.driver_id.name, rec.request_id.name),
                subtype_xmlid='mail.mt_note',
            )
        return records

    def write(self, vals):
        """Track state transitions and synchronize linked requisition state."""
        old_states = {rec.id: rec.state for rec in self}
        old_requisition_states = {rec.id: rec.request_id.state for rec in self if rec.request_id}

        result = super().write(vals)

        for rec in self:
            old_state = old_states.get(rec.id)
            if old_state != rec.state:
                rec._handle_state_transition(old_state, rec.state)
            # Controlled synchronization (no recursion)
            if rec.request_id and rec.request_id.state != rec._map_requisition_state():
                rec.request_id._sync_from_allocation_state(new_allocation_state=rec.state, old_requisition_state=old_requisition_states.get(rec.id))

        return result

    def _map_requisition_state(self):
        """
        Centralized state mapping from allocation to requisition.
        
        This ensures only valid requisition states are returned.
        Direct synchronization is dangerous - always map through this dictionary.
        
        Returns:
            str: Valid requisition state or default 'fmo_approved'
        """
        self.ensure_one()
        
        # Centralized mapping dictionary - single source of truth
        # IMPORTANT: this module must not introduce/retain a dispatch stage.
        allocation_to_requisition_map = {
            'draft': 'assigned',
            'assigned': 'assigned',
            'in_progress': 'assigned',
            'returned': 'assigned',
            'completed': 'completed',
            'cancelled': 'cancelled',
        }

        
        target_state = allocation_to_requisition_map.get(self.state)
        
        # Defensive protection: ensure we always return a valid state
        if not target_state:
            _logger.warning(
                'Invalid allocation state %s for allocation %s. Using default assigned.',
                self.state, self.id
            )
            return 'assigned'
            
        # Validate the target state is actually valid for requisition model
        # This prevents the "Wrong value for fleet.requisition.state" error
        # Use proper ORM registry access instead of direct class metadata access
        requisition_model = self.env['fleet.requisition']
        valid_requisition_states = [state[0] for state in requisition_model._fields['state'].selection]
        
        if target_state not in valid_requisition_states:
            _logger.error(
                'CRITICAL: Mapped state %s is invalid for requisition model. Allocation %s state was %s.',
                target_state, self.id, self.state
            )
            return 'assigned'  # Safe fallback
            
        return target_state


    # =========================================================================
    # State Transition Logic
    # =========================================================================

    def _handle_state_transition(self, old_state, new_state):
        """Handle state transition logic and side effects."""
        self.ensure_one()
        
        # Get state labels
        state_selection = dict(self._fields['state'].selection)
        old_state_label = state_selection.get(old_state, old_state)
        new_state_label = state_selection.get(new_state, new_state)
        
        # Note about EAT timestamp (UTC+3)
        eat_note = _("(Timestamp in UTC, displayed as EAT UTC+3 in UI)")
        
        # Log state change in chatter with EAT timestamp note
        self.message_post(
            body=_('Allocation state changed from %(old_state)s to %(new_state)s by %(user)s. %(eat_note)s')
            % {
                'old_state': old_state_label,
                'new_state': new_state_label,
                'user': self.env.user.name,
                'eat_note': eat_note,
            },
            subtype_xmlid='mail.mt_note',
        )
        
            # When transitioning to 'returned' or 'cancelled', update vehicle status
        if new_state in ('returned', 'cancelled'):
            if self.vehicle_id:
                # The vehicle status is computed based on active allocations/maintenance.
                self.vehicle_id._compute_status()
                self.message_post(
                    body=_('Vehicle %s is now available.')
                    % self.vehicle_id.name,
                    subtype_xmlid='mail.mt_note',
                )

    # =========================================================================
    # Action Methods
    # =========================================================================

    def action_assign_vehicle(self):
        """Confirm assignment.

        Required workflow (user-facing): Confirm Assignment -> Start Trip.
        Do NOT dispatch as an intermediate manual step.
        """
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_('Only draft allocations can be assigned.'))
            if not rec.vehicle_id:
                raise UserError(_('Please assign a vehicle before confirming the assignment.'))

            # Move to assigned without dispatching.
            rec.write({'state': 'assigned'})

            # Ensure a linked trip exists (only create if missing) to keep trip mechanism stable.
            if not rec.trip_id:
                latest_completed_trip = self.env['fleet.trip'].search([
                    ('vehicle_id', '=', rec.vehicle_id.id),
                    ('state', '=', 'completed'),
                    ('km_at_end_actual', '>', 0),
                ], order='id desc', limit=1)

                prev_trip_km_end = latest_completed_trip.km_at_end_actual if latest_completed_trip else (rec.vehicle_id.odometer or 0.0)

                trip_vals = {
                    'allocation_id': rec.id,
                    'vehicle_id': rec.vehicle_id.id,
                    'allocation_date': rec.allocation_date,
                    'allocated_by': self.env.user.id,
                    'start_location': rec.request_id.destination if hasattr(rec.request_id, 'destination') else 'Office',
                    # Trip must start in Trip Planning so the UI never bypasses planning.
                    'state': 'trip_planning',
                    # Auto-populate starting odometer from allocation's assigned odometer
                    'km_at_start': rec.assigned_odometer or rec.vehicle_id.odometer,
                    # km_at_start_actual is only required for Start Trip; set to 0 to satisfy type.
                    'km_at_start_actual': 0.0,
                    'prev_trip_km_end': prev_trip_km_end,
                    'company_id': rec.company_id.id,
                    'requisition_ids': [(4, rec.request_id.id)],
                }
                trip = self.env['fleet.trip'].create(trip_vals)
                rec.write({'trip_id': trip.id})

                rec.request_id.with_context(allow_workflow=True).write({
                    'trip_id': trip.id,
                    'allocated_by': self.env.user.id,
                    'allocated_date': rec.allocation_date,
                    'allocation_id': rec.id,
                })

        if len(self) == 1:
            trip = self.trip_id
            # Open Trip Planning screen (do not auto-start)
            return {
                'name': _('Trip Planning'),
                'type': 'ir.actions.act_window',
                'res_model': 'fleet.trip',
                'view_mode': 'form',
                'target': 'current',
                'res_id': trip.id,
            }
        return True



    def action_dispatch_vehicle(self):
        """DISABLED.

        Dispatch is not a workflow stage in this module.
        This method is kept only to avoid crashes if an old view/action still references it.
        """
        raise UserError(_('Dispatch workflow is disabled. Use Confirm Assignment -> Start Trip instead.'))


    def action_return_vehicle(self):
        """Mark allocation as returned and update trip if it exists."""
        for rec in self:
            if rec.state != 'in_progress':
                raise UserError(_('Only in-progress allocations can be returned.'))
            
            # If there is a linked trip, it should ideally be completed through the Trip record
            # but we provide this as a fallback synchronization
            if rec.trip_id and rec.trip_id.state != 'completed':
                 rec.trip_id.write({'state': 'completed'})

            rec.write({
                'state': 'returned',
                'return_date': fields.Datetime.now(),
            })

    def action_complete_allocation(self):
        """Final terminal state for the allocation."""
        for rec in self:
            if rec.state != 'returned':
                raise UserError(_('Only returned allocations can be completed.'))
            rec.write({'state': 'completed'})
        return True

    def action_cancel(self):
        """Cancel allocation and update linked trip and vehicle status."""
        for rec in self:
            if rec.state in ('completed', 'cancelled'):
                continue
            rec.write({'state': 'cancelled'})
            rec.message_post(body=_('Allocation cancelled.'))
            
            # Also cancel linked trip if it's not already completed or cancelled
            if rec.trip_id and rec.trip_id.state not in ('completed', 'cancelled'):
                rec.trip_id.write({'state': 'cancelled'})
                rec.trip_id.message_post(body=_('Trip cancelled due to allocation cancellation.'))
                
            # Update vehicle's status
            if rec.vehicle_id:
                rec.vehicle_id._compute_status()
        return True

    def action_reset_to_draft(self):
        """Reset allocation back to draft (admin only)."""
        for rec in self:
            if rec.state == 'draft':
                raise UserError(_('Allocation is already in draft state.'))
            if not self.env.user.has_group('hagbes_fleet.group_fleet_admin'):
                raise UserError(_('Only Fleet Admin can reset allocations.'))
            rec.write({
                'state': 'draft',
                'return_date': False,
            })
            rec.message_post(body=_('Allocation reset to draft.'))
            
            # Also reset linked trip to draft if it's not cancelled or completed
            if rec.trip_id and rec.trip_id.state not in ('cancelled', 'completed'):
                rec.trip_id.action_reset_to_draft()
            
            # Update vehicle's status
            if rec.vehicle_id:
                rec.vehicle_id._compute_status()
        return True
    
    def action_reset_to_assigned(self):
        """Reset allocation back to assigned (admin only)."""
        for rec in self:
            if rec.state != 'returned':
                raise UserError(_('Only returned allocations can be reset.'))
            if not self.env.user.has_group('hagbes_fleet.group_fleet_admin'):
                raise UserError(_('Only Fleet Admin can reset allocations.'))
            rec.write({
                'state': 'assigned',
                'return_date': False,
            })

    @api.model
    def _cron_check_overdue_returns(self):
        """Daily check for allocations not returned by the expected date."""
        overdue_allocations = self.search([
            ('state', '=', 'assigned'),
            ('allocation_date', '<', fields.Datetime.subtract(fields.Datetime.now(), days=1))
        ])
        for allocation in overdue_allocations:
            allocation.message_post(body=_('Overdue allocation alert! This vehicle has not been returned.'))
            # Notify FMOs
            fmo_group = self.env.ref('hagbes_fleet.group_fmo')
            for fmo in fmo_group.users:
                allocation.activity_schedule(
                    'mail.mail_activity_data_todo',
                    user_id=fmo.id,
                    summary=_('Overdue Return: %s') % allocation.name,
                    note=_('Vehicle %s is overdue for return.') % allocation.vehicle_id.name
                )
