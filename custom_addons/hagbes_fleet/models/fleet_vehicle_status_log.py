# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import date


class FleetVehicleStatusLog(models.Model):
    _name = 'hagbes.fleet.vehicle.status.log'
    _description = 'Vehicle Status Log'
    _order = 'date desc'
    _rec_name = 'display_name'

    vehicle_id = fields.Many2one(
        'hagbes.fleet.vehicle',
        string='Vehicle',
        required=True,
        ondelete='cascade',
        help='Vehicle for which status is being logged'
    )
    odometer = fields.Float(
        string='Odometer Reading',
        digits=(10, 2),
        required=True,
        help='Current odometer reading in kilometers'
    )
    fuel_level = fields.Float(
        string='Fuel Level',
        digits=(10, 2),
        help='Current fuel level (liters or percentage)'
    )
    condition_notes = fields.Text(
        string='Condition Notes',
        help='Notes about vehicle condition, maintenance needs, or observations'
    )
    date = fields.Date(
        string='Log Date',
        required=True,
        default=fields.Date.context_today,
        help='Date of the status log entry'
    )
    display_name = fields.Char(
        string='Display Name',
        compute='_compute_display_name',
        store=True
    )

    @api.depends('vehicle_id', 'date')
    def _compute_display_name(self):
        """Compute display name for the status log record"""
        for record in self:
            if record.vehicle_id and record.date:
                record.display_name = f"{record.vehicle_id.name} - {record.date}"
            else:
                record.display_name = _("Vehicle Status Log")

    @api.constrains('vehicle_id', 'date')
    def _check_unique_vehicle_date(self):
        """Ensure only one status log per vehicle per date"""
        for record in self:
            if record.vehicle_id and record.date:
                existing = self.search([
                    ('vehicle_id', '=', record.vehicle_id.id),
                    ('date', '=', record.date),
                    ('id', '!=', record.id)
                ])
                if existing:
                    raise ValidationError(
                        _("A status log already exists for vehicle '%s' on %s. "
                          "Only one status log per vehicle per date is allowed.") % 
                        (record.vehicle_id.name, record.date)
                    )

    @api.model_create_multi
    def create(self, vals_list):
        """Override create to post chatter note to vehicle"""
        records = super().create(vals_list)
        for record in records:
            if record.vehicle_id:
                # Post chatter note to vehicle record
                message = _("Status log created for %s: Odometer: %s km") % (
                    record.date,
                    record.odometer
                )
                if record.fuel_level:
                    message += _(", Fuel Level: %s") % record.fuel_level
                if record.condition_notes:
                    message += _(", Notes: %s") % record.condition_notes
                
                record.vehicle_id.message_post(
                    body=message,
                    message_type='notification',
                    subtype_xmlid='mail.mt_note'
                )
        return records