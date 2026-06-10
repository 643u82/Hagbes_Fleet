# -*- coding: utf-8 -*-

from odoo import models, fields, tools
from odoo.tools import config


class FleetMaintenanceDueReport(models.Model):
    _name = 'fleet.maintenance.due.report'
    _description = 'Maintenance Due Analysis'
    _auto = False
    _order = 'due_status desc, km_since_service desc'

    vehicle_id = fields.Many2one('hagbes.fleet.vehicle', string='Vehicle', readonly=True)
    company_id = fields.Many2one('res.company', string='Branch', readonly=True)
    current_odometer = fields.Float(string='Current Odometer', readonly=True)
    last_service_date = fields.Date(string='Last Service Date', readonly=True)
    last_service_km = fields.Float(string='Last Service KM', readonly=True)
    wear_since_service = fields.Float(string='Wear Since Service (KM)', readonly=True)
    days_since_service = fields.Integer(string='Days Since Last Service', readonly=True)
    km_since_service = fields.Float(string='KM Since Last Service', readonly=True)
    due_status = fields.Selection([
        ('normal', 'Normal'),
        ('warning', 'Warning'),
        ('due', 'Due'),
        ('overdue', 'Overdue'),
    ], string='Due Status', compute='_compute_due_status', store=True)

    def _compute_due_status(self):
        for rec in self:
            # Get config parameters
            warning_km = float(self.env['ir.config_parameter'].sudo().get_param('fleet.maintenance.warning_km', 7500.0))
            due_km = float(self.env['ir.config_parameter'].sudo().get_param('fleet.maintenance.due_km', 10000.0))
            overdue_km = float(self.env['ir.config_parameter'].sudo().get_param('fleet.maintenance.overdue_km', 15000.0))
            warning_days = int(self.env['ir.config_parameter'].sudo().get_param('fleet.maintenance.warning_days', 90))
            due_days = int(self.env['ir.config_parameter'].sudo().get_param('fleet.maintenance.due_days', 120))
            overdue_days = int(self.env['ir.config_parameter'].sudo().get_param('fleet.maintenance.overdue_days', 180))

            if rec.km_since_service >= overdue_km or rec.days_since_service >= overdue_days:
                rec.due_status = 'overdue'
            elif rec.km_since_service >= due_km or rec.days_since_service >= due_days:
                rec.due_status = 'due'
            elif rec.km_since_service >= warning_km or rec.days_since_service >= warning_days:
                rec.due_status = 'warning'
            else:
                rec.due_status = 'normal'

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW %s AS (
                WITH last_service AS (
                    SELECT 
                        m.vehicle_id,
                        MAX(m.service_date) AS last_service_date,
                        MAX(m.service_date) FILTER (WHERE m.state = 'completed') AS last_completed_service_date
                    FROM hagbes_fleet_maintenance m
                    GROUP BY m.vehicle_id
                ),
                last_completed_service_km AS (
                    SELECT 
                        m.vehicle_id,
                        m.service_date,
                        COALESCE(t.km_at_end_actual, 0) AS service_km
                    FROM hagbes_fleet_maintenance m
                    LEFT JOIN fleet_trip t ON m.vehicle_id = t.vehicle_id AND t.state = 'completed'
                    WHERE m.state = 'completed'
                ),
                latest_service_km AS (
                    SELECT 
                        vehicle_id,
                        service_km
                    FROM last_completed_service_km
                    WHERE (vehicle_id, service_date) IN (
                        SELECT vehicle_id, MAX(service_date)
                        FROM last_completed_service_km
                        GROUP BY vehicle_id
                    )
                ),
                vehicle_utilization AS (
                    SELECT 
                        v.id AS vehicle_id,
                        v.company_id,
                        COALESCE(ur.odometer, 0) AS current_odometer,
                        COALESCE(ur.wear_since_service, 0) AS wear_since_service,
                        ur.last_service_date
                    FROM hagbes_fleet_vehicle v
                    LEFT JOIN fleet_utilization_report ur ON v.id = ur.vehicle_id
                )
                SELECT 
                    vh.vehicle_id AS id,
                    vh.vehicle_id,
                    vh.company_id,
                    vh.current_odometer,
                    vh.last_service_date,
                    COALESCE(lsk.service_km, 0) AS last_service_km,
                    vh.wear_since_service,
                    CASE 
                        WHEN vh.last_service_date IS NOT NULL THEN CURRENT_DATE - vh.last_service_date
                        ELSE 9999
                    END AS days_since_service,
                    CASE 
                        WHEN vh.last_service_date IS NOT NULL THEN vh.current_odometer - COALESCE(lsk.service_km, 0)
                        ELSE vh.current_odometer
                    END AS km_since_service
                FROM vehicle_utilization vh
                LEFT JOIN latest_service_km lsk ON vh.vehicle_id = lsk.vehicle_id
            )
        """ % self._table)
