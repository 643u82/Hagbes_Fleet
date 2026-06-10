# -*- coding: utf-8 -*-

from odoo import models, fields, tools


class FleetUtilizationReport(models.Model):
    _name = 'fleet.utilization.report'
    _description = 'Fleet Utilization Analysis'
    _auto = False
    _order = 'total_distance desc'

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
    
    trip_count = fields.Integer(string='Trip Count', readonly=True)
    total_distance = fields.Float(string='Total Distance (KM)', readonly=True)
    avg_distance = fields.Float(string='Avg Distance per Trip', readonly=True)
    last_trip_date = fields.Date(string='Last Trip Date', readonly=True)
    
    # State Layer
    odometer = fields.Float(string='Current Odometer', readonly=True)
    
    # Usage Layer
    last_service_date = fields.Date(string='Last Service Date', readonly=True)
    last_service_km = fields.Float(string='Last Service KM', readonly=True)
    wear_since_service = fields.Float(string='Wear Since Service (KM)', readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW %s AS (
                SELECT 
                    v.id as id,
                    v.id as vehicle_id,
                    v.plate_number as plate_number,
                    v.company_id as company_id,
                    v.status as vehicle_status,
                    COUNT(t.id) as trip_count,
                    SUM(COALESCE(t.actual_distance, 0)) as total_distance,
                    CASE 
                        WHEN COUNT(t.id) > 0 THEN SUM(COALESCE(t.actual_distance, 0)) / COUNT(t.id)
                        ELSE 0 
                    END as avg_distance,
                    MAX(t.return_date) as last_trip_date,
                    -- State Layer: Current Odometer
                    MAX(COALESCE(t.km_at_end_actual, 0)) as odometer,
                    -- Usage Layer: Wear tracking
                    ls.last_service_date,
                    MAX(CASE 
                        WHEN ls.last_service_date IS NOT NULL AND t.return_date <= ls.last_service_date 
                        THEN COALESCE(t.km_at_end_actual, 0) 
                        ELSE 0 
                    END) as last_service_km,
                    SUM(CASE 
                        WHEN ls.last_service_date IS NULL OR t.return_date > ls.last_service_date 
                        THEN COALESCE(t.actual_distance, 0) 
                        ELSE 0 
                    END) as wear_since_service
                FROM 
                    hagbes_fleet_vehicle v
                LEFT JOIN 
                    fleet_trip t ON v.id = t.vehicle_id AND t.state = 'completed'
                LEFT JOIN (
                    SELECT vehicle_id, MAX(service_date) as last_service_date
                    FROM hagbes_fleet_maintenance
                    WHERE state = 'completed'
                    GROUP BY vehicle_id
                ) ls ON v.id = ls.vehicle_id
                GROUP BY 
                    v.id, v.plate_number, v.company_id, v.status, ls.last_service_date
            )
        """ % self._table)
