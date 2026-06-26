# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class FleetTrip(models.Model):
    _name = 'fleet.trip'
    _description = 'Fleet Trip'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'allocation_date desc, id desc'

    # ─── Identification ───────────────────────────────────────────────────────
    name = fields.Char(
        string='Reference',
        readonly=True,
        copy=False,
        default='New',
        index=True,
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    allocation_id = fields.Many2one(
        'hagbes.fleet.allocation',
        string='Allocation',
        ondelete='restrict',
        index=True,
        copy=False,
    )
    requisition_ids = fields.Many2many(
        'fleet.requisition',
        'fleet_trip_requisition_rel',
        'trip_id',
        'requisition_id',
        string='Requisitions',
        copy=False,
    )
    requisition_count = fields.Integer(
        string='Requisition Count',
        compute='_compute_requisition_count',
    )

    # ─── Vehicle / driver ─────────────────────────────────────────────────────
    vehicle_id = fields.Many2one(
        'hagbes.fleet.vehicle',
        string='Vehicle',
        required=True,
        ondelete='restrict',
        index=True,
        tracking=True,
    )
    plate_number = fields.Char(
        string='Plate Number',
        related='vehicle_id.plate_number',
        store=True,
        readonly=True,
    )
    driver_name = fields.Char(
        string='Driver',
        compute='_compute_driver_name',
        store=True,
        readonly=True,
    )

    # ─── Planning ─────────────────────────────────────────────────────────────
    allocation_date = fields.Datetime(
        string='Allocation Date',
        default=fields.Datetime.now,
        tracking=True,
    )
    allocated_by = fields.Many2one(
        'res.users',
        string='Allocated By',
        readonly=True,
        copy=False,
    )
    start_location = fields.Char(string='Start Location')
    planned_route_distance = fields.Float(
        string='Planned Route Distance (KM)',
        digits=(10, 2),
    )
    km_at_start = fields.Float(string='Starting Odometer', digits=(10, 2))

    fuel_at_start = fields.Float(string='Fuel at Start (L)', digits=(10, 2))
    km_per_liter = fields.Float(string='KM per Liter', digits=(10, 2))
    fuel_for_route = fields.Float(
        string='Fuel for Route (L)',
        digits=(10, 2),
        compute='_compute_fuel_for_route',
        store=True,
    )

    # ─── Actual return data ───────────────────────────────────────────────────
    return_date = fields.Date(string='Return Date', copy=False)
    return_time = fields.Float(string='Return Time', copy=False)
    actual_start_place = fields.Char(string='Trip Origin', copy=False)
    actual_destination = fields.Char(string='Final Destination', copy=False)
    signed_by = fields.Char(string='Signed By', copy=False)
    km_at_start_actual = fields.Float(string='KM at Start (Actual)', digits=(10, 2), copy=False)
    km_at_end_actual = fields.Float(string='KM at End (Actual)', digits=(10, 2), copy=False)
    transport_km = fields.Float(
        string='Transport KM',
        digits=(10, 2),
        compute='_compute_transport_km',
        store=True,
        readonly=False,
        copy=False,
    )
    prev_trip_km_end = fields.Float(
        string='Previous Trip End KM',
        digits=(10, 2),
        help='End odometer reading from the last completed trip for this vehicle.',
    )
    actual_distance = fields.Float(
        string='Actual Distance (KM)',
        digits=(10, 2),
        compute='_compute_actual_metrics',
        store=True,
    )
    distance_difference = fields.Float(
        string='Distance Difference (KM)',
        digits=(10, 2),
        compute='_compute_actual_metrics',
        store=True,
    )
    distance_difference_pct = fields.Float(
        string='Distance Difference (%)',
        digits=(10, 2),
        compute='_compute_actual_metrics',
        store=True,
    )
    odometer_gap = fields.Float(
        string='Odometer Gap (KM)',
        digits=(10, 2),
        compute='_compute_actual_metrics',
        store=True,
    )
    odometer_gap_flag = fields.Boolean(
        string='Odometer Gap Flagged',
        compute='_compute_actual_metrics',
        store=True,
    )
    discrepancy_status = fields.Selection(
        selection=[
            ('none', 'None'),
            ('flagged', 'Flagged'),
            ('resolved', 'Resolved'),
        ],
        string='Discrepancy Status',
        default='none',
        copy=False,
        tracking=True,
    )
    discrepancy_reason = fields.Text(string='Discrepancy Reason', copy=False)

    # ─── Fuel consumption tracking ───────────────────────────────────────
    fuel_used_l = fields.Float(
        string='Fuel Used (L)',
        digits=(10, 2),
        default=0.0,
    )
    distance_travelled_km = fields.Float(
        string='Distance Travelled (KM)',
        digits=(10, 2),
        compute='_compute_fuel_metrics',
        store=True,
        readonly=True,
    )
    fuel_efficiency_km_per_l = fields.Float(
        string='Fuel Efficiency (KM/L)',
        digits=(10, 4),
        compute='_compute_fuel_metrics',
        store=True,
        readonly=True,
    )

    @api.depends('km_at_start_actual', 'km_at_end_actual', 'fuel_used_l')
    def _compute_fuel_metrics(self):
        for trip in self:
            start = trip.km_at_start_actual or 0.0
            end = trip.km_at_end_actual or 0.0
            distance = end - start if (end and start) or (end != 0.0 and start != 0.0) else (end - start)
            if distance < 0:
                distance = 0.0

            trip.distance_travelled_km = distance

            fuel = trip.fuel_used_l or 0.0
            if fuel > 0:
                trip.fuel_efficiency_km_per_l = trip.distance_travelled_km / fuel
            else:
                trip.fuel_efficiency_km_per_l = 0.0

    @api.constrains('fuel_used_l')
    def _check_fuel_used_l_non_negative(self):
        for trip in self:
            if trip.fuel_used_l < 0:
                raise ValidationError(_('Fuel Used (L) cannot be negative.'))



    # ─── GPS summary (optional manual / integration fields) ───────────────────
    gps_distance = fields.Float(string='GPS Distance (KM)', digits=(10, 2))
    gps_km_at_end = fields.Float(string='GPS KM at End', digits=(10, 2))
    gps_fuel_at_end = fields.Float(string='GPS Fuel at End (L)', digits=(10, 2))
    gps_fuel_consumed = fields.Float(string='GPS Fuel Consumed (L)', digits=(10, 2))
    unauthorized_stops = fields.Text(string='Unauthorized Stops')
    
    # ─── Trip Route Stops (Trip Planning) ───────────────────────────────
    stops_ids = fields.One2many(
        'fleet.trip.stop',
        'trip_id',
        string='Route Stops',
        copy=True,
        help='Planning stops for this trip; editable during Trip Planning.',
    )

    # ─── Additional Places (Actual phase) ───────────────────────────────
    additional_place_ids = fields.One2many(
        'fleet.trip.additional.place',
        'trip_id',
        string='Additional Places',
        copy=True,
    )


    # ─── Report helpers ───────────────────────────────────────────────────────
    combined_purpose = fields.Text(
        string='Combined Purpose',
        compute='_compute_combined_requisition_text',
    )
    combined_destination = fields.Text(
        string='Combined Destination',
        compute='_compute_combined_requisition_text',
    )
    combined_travellers = fields.Text(
        string='Combined Travellers',
        compute='_compute_combined_requisition_text',
    )

    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('planned', 'Planned'),
            ('approved', 'Approved'),
            ('dispatched', 'Dispatched'),
            ('in_progress', 'In Progress'),
            ('done', 'Done'),
            ('cancelled', 'Cancelled'),
            ('trip_planning', 'Trip Planning'),
        ],
        string='Status',
        default='draft',
        required=True,
        tracking=True,
        copy=False,
        index=True,
    )



    # ─── Computes ─────────────────────────────────────────────────────────────

    @api.depends('requisition_ids')
    def _compute_requisition_count(self):
        for trip in self:
            trip.requisition_count = len(trip.requisition_ids)

    @api.depends('vehicle_id', 'allocation_id', 'allocation_id.driver_id')
    def _compute_driver_name(self):
        for trip in self:
            if trip.allocation_id and trip.allocation_id.driver_id:
                trip.driver_name = trip.allocation_id.driver_id.name
            elif trip.vehicle_id:
                trip.driver_name = trip.vehicle_id.driver
            else:
                trip.driver_name = False

    @api.depends('planned_route_distance', 'km_per_liter')
    def _compute_fuel_for_route(self):
        for trip in self:
            if trip.planned_route_distance and trip.km_per_liter:
                trip.fuel_for_route = trip.planned_route_distance / trip.km_per_liter
            else:
                trip.fuel_for_route = 0.0



    @api.depends(
        'km_at_start_actual',
        'km_at_end_actual',
        'planned_route_distance',
        'prev_trip_km_end',
    )
    def _compute_actual_metrics(self):
        for trip in self:
            if trip.km_at_end_actual and trip.km_at_start_actual:
                trip.actual_distance = trip.km_at_end_actual - trip.km_at_start_actual
            else:
                trip.actual_distance = 0.0

            trip.distance_difference = trip.actual_distance - (trip.planned_route_distance or 0.0)
            if trip.planned_route_distance:
                trip.distance_difference_pct = (
                    (trip.distance_difference / trip.planned_route_distance) * 100.0
                )
            else:
                trip.distance_difference_pct = 0.0

            # Now transport_km is computed, but for odometer gap,
            # expected start is prev_trip_km_end (since transport km is now end - start)
            expected_start = trip.prev_trip_km_end or 0.0
            if trip.km_at_start_actual:
                trip.odometer_gap = trip.km_at_start_actual - expected_start
            else:
                trip.odometer_gap = 0.0
            trip.odometer_gap_flag = abs(trip.odometer_gap) > 1.0

    @api.depends('requisition_ids', 'requisition_ids.purpose', 'requisition_ids.destination', 'requisition_ids.traveller_ids')
    def _compute_combined_requisition_text(self):
        for trip in self:
            reqs = trip.requisition_ids
            trip.combined_purpose = '\n'.join(filter(None, reqs.mapped('purpose')))
            trip.combined_destination = '\n'.join(filter(None, reqs.mapped('destination')))
            
            # Map traveler names from Many2many traveller_ids recordsets of all linked requisitions
            travellers = reqs.mapped('traveller_ids')
            trip.combined_travellers = '\n'.join(filter(None, travellers.mapped('name')))
    
    @api.depends('km_at_start_actual', 'km_at_end_actual')
    def _compute_transport_km(self):
        for trip in self:
            if trip.km_at_start_actual and trip.km_at_end_actual:
                trip.transport_km = trip.km_at_end_actual - trip.km_at_start_actual
            else:
                trip.transport_km = 0.0

    @api.onchange('allocation_id')
    def _onchange_allocation_id(self):
        """Auto-populate trip planning info from linked allocation.

        Starting odometer defaults to the vehicle's current odometer at allocation/trip creation time.
        """

        if self.allocation_id:
            self.vehicle_id = self.allocation_id.vehicle_id
            self.company_id = self.allocation_id.company_id
            self.allocation_date = self.allocation_id.allocation_date
            self.planned_route_distance = self.allocation_id.planned_distance
            # Default starting odometer from the allocation's assigned odometer.
            self.km_at_start = self.allocation_id.assigned_odometer or self.allocation_id.vehicle_id.odometer
            # Actual start odometer must be entered at start time.
            self.km_at_start_actual = False

            self.fuel_at_start = self.allocation_id.fuel_estimate
            if self.allocation_id.request_id:
                self.requisition_ids = [(6, 0, [self.allocation_id.request_id.id])]
            # Fetch previous trip km end (for info only)
            if self.vehicle_id:
                last_trip = self.search([
                    ('vehicle_id', '=', self.vehicle_id.id),
                    ('state', '=', 'completed'),
                    ('km_at_end_actual', '>', 0),
                ], order='id desc', limit=1)
                if last_trip:
                    self.prev_trip_km_end = last_trip.km_at_end_actual
                else:
                    self.prev_trip_km_end = self.vehicle_id.odometer or 0.0


    @api.onchange('vehicle_id')
    def _onchange_vehicle_id(self):
        """Fetch vehicle defaults and auto-populate starting odometer from vehicle current odometer."""
        if self.vehicle_id:
            self.km_per_liter = self.vehicle_id.kmperl or 10.0

            # Auto-populate starting odometer from current vehicle odometer.
            self.km_at_start = self.vehicle_id.odometer or 0.0

            # Get previous trip's end KM (for info only)
            last_trip = self.search([
                ('vehicle_id', '=', self.vehicle_id.id),
                ('state', '=', 'completed'),
                ('km_at_end_actual', '>', 0),
            ], order='id desc', limit=1)
            if last_trip:
                self.prev_trip_km_end = last_trip.km_at_end_actual
            else:
                self.prev_trip_km_end = self.vehicle_id.odometer or 0.0

            # Ensure actual start odometer must be entered later.
            self.km_at_start_actual = False



    # ─── ORM ──────────────────────────────────────────────────────────────────

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('fleet.trip') or 'New'
            self._apply_allocation_defaults(vals)
            self._apply_vehicle_defaults(vals)
        return super().create(vals_list)

    def _apply_allocation_defaults(self, vals):
        allocation_id = vals.get('allocation_id')
        if not allocation_id:
            return
        allocation = self.env['hagbes.fleet.allocation'].browse(allocation_id)
        if not allocation.exists():
            return
        vals.setdefault('vehicle_id', allocation.vehicle_id.id)
        vals.setdefault('company_id', allocation.company_id.id)
        vals.setdefault('allocation_date', allocation.allocation_date)
        vals.setdefault('planned_route_distance', allocation.planned_distance)
        # Leave km_at_start blank for manual entry
        vals.setdefault('fuel_at_start', allocation.fuel_estimate)
        if allocation.request_id:
            vals.setdefault('requisition_ids', [(4, allocation.request_id.id)])
        if allocation.driver_id and not vals.get('allocated_by'):
            vals.setdefault('allocated_by', self.env.user.id)

    def _apply_vehicle_defaults(self, vals):
        vehicle_id = vals.get('vehicle_id')
        if not vehicle_id:
            return
        vehicle = self.env['hagbes.fleet.vehicle'].browse(vehicle_id)
        if not vehicle.exists():
            return
        vals.setdefault('km_per_liter', vehicle.kmperl or 10.0)

        # Auto-populate starting odometer from current vehicle odometer unless explicitly provided.
        vals.setdefault('km_at_start', vehicle.odometer or 0.0)

        if not vals.get('prev_trip_km_end'):
            last_trip = self.search([
                ('vehicle_id', '=', vehicle.id),
                ('state', '=', 'completed'),
                ('km_at_end_actual', '>', 0),
            ], order='id desc', limit=1)
            if last_trip:
                vals['prev_trip_km_end'] = last_trip.km_at_end_actual
            else:
                # If no previous trips, use vehicle's current odometer
                vals['prev_trip_km_end'] = vehicle.odometer or 0.0
        # Leave km_at_start_actual blank for manual entry

    # ─── Workflow actions ─────────────────────────────────────────────────────

    def action_confirm_planning(self):
        """Planning stage: move draft/planned -> planned.

        Guardrails:
        - must have at least one stop
        - only planning fields should be filled by this point
        """
        for trip in self:
            if trip.state not in ('draft', 'planned'):
                raise UserError(_('Only Draft/Planned trips can be confirmed as Planned.'))
            if not trip.stops_ids:
                raise UserError(_('Add at least one route stop before confirming planning.'))
            trip.write({'state': 'planned'})
            trip.message_post(body=_('Trip planned.'))
        return True

    def action_approve_planning(self):
        """Planning approval stage: planned -> approved."""
        for trip in self:
            if trip.state != 'planned':
                raise UserError(_('Only Planned trips can be approved.'))
            trip.write({'state': 'approved'})
            trip.message_post(body=_('Trip approved.'))
        return True

    def action_dispatch(self):
        """Dispatch stage: approved -> dispatched.

        Dispatch unlocks dispatch inputs (km_at_start_actual / fuel_at_start) and locks planning inputs.
        """
        for trip in self:
            if trip.state != 'approved':
                raise UserError(_('Only Approved trips can be dispatched.'))
            # Ensure dispatch baseline values exist
            if not trip.km_at_start_actual and trip.km_at_start:
                trip.km_at_start_actual = trip.km_at_start
            if not trip.km_at_start_actual:
                raise UserError(_('KM at Start (Actual) is required before dispatch.'))
            trip.write({'state': 'dispatched'})
            trip.message_post(body=_('Trip dispatched.'))
        return True

    def action_start_trip(self):
        """Execution stage: dispatched -> in_progress."""
        for trip in self:
            if trip.state != 'dispatched':
                raise UserError(_('Only Dispatched trips can be started.'))
            trip.write({'state': 'in_progress'})
            # Update linked allocation when the trip starts.
            if trip.allocation_id and trip.allocation_id.state in ['assigned', 'draft', 'in_progress']:
                trip.allocation_id.write({'state': 'in_progress'})
            trip.message_post(body=_('Trip execution started.'))
        return True




    def action_record_actual_data(self):
        self.ensure_one()
        return {
            'name': _('Record Return Data'),
            'type': 'ir.actions.act_window',
            'res_model': 'fleet.trip.actual.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_trip_id': self.id},
        }

    def action_cancel_trip(self):
        for trip in self:
            if trip.state in ('done', 'cancelled'):
                raise UserError(_('Completed/Cancelled trips cannot be cancelled.'))
            trip.write({'state': 'cancelled'})
            trip.message_post(body=_('Trip cancelled.'))

            
            # Update linked allocation if it exists
            if trip.allocation_id and trip.allocation_id.state not in ('cancelled', 'completed', 'returned'):
                trip.allocation_id.write({'state': 'cancelled'})
                trip.allocation_id.message_post(body=_('Allocation cancelled due to trip cancellation.'))
                
            # Also update the vehicle's status by calling _compute_status
            if trip.vehicle_id:
                trip.vehicle_id._compute_status()
        return True

    def action_reset_to_draft(self):
        for trip in self:
            if trip.state == 'draft':
                raise UserError(_('Trip is already in draft state.'))
            trip.write({
                'state': 'draft',
                # Clear actual data (optional, uncomment if needed:
                # 'return_date': False,
                # 'return_time': 0.0,
                # 'actual_start_place': False,
                # 'actual_destination': False,
                # 'signed_by': False,
                # 'km_at_end_actual': 0.0,
                # 'transport_km': 0.0,
                # 'discrepancy_status': 'none',
                # 'discrepancy_reason': False,
            })
            trip.message_post(body=_('Trip reset to draft.'))
            
            # Update linked allocation to draft if it exists
            if trip.allocation_id and trip.allocation_id.state not in ('draft', 'cancelled', 'completed'):
                trip.allocation_id.write({'state': 'draft'})
                trip.allocation_id.message_post(body=_('Allocation reset to draft due to trip reset.'))
                
            # Also update the vehicle's status by calling _compute_status
            if trip.vehicle_id:
                trip.vehicle_id._compute_status()
        return True

    @api.constrains('km_at_start_actual', 'km_at_end_actual')
    def _check_odometer_values(self):
        """Ensure end odometer is greater than or equal to start odometer."""
        for trip in self:
            if trip.km_at_start_actual and trip.km_at_end_actual:
                if trip.km_at_end_actual < trip.km_at_start_actual:
                    raise ValidationError(
                        _('End odometer (%s) must be greater than or equal to start odometer (%s).')
                        % (trip.km_at_end_actual, trip.km_at_start_actual)
                    )

    def action_complete_trip(self):
        for trip in self:
            if trip.state != 'in_progress':
                raise UserError(_('Only In-Progress trips can be completed.'))
            if trip.km_at_end_actual == 0.0 and not trip.km_at_end_actual:
                pass
            if not trip.km_at_end_actual:
                raise ValidationError(_('KM at end (actual) is required to complete the trip.'))
            if trip.km_at_end_actual < trip.km_at_start_actual:
                raise ValidationError(
                    _('End odometer (%s) must be greater than or equal to start odometer (%s).')
                    % (trip.km_at_end_actual, trip.km_at_start_actual)
                )
            # Fuel must exist for completion analytics
            if trip.fuel_used_l < 0:
                raise ValidationError(_('Fuel Used (L) cannot be negative.'))

            discrepancy_status = 'none'
            if trip.odometer_gap_flag or abs(trip.distance_difference_pct) > 10.0:
                discrepancy_status = 'flagged' if not trip.discrepancy_reason else 'resolved'

            trip.write({
                'state': 'done',
                'discrepancy_status': discrepancy_status,
            })

            # Update vehicle's odometer to the trip's end odometer
            if trip.vehicle_id:
                trip.vehicle_id.odometer = trip.km_at_end_actual
            # Mark allocation as returned and then completed
            if trip.allocation_id:
                if trip.allocation_id.state in ['in_progress', 'assigned']:
                    trip.allocation_id.write({'state': 'returned'})
                    # Then complete the allocation to make vehicle available
                    trip.allocation_id.action_complete_allocation()


            for req in trip.requisition_ids:
                # Keep existing requisition workflow semantics.
                if req.state in ('dispatched', 'assigned'):
                    req.with_context(allow_workflow=True).write({'state': 'completed'})

            trip.message_post(body=_('Trip completed.'))
        return True

    def action_view_requisitions(self):
        self.ensure_one()
        return {
            'name': _('Requisitions'),
            'type': 'ir.actions.act_window',
            'res_model': 'fleet.requisition',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.requisition_ids.ids)],
            'context': {'create': False},
        }


