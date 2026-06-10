# -*- coding: utf-8 -*-

from odoo import models, fields, tools


class FleetAvailabilityReport(models.Model):
    _name = 'fleet.availability.report'
    _description = 'Vehicle Availability Analysis'
    _auto = False
    _order = 'days_idle desc'

    vehicle_id = fields.Many2one('hagbes.fleet.vehicle', string='Vehicle', readonly=True)
    plate_number = fields.Char(string='Plate Number', readonly=True)
    company_id = fields.Many2one('res.company', string='Branch', readonly=True)
    vehicle_status = fields.Selection([
        ('available', 'Available'),
        ('assigned', 'Assigned'),
        ('maintenance', 'Maintenance'),
        ('waiting_approval', 'Waiting Approval'),
        ('out_of_service', 'Out of Service'),
    ], string='Status', readonly=True)
    
    driver_name = fields.Char(string='Assigned Driver', readonly=True)
    last_trip_date = fields.Date(string='Last Trip Date', readonly=True)
    days_idle = fields.Integer(string='Days Idle', readonly=True)
    
    current_trip_id = fields.Many2one('fleet.trip', string='Current Trip', readonly=True)
    maintenance_status = fields.Char(string='Maintenance Note', readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW %s AS (
                WITH last_trips AS (
                    SELECT DISTINCT ON (vehicle_id) 
                        vehicle_id, 
                        return_date,
                        id as trip_id
                    FROM fleet_trip 
                    WHERE state = 'completed'
                    ORDER BY vehicle_id, return_date DESC, id DESC
                ),
                current_trips AS (
                    SELECT DISTINCT ON (vehicle_id)
                        vehicle_id,
                        id as trip_id
                    FROM fleet_trip
                    WHERE state IN ('started')
                    ORDER BY vehicle_id, id DESC
                ),
                active_maintenance AS (
                    SELECT DISTINCT ON (vehicle_id)
                        vehicle_id,
                        service_type as maintenance_name
                    FROM hagbes_fleet_maintenance
                    WHERE state = 'active'
                    ORDER BY vehicle_id, id DESC
                )
                SELECT 
                    v.id as id,
                    v.id as vehicle_id,
                    v.plate_number as plate_number,
                    v.company_id as company_id,
                    v.status as vehicle_status,
                    v.driver as driver_name,
                    lt.return_date as last_trip_date,
                    CASE 
                        WHEN lt.return_date IS NOT NULL THEN CURRENT_DATE - lt.return_date
                        ELSE 999 
                    END as days_idle,
                    ct.trip_id as current_trip_id,
                    am.maintenance_name as maintenance_status
                FROM 
                    hagbes_fleet_vehicle v
                LEFT JOIN last_trips lt ON v.id = lt.vehicle_id
                LEFT JOIN current_trips ct ON v.id = ct.vehicle_id
                LEFT JOIN active_maintenance am ON v.id = am.vehicle_id
            )
        """ % self._table)
