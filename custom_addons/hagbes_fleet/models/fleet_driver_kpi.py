# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from datetime import datetime
import calendar

class FleetDriverKpi(models.Model):
    _name = 'fleet.driver.kpi'
    _description = 'Driver Performance KPI'
    _order = 'period desc, total_score desc'

    driver_id = fields.Many2one('hr.employee', string='Driver', required=True, domain=[('is_driver', '=', True)])
    period = fields.Char(string='Period (YYYY-MM)', required=True, help="e.g. 2026-06")
    
    fuel_score = fields.Float(string='Fuel Score (40%)', compute='_compute_scores', store=True)
    distance_score = fields.Float(string='Distance Score (25%)', compute='_compute_scores', store=True)
    time_score = fields.Float(string='Time Score (20%)', compute='_compute_scores', store=True)
    compliance_score = fields.Float(string='Compliance Score (15%)', compute='_compute_scores', store=True)
    
    total_score = fields.Float(string='Total Score', compute='_compute_scores', store=True)
    rank = fields.Integer(string='Rank', help='Monthly Rank')
    computed_date = fields.Datetime(string='Last Computed', default=fields.Datetime.now)
    
    line_ids = fields.One2many('fleet.driver.kpi.line', 'kpi_id', string='Trip Details')

    _sql_constraints = [
        ('driver_period_unique', 'unique(driver_id, period)', 'KPI for this driver and period already exists!')
    ]

    @api.depends('line_ids', 'line_ids.total_score')
    def _compute_scores(self):
        for kpi in self:
            if not kpi.line_ids:
                kpi.fuel_score = 0.0
                kpi.distance_score = 0.0
                kpi.time_score = 0.0
                kpi.compliance_score = 0.0
                kpi.total_score = 0.0
                continue

            # Averages
            kpi.fuel_score = sum(kpi.line_ids.mapped('fuel_score')) / len(kpi.line_ids)
            kpi.distance_score = sum(kpi.line_ids.mapped('distance_score')) / len(kpi.line_ids)
            kpi.time_score = sum(kpi.line_ids.mapped('time_score')) / len(kpi.line_ids)
            kpi.compliance_score = sum(kpi.line_ids.mapped('compliance_score')) / len(kpi.line_ids)

            # Weighted Total
            kpi.total_score = (kpi.fuel_score * 0.40) + (kpi.distance_score * 0.25) + \
                              (kpi.time_score * 0.20) + (kpi.compliance_score * 0.15)


class FleetDriverKpiLine(models.Model):
    _name = 'fleet.driver.kpi.line'
    _description = 'Driver KPI Trip Detail'

    kpi_id = fields.Many2one('fleet.driver.kpi', string='KPI Summary', required=True, ondelete='cascade')
    trip_id = fields.Many2one('fleet.trip', string='Trip', required=True, ondelete='cascade')
    
    fuel_score = fields.Float(string='Fuel Score', default=100.0)
    distance_score = fields.Float(string='Distance Score', default=100.0)
    time_score = fields.Float(string='Time Score', default=100.0)
    compliance_score = fields.Float(string='Compliance Score', default=100.0)
    
    total_score = fields.Float(string='Trip Total Score', compute='_compute_total', store=True)

    @api.depends('fuel_score', 'distance_score', 'time_score', 'compliance_score')
    def _compute_total(self):
        for line in self:
            line.total_score = (line.fuel_score * 0.40) + (line.distance_score * 0.25) + \
                               (line.time_score * 0.20) + (line.compliance_score * 0.15)