class FleetTripStop(models.Model):
    _name = 'fleet.trip.stop'
    _description = 'Fleet Trip Stop'
    _order = 'sequence, id'

    trip_id = fields.Many2one('fleet.trip', string='Trip', required=True, ondelete='cascade')
    sequence = fields.Integer(string='Sequence', default=10)
    location = fields.Char(string='Stop Location', required=True)
    notes = fields.Text(string='Notes')




    def action_mark_visited(self):
        for stop in self:
            if stop.trip_id.state != 'started':
                raise UserError(_('You can mark stops as visited only when the trip is started.'))
            stop.write({
                'status': 'visited',
                'visited_by': stop.env.user.id,
                'visited_datetime': fields.Datetime.now(),
            })

    def action_mark_skipped(self, reason=None):
        for stop in self:
            if stop.trip_id.state != 'started':
                raise UserError(_('You can mark stops as skipped only when the trip is started.'))
            stop.write({
                'status': 'skipped',
                'skipped_reason': reason or stop.skipped_reason or False,
            })


    # Execution tracking (trip must be started)
    status = fields.Selection(
        [
            ('planned', 'Planned'),
            ('visited', 'Visited'),
            ('skipped', 'Skipped'),
        ],
        string='Stop Status',
        default='planned',
        required=True,
        tracking=True,
    )
    visited_by = fields.Many2one(
        'res.users',
        string='Visited By',
        readonly=True,
        copy=False,
        tracking=True,
    )
    visited_datetime = fields.Datetime(
        string='Visited Date Time',
        readonly=True,
        copy=False,
        tracking=True,
    )
    skipped_reason = fields.Text(string='Skipped Reason')



class FleetTripAdditionalPlace(models.Model):
    _name = 'fleet.trip.additional.place'
    _description = 'Fleet Trip Additional Place'

    trip_id = fields.Many2one('fleet.trip', string='Trip', required=True, ondelete='cascade')
    place_name = fields.Char(string='Place Name', required=True)
    km_used = fields.Float(string='KM Used', digits=(10, 2), required=True)


