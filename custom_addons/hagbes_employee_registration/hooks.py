from odoo import api, SUPERUSER_ID, models

# def post_init_hook(cr, registry):
#     env = api.Environment(cr, SUPERUSER_ID, {})
#     env['hr.employee'].recompute_all_parent_ids()

# class ModuleUpgradeHook(models.AbstractModel):
#     _name = 'hagbes_employee_registration.upgrade_hook'
#     _description = 'Run on module upgrade'

#     @api.model
#     def _register_hook(self):
#         self.env['hr.employee'].recompute_all_parent_ids()
#         return super()._register_hook()

import logging
_logger = logging.getLogger(__name__)

def assign_parent_hook(cr, registry):
    _logger.info("Running assign_parent_hook to set parent_id for employees based on job positions.")
    print("Running assign_parent_hook to set parent_id for employees based on job positions.")
    env = api.Environment(cr, SUPERUSER_ID, {})
    employees = env['hr.employee'].search([])
    employees._assign_parent_from_job()
    _logger.info("Completed assign_parent_hook.")
    print("Completed assign_parent_hook.")