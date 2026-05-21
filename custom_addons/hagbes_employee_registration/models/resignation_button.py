from odoo import models, fields, api

class HrEmployeePublic(models.Model):
    _inherit = 'hr.employee.public'

    current_user_id = fields.Integer(compute='_compute_current_user_id', store=False)

    @api.depends('user_id')
    def _compute_current_user_id(self):
        for record in self:
            record.current_user_id = self.env.uid