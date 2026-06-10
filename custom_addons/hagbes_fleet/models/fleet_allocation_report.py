# -*- coding: utf-8 -*-

from odoo import models, fields, tools


class FleetAllocationReport(models.Model):
    _name = 'fleet.allocation.report'
    _description = 'Vehicle Allocation Analysis'
    _auto = False
    _order = 'last_allocation_date desc'

    vehicle_id = fields.Many2one('hagbes.fleet.vehicle', string='Vehicle', readonly=True)
    company_id = fields.Many2one('res.company', string='Branch', readonly=True)
    driver_id = fields.Many2one('hr.employee', string='Driver', readonly=True)
    
    allocation_count = fields.Integer(string='Allocation Count', readonly=True)
    active_allocations = fields.Integer(string='Active Allocations', readonly=True)
    total_planned_distance = fields.Float(string='Total Planned Distance (KM)', readonly=True)
    avg_planned_distance = fields.Float(string='Avg Planned Distance', readonly=True)
    first_allocation_date = fields.Datetime(string='First Allocation Date', readonly=True)
    last_allocation_date = fields.Datetime(string='Last Allocation Date', readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW %s AS (
                SELECT 
                    MIN(a.id) as id,
                    a.vehicle_id as vehicle_id,
                    a.company_id as company_id,
                    a.driver_id as driver_id,
                    COUNT(a.id) as allocation_count,
                    SUM(CASE WHEN a.state IN ('assigned', 'dispatched', 'in_progress') THEN 1 ELSE 0 END) as active_allocations,
                    SUM(COALESCE(a.planned_distance, 0)) as total_planned_distance,
                    AVG(COALESCE(a.planned_distance, 0)) as avg_planned_distance,
                    MIN(a.allocation_date) as first_allocation_date,
                    MAX(a.allocation_date) as last_allocation_date
                FROM 
                    hagbes_fleet_allocation a
                GROUP BY 
                    a.vehicle_id, a.company_id, a.driver_id
            )
        """ % self._table)
