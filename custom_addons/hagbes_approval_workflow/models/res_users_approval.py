# -*- coding: utf-8 -*-
from odoo import models, fields, api

class ResUsers(models.Model):
    _inherit = 'res.users'

    approval_step_ids = fields.One2many(
        'approval.step',
        compute='_compute_approval_steps',
        string='Approval Assignments',
        help='Steps/Flows where this user can approve based on group membership.'
    )

    def _compute_approval_steps(self):
        for user in self:
            steps = self.env['approval.step'].sudo().search([
                ('role_id.users', 'in', user.ids),
                ('flow_id.active', '=', True),
            ])
            user.approval_step_ids = steps
