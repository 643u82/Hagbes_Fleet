# -*- coding: utf-8 -*-

from odoo import models, fields, api


class FleetDashboard(models.Model):
    _name = 'fleet.dashboard'
    _description = 'Fleet Operations Dashboard'
    _auto = False

    # KPIs are computed via SQL view for performance
    total_vehicles = fields.Integer(string='Total Vehicles', readonly=True)
    available_vehicles = fields.Integer(string='Available Vehicles', readonly=True)
    allocated_vehicles = fields.Integer(string='Allocated Vehicles', readonly=True)
    in_maintenance_vehicles = fields.Integer(string='Vehicles In Maintenance', readonly=True)
    out_of_service_vehicles = fields.Integer(string='Out Of Service Vehicles', readonly=True)

    total_fleet_distance = fields.Float(string='Total Fleet Distance (KM)', readonly=True)
    average_distance = fields.Float(string='Average Distance (KM)', readonly=True)
    total_trips = fields.Integer(string='Total Trips', readonly=True)

    total_maintenance_events = fields.Integer(string='Total Maintenance Events', readonly=True)
    total_maintenance_cost = fields.Float(string='Total Maintenance Cost', readonly=True)
    vehicles_due = fields.Integer(string='Vehicles Due', readonly=True)
    vehicles_overdue = fields.Integer(string='Vehicles Overdue', readonly=True)

    active_allocations = fields.Integer(string='Active Allocations', readonly=True)
    allocation_count = fields.Integer(string='Allocation Count', readonly=True)

    def init(self):
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW %s AS (
                WITH vehicle_counts AS (
                    SELECT 
                        COUNT(id) AS total_vehicles,
                        SUM(CASE WHEN status = 'available' THEN 1 ELSE 0 END) AS available_vehicles,
                        SUM(CASE WHEN status = 'assigned' THEN 1 ELSE 0 END) AS allocated_vehicles,
                        SUM(CASE WHEN status = 'maintenance' THEN 1 ELSE 0 END) AS in_maintenance_vehicles,
                        SUM(CASE WHEN status = 'out_of_service' THEN 1 ELSE 0 END) AS out_of_service_vehicles
                    FROM hagbes_fleet_vehicle
                ),
                utilization_kpis AS (
                    SELECT 
                        SUM(total_distance) AS total_fleet_distance,
                        AVG(avg_distance) AS average_distance,
                        SUM(trip_count) AS total_trips
                    FROM fleet_utilization_report
                ),
                maintenance_kpis AS (
                    SELECT 
                        COUNT(id) AS total_maintenance_events,
                        SUM(total_cost) AS total_maintenance_cost
                    FROM fleet_maintenance_history_report
                ),
                maintenance_due_kpis AS (
                    SELECT 
                        SUM(CASE WHEN due_status IN ('due', 'warning') THEN 1 ELSE 0 END) AS vehicles_due,
                        SUM(CASE WHEN due_status = 'overdue' THEN 1 ELSE 0 END) AS vehicles_overdue
                    FROM fleet_maintenance_due_report
                ),
                allocation_kpis AS (
                    SELECT 
                        SUM(active_allocations) AS active_allocations,
                        SUM(allocation_count) AS allocation_count
                    FROM fleet_allocation_report
                )
                SELECT 
                    1 AS id,
                    vc.total_vehicles,
                    vc.available_vehicles,
                    vc.allocated_vehicles,
                    vc.in_maintenance_vehicles,
                    vc.out_of_service_vehicles,
                    COALESCE(uk.total_fleet_distance, 0) AS total_fleet_distance,
                    COALESCE(uk.average_distance, 0) AS average_distance,
                    COALESCE(uk.total_trips, 0) AS total_trips,
                    COALESCE(mk.total_maintenance_events, 0) AS total_maintenance_events,
                    COALESCE(mk.total_maintenance_cost, 0) AS total_maintenance_cost,
                    COALESCE(mdk.vehicles_due, 0) AS vehicles_due,
                    COALESCE(mdk.vehicles_overdue, 0) AS vehicles_overdue,
                    COALESCE(ak.active_allocations, 0) AS active_allocations,
                    COALESCE(ak.allocation_count, 0) AS allocation_count
                FROM vehicle_counts vc
                CROSS JOIN utilization_kpis uk
                CROSS JOIN maintenance_kpis mk
                CROSS JOIN maintenance_due_kpis mdk
                CROSS JOIN allocation_kpis ak
            )
        """ % self._table)
