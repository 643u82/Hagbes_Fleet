import logging
from odoo import models, api

_logger = logging.getLogger(__name__)

class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    def write(self, vals):
        archiving = 'active' in vals and vals['active'] is False
        unarchiving = 'active' in vals and vals['active'] is True

        res = super(HrEmployee, self).write(vals)

        if archiving or unarchiving:
            for employee in self:

                # Leave allocations
                self.env['hr.leave.allocation'].sudo().with_context(active_test=False).search([
                    ('employee_id', '=', employee.id),
                ]).write({'active': vals['active']})

                # Accrual history
                self.env['hr.leave.accrual.history'].sudo().with_context(active_test=False).search([
                    ('allocation_id.employee_id', '=', employee.id),
                ]).write({'active': vals['active']})

                # Leaves
                self.env['hr.leave'].with_context(active_test=False).search([
                    ('employee_id', '=', employee.id),
                ]).write({'active': vals['active']})

                self.env['hr.leave.expiry.history'].sudo().with_context(active_test=False).search([
                    ('employee_id', '=', employee.id),
                ]).write({'active': vals['active']})

                self.env['hr.leave.deduction.history'].sudo().with_context(active_test=False).search([
                    ('employee_id', '=', employee.id),
                ]).write({'active': vals['active']})

                # Linked user
                if employee.user_id:
                    try:
                        employee.user_id.sudo().write({'active': vals['active']})
                    except Exception as e:
                        _logger.warning(
                            f"Could not update user {employee.user_id.name} "
                            f"linked to employee {employee.name}: {e}"
                        )

        return res
