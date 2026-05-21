from odoo import fields, models, api
from datetime import date


class HrEmployee(models.Model):
    _inherit = 'hr.employee.public'
    # is_current_user = fields.Boolean(compute="_compute_is_current_user", store=False)
    # @api.depends('employee_id.user_id')
    # def _compute_is_current_user(self):
    #     for rec in self:
    #         rec.is_current_user = rec.employee_id.user_id == self.env.user
    def action_submit_resignation(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Submit Resignation',
            'res_model': 'employee.resignation',
            'view_mode': 'form',
            'target': 'new',  # Open in popup
            'context': {
                'default_employee_id': self.id,
            }
        }