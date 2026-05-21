# -*- coding: utf-8 -*-

import datetime

from odoo import models, _
from odoo.exceptions import AccessError


class ReportFleetRequisition(models.AbstractModel):
    _name = 'report.hagbes_fleet.report_fleet_requisition'
    _description = 'Secure Fleet Requisition Report'

    def _get_report_values(self, docids, data=None):
        docs = self.env['fleet.requisition'].search([('id', 'in', docids)])
        if set(docs.ids) != set(docids):
            raise AccessError(_('You are not allowed to print one or more selected fleet requisitions.'))
        return {
            'doc_ids': docs.ids,
            'doc_model': 'fleet.requisition',
            'docs': docs,
            'datetime': datetime,
        }


class ReportFleetTripSummary(models.AbstractModel):
    _name = 'report.hagbes_fleet.report_fleet_trip_summary'
    _description = 'Secure Fleet Trip Summary Report'

    def _get_report_values(self, docids, data=None):
        docs = self.env['fleet.trip'].search([('id', 'in', docids)])
        if set(docs.ids) != set(docids):
            raise AccessError(_('You are not allowed to print one or more selected fleet trips.'))
        return {
            'doc_ids': docs.ids,
            'doc_model': 'fleet.trip',
            'docs': docs,
            'datetime': datetime,
        }
