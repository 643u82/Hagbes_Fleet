# -*- coding: utf-8 -*-

from odoo import api, SUPERUSER_ID
import logging

_logger = logging.getLogger(__name__)

def post_init_hook(env):
    """
    Initialize default data and check for optional approval workflow.
    """
    _logger.info("Starting hagbes_fleet post_init_hook")
    
    # 1. Initialize default vehicle states (Idempotent)
    # The 'status' is computed, but we can initialize vehicles without status history
    vehicles_to_init = env['hagbes.fleet.vehicle'].search([('status', '=', False)])
    if vehicles_to_init:
        _logger.info("Initializing %d vehicles with 'available' status.", len(vehicles_to_init))
        for vehicle in vehicles_to_init:
            vehicle._compute_status()
            
    # 2. Initialize default configuration parameters (Idempotent)
    _logger.info("Initializing default configuration parameters.")
    config_params = {
        'fleet.approval.master_enabled': 'True',
        'fleet.approval.maintenance_threshold': '10000.0',
        'fleet.approval.enable_assignment': 'True',
        'fleet.approval.enable_disposal': 'True',
        'fleet.maintenance.warning_km': '7500.0',
        'fleet.maintenance.due_km': '10000.0',
        'fleet.maintenance.overdue_km': '15000.0',
        'fleet.maintenance.warning_days': '90',
        'fleet.maintenance.due_days': '120',
        'fleet.maintenance.overdue_days': '180',
    }
    for key, value in config_params.items():
        if not env['ir.config_parameter'].sudo().get_param(key):
            env['ir.config_parameter'].sudo().set_param(key, value)
            _logger.info("Set default config parameter: %s = %s", key, value)

    # 3. Check if hagbes_approval_workflow is installed and load its data
    approval_module = env['ir.module.module'].search([('name', '=', 'hagbes_approval_workflow'), ('state', '=', 'installed')])
    if approval_module:
        _logger.info("hagbes_approval_workflow detected. Loading fleet approval data...")
        try:
            from odoo.tools import convert_file
            import os
            # Get path to the data file
            manifest_path = os.path.dirname(__file__)
            data_file = 'data/fleet_approval_flows.xml'
            file_path = os.path.join(manifest_path, data_file)
            if os.path.exists(file_path):
                convert_file(env, 'hagbes_fleet', data_file, {}, mode='init', kind='data', pathname=None)
                _logger.info("Fleet approval data loaded successfully.")
            else:
                _logger.warning("Approval data file not found at: %s", file_path)
        except Exception as e:
            _logger.error("Failed to load optional fleet approval data: %s", str(e))
    else:
        _logger.info("hagbes_approval_workflow not installed or not yet active. Skipping approval data load.")
    
    _logger.info("Finished hagbes_fleet post_init_hook")
