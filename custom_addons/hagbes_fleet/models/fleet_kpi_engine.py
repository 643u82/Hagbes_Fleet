# -*- coding: utf-8 -*-

from odoo import models, fields, api
from datetime import datetime, timedelta
import logging

_logger = logging.getLogger(__name__)

class FleetKpiEngine(models.TransientModel):
    _name = 'fleet.kpi.engine'
    _description = 'Driver KPI Aggregation Engine'

    @api.model
    def cron_compute_driver_kpis(self):
        """
        Scheduled action to compute driver KPIs for the current month.
        """
        _logger.info("Starting Driver KPI Aggregation Engine...")
        
        # Determine the current period (YYYY-MM)
        today = datetime.today()
        period_str = today.strftime('%Y-%m')
        
        # Find all active drivers
        drivers = self.env['hr.employee'].search([('is_driver', '=', True)])
        if not drivers:
            _logger.info("No drivers found for KPI computation.")
            return

        # Start/End date for the current month
        start_date = today.replace(day=1, hour=0, minute=0, second=0)
        # Next month, day 1, minus 1 second
        if today.month == 12:
            end_date = today.replace(year=today.year+1, month=1, day=1, hour=23, minute=59, second=59) - timedelta(days=1)
        else:
            end_date = today.replace(month=today.month+1, day=1, hour=23, minute=59, second=59) - timedelta(days=1)

        for driver in drivers:
            # Get completed trips for this driver in this month
            trips = self.env['fleet.trip'].search([
                ('driver_id', '=', driver.id),
                ('state', '=', 'completed'),
                ('date_to', '>=', start_date),
                ('date_to', '<=', end_date)
            ])

            if not trips:
                continue

            # Find or create the KPI summary for this driver & period
            kpi_record = self.env['fleet.driver.kpi'].search([
                ('driver_id', '=', driver.id),
                ('period', '=', period_str)
            ], limit=1)

            if not kpi_record:
                kpi_record = self.env['fleet.driver.kpi'].create({
                    'driver_id': driver.id,
                    'period': period_str,
                })

            # Clear existing lines to recalculate
            kpi_record.line_ids.unlink()

            # Create lines for each trip
            for trip in trips:
                # 1. Fuel Variance
                fuel_disc = self.env['hagbes.fleet.discrepancy'].search([
                    ('allocation_id', '=', trip.allocation_id.id if hasattr(trip, 'allocation_id') else False),
                    ('type', '=', 'fuel')
                ], limit=1)
                fuel_var = fuel_disc.variance_percent if fuel_disc else 0.0

                # 2. Distance Variance
                dist_disc = self.env['hagbes.fleet.discrepancy'].search([
                    ('allocation_id', '=', trip.allocation_id.id if hasattr(trip, 'allocation_id') else False),
                    ('type', '=', 'distance')
                ], limit=1)
                dist_var = dist_disc.variance_percent if dist_disc else 0.0

                # 3. Time Variance
                time_disc = self.env['hagbes.fleet.discrepancy'].search([
                    ('allocation_id', '=', trip.allocation_id.id if hasattr(trip, 'allocation_id') else False),
                    ('type', '=', 'time')
                ], limit=1)
                time_var = time_disc.variance_percent if time_disc else 0.0

                # 4. Compliance Elements
                hs_disc_count = self.env['hagbes.fleet.discrepancy'].search_count([
                    ('allocation_id', '=', trip.allocation_id.id if hasattr(trip, 'allocation_id') else False),
                    ('severity', '=', 'high')
                ])
                issue_log_count = self.env['fleet.trip.log'].search_count([
                    ('trip_id', '=', trip.id),
                    ('log_type', '=', 'issue')
                ])

                # Calculate Scores (incorporating math adjustments: higher penalties for compliance issues)
                fuel_score = max(0.0, 100.0 - (fuel_var * 2)) if fuel_var > 0 else 100.0
                dist_score = max(0.0, 100.0 - (dist_var * 2)) if dist_var > 0 else 100.0
                time_score = max(0.0, 100.0 - (time_var * 2)) if time_var > 0 else 100.0
                
                # Compliance penalty increased to ensure reckless drivers take a noticeable hit
                comp_score = 100.0 - (hs_disc_count * 50) - (issue_log_count * 20)
                comp_score = max(0.0, comp_score)

                # Create KPI line
                self.env['fleet.driver.kpi.line'].create({
                    'kpi_id': kpi_record.id,
                    'trip_id': trip.id,
                    'fuel_score': fuel_score,
                    'distance_score': dist_score,
                    'time_score': time_score,
                    'compliance_score': comp_score
                })

            kpi_record.computed_date = fields.Datetime.now()

        # Update Rankings
        all_kpis = self.env['fleet.driver.kpi'].search([('period', '=', period_str)], order='total_score desc')
        current_rank = 1
        for kpi in all_kpis:
            kpi.rank = current_rank
            current_rank += 1
            
        _logger.info("Driver KPI Aggregation Engine completed.")
