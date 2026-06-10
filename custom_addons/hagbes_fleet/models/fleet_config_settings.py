# -*- coding: utf-8 -*-

from odoo import models, api, fields

class IrConfigParam(models.TransientModel):
    _inherit = 'res.config.settings'

    fleet_approval_master_enabled = fields.Boolean(
        string='Enable Approval Workflows',
        config_parameter='fleet.approval.master_enabled',
        default=True,
        help='Global switch to enable/disable approval flows for fleet operations.'
    )
    fleet_approval_maintenance_threshold = fields.Float(
        string='Maintenance Approval Threshold',
        config_parameter='fleet.approval.maintenance_threshold',
        default=10000.0,
    )
    fleet_approval_enable_assignment = fields.Boolean(
        string='Assignment Approval',
        config_parameter='fleet.approval.enable_assignment',
        default=True
    )
    fleet_approval_enable_disposal = fields.Boolean(
        string='Disposal Approval',
        config_parameter='fleet.approval.enable_disposal',
        default=True
    )
    is_approval_installed = fields.Boolean(
        string='Is Approval Installed',
        compute='_compute_is_approval_installed'
    )
    fleet_maintenance_warning_km = fields.Float(
        string='Maintenance Warning KM',
        config_parameter='fleet.maintenance.warning_km',
        default=7500.0,
        help='KM threshold for warning status'
    )
    fleet_maintenance_due_km = fields.Float(
        string='Maintenance Due KM',
        config_parameter='fleet.maintenance.due_km',
        default=10000.0,
        help='KM threshold for due status'
    )
    fleet_maintenance_overdue_km = fields.Float(
        string='Maintenance Overdue KM',
        config_parameter='fleet.maintenance.overdue_km',
        default=15000.0,
        help='KM threshold for overdue status'
    )
    fleet_maintenance_warning_days = fields.Integer(
        string='Maintenance Warning Days',
        config_parameter='fleet.maintenance.warning_days',
        default=90,
        help='Days threshold for warning status'
    )
    fleet_maintenance_due_days = fields.Integer(
        string='Maintenance Due Days',
        config_parameter='fleet.maintenance.due_days',
        default=120,
        help='Days threshold for due status'
    )
    fleet_maintenance_overdue_days = fields.Integer(
        string='Maintenance Overdue Days',
        config_parameter='fleet.maintenance.overdue_days',
        default=180,
        help='Days threshold for overdue status'
    )

    def _compute_is_approval_installed(self):
        for rec in self:
            rec.is_approval_installed = 'approval.request' in self.env.registry

    def action_sync_approval_data(self):
        """
        Manually trigger the loading of approval flow XML data.
        """
        self.ensure_one()
        if not self.is_approval_installed:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Error',
                    'message': 'The hagbes_approval_workflow module is not installed.',
                    'sticky': False,
                    'type': 'danger',
                }
            }
        
        try:
            from odoo.tools import convert_file
            import os
            # Get path to the data file
            manifest_path = os.path.dirname(os.path.dirname(__file__))
            data_file = 'data/fleet_approval_flows.xml'
            # Convert file
            convert_file(self.env, 'hagbes_fleet', data_file, {}, mode='init', kind='data', pathname=None)
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Success',
                    'message': 'Approval flows synchronized successfully.',
                    'sticky': False,
                    'type': 'success',
                }
            }
        except Exception as e:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Sync Failed',
                    'message': str(e),
                    'sticky': True,
                    'type': 'danger',
                }
            }
