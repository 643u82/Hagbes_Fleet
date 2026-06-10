# -*- coding: utf-8 -*-

from odoo import models, fields, tools


class FleetMaintenanceHistoryReport(models.Model):
    _name = 'fleet.maintenance.history.report'
    _description = 'Maintenance History Analysis'
    _auto = False
    _order = 'last_service_date desc'

    vehicle_id = fields.Many2one('hagbes.fleet.vehicle', string='Vehicle', readonly=True)
    company_id = fields.Many2one('res.company', string='Branch', readonly=True)
    service_type = fields.Selection([
        ('preventive', 'Preventive'),
        ('corrective', 'Corrective'),
    ], string='Service Type', readonly=True)
    service_date = fields.Date(string='Service Date', readonly=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('pending', 'Pending Approval'),
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('rejected', 'Rejected'),
    ], string='State', readonly=True)
    
    maintenance_count = fields.Integer(string='Maintenance Count', readonly=True)
    total_cost = fields.Float(string='Total Cost', readonly=True)
    avg_cost = fields.Float(string='Avg Cost', readonly=True)
    first_service_date = fields.Date(string='First Service Date', readonly=True)
    last_service_date = fields.Date(string='Last Service Date', readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW %s AS (
                SELECT 
                    MIN(m.id) as id,
                    m.vehicle_id as vehicle_id,
                    m.company_id as company_id,
                    m.service_type as service_type,
                    m.service_date as service_date,
                    m.state as state,
                    COUNT(m.id) as maintenance_count,
                    SUM(COALESCE(m.cost, 0)) as total_cost,
                    AVG(COALESCE(m.cost, 0)) as avg_cost,
                    MIN(m.service_date) as first_service_date,
                    MAX(m.service_date) as last_service_date
                FROM 
                    hagbes_fleet_maintenance m
                GROUP BY 
                    m.vehicle_id, m.company_id, m.service_type, m.service_date, m.state
            )
        """ % self._table)
