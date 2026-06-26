# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class FleetTripActualWizard(models.TransientModel):
    _name = 'fleet.trip.actual.wizard'
    _description = 'Record Actual Trip Data'

    trip_id = fields.Many2one('fleet.trip', string='Trip', required=True)

    # Single native datetime picker (no separate date/time floats)
    actual_return_datetime = fields.Datetime(
        string='Actual Return Date & Time',
        required=True,
        default=fields.Datetime.now,
    )

    actual_start_place = fields.Char(string='Trip Origin', required=True)
    actual_destination = fields.Char(string='Final Destination', required=True)
    
    km_at_start_actual = fields.Float(string='KM at Start (Actual Odo.)', required=True)
    km_at_end_actual = fields.Float(string='KM at End (Actual Odo.)', required=True)

    # Fleet Management Officer enters actual fuel used (liters)
    fuel_used_l = fields.Float(string='Fuel Used (L)', required=False, default=0.0)

    transport_km = fields.Float(
        string='Transport KM',
        compute='_compute_transport_km',
        store=True,
        readonly=True,
        default=0.0,
    )

    signed_by = fields.Char(string='Signed By', required=False, readonly=True)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if 'signed_by' in fields_list and not res.get('signed_by'):
            res['signed_by'] = self.env.user.name
        return res

    
    discrepancy_reason = fields.Text(string='Discrepancy Reason')
    
    additional_place_ids = fields.One2many(
        'fleet.trip.actual.wizard.additional.place',
        'wizard_id',
        string='Additional Places',
    )


    @api.onchange('trip_id')
    def _onchange_trip_id(self):
        if self.trip_id:
            self.actual_start_place = self.trip_id.start_location
            # First, get the LATEST completed trip for the vehicle to use its end odometer
            latest_completed_trip = False
            if self.trip_id.vehicle_id:
                latest_completed_trip = self.env['fleet.trip'].search([
                    ('vehicle_id', '=', self.trip_id.vehicle_id.id),
                    ('state', '=', 'completed'),
                    ('km_at_end_actual', '>', 0),
                ], order='id desc', limit=1)
            
            if latest_completed_trip:
                # Use latest completed trip's end odometer
                self.km_at_start_actual = latest_completed_trip.km_at_end_actual
            # Next try the trip's prev_trip_km_end
            elif self.trip_id.prev_trip_km_end:
                self.km_at_start_actual = self.trip_id.prev_trip_km_end
            # If none, get from vehicle
            elif self.trip_id.vehicle_id:
                self.km_at_start_actual = self.trip_id.vehicle_id.odometer or 0.0
            else:
                self.km_at_start_actual = 0.0
            # Load existing additional places from trip
            if self.trip_id.additional_place_ids:
                additional_places = []
                for place in self.trip_id.additional_place_ids:
                    additional_places.append((0, 0, {
                        'place_name': place.place_name,
                        'km_used': place.km_used,
                    }))
                self.additional_place_ids = additional_places

    @api.depends('km_at_start_actual', 'km_at_end_actual')
    def _compute_transport_km(self):
        for wizard in self:
            if wizard.km_at_start_actual and wizard.km_at_end_actual:
                wizard.transport_km = wizard.km_at_end_actual - wizard.km_at_start_actual
            else:
                wizard.transport_km = 0.0

    def action_confirm(self):
        self.ensure_one()
        # Validate odometer values before proceeding
        if self.km_at_end_actual < self.km_at_start_actual:
            raise ValidationError(
                _('End odometer (%s) must be greater than or equal to start odometer (%s).')
                % (self.km_at_end_actual, self.km_at_start_actual)
            )

        if self.fuel_used_l < 0:
            raise ValidationError(_('Fuel Used (L) cannot be negative.'))

        # Prepare additional places data
        additional_places = []
        for place in self.additional_place_ids:
            additional_places.append((0, 0, {
                'place_name': place.place_name,
                'km_used': place.km_used,
            }))
        # Derive legacy Date/Time fields internally from a single datetime picker.
        dt = self.actual_return_datetime
        return_date = dt.date() if dt else False

        # Legacy return_time is a Float representing hours.
        # Example: 06:15 -> 6.25
        return_time = 0.0
        if dt:
            return_time = (dt.hour + (dt.minute / 60.0) + (dt.second / 3600.0))

        self.trip_id.write({
            'return_date': return_date,
            'return_time': return_time,

            'actual_start_place': self.actual_start_place,
            'actual_destination': self.actual_destination,
            'km_at_start_actual': self.km_at_start_actual,
            'km_at_end_actual': self.km_at_end_actual,
            'fuel_used_l': self.fuel_used_l,
            'transport_km': self.transport_km,

            'signed_by': self.signed_by,
            'discrepancy_reason': self.discrepancy_reason,
            'additional_place_ids': additional_places,
        })

        # Completion analytics + discrepancy_status must only be finalized when the trip is in execution stage.
        self.trip_id.action_complete_trip()

        if self.trip_id.vehicle_id:
            self.trip_id.vehicle_id._compute_status()
        return {'type': 'ir.actions.act_window_close'}


class FleetTripActualWizardAdditionalPlace(models.TransientModel):
    _name = 'fleet.trip.actual.wizard.additional.place'
    _description = 'Wizard Additional Place'

    wizard_id = fields.Many2one('fleet.trip.actual.wizard', string='Wizard', required=True, ondelete='cascade')
    place_name = fields.Char(string='Place Name', required=True)
    km_used = fields.Float(string='KM Used', digits=(10, 2), required=True)
