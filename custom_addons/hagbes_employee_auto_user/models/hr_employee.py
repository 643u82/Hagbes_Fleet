# from odoo import models, fields, api
#
# class HREmployee(models.Model):
#     _inherit = 'hr.employee'
#
#     def _create_user(self):
#         self.ensure_one()
#         if not self.user_id and self.work_email:
#             user = self.env['res.users'].create({
#                 'name': self.name,
#                 'login': self.work_email,
#                 'groups_id': [(6, 0, self.job_id.group_ids.ids)],
#                 'email': self.work_email,
#             })
#             self.user_id = user
#             return user
#         return False
#
#     @api.model_create_multi
#     def create(self, vals_list):
#         employees = super().create(vals_list)
#         for employee in employees:
#             employee._create_user()
#         return employees
#
#     def write(self, vals):
#         res = super().write(vals)
#         if 'job_id' in vals:
#             for employee in self:
#                 if employee.user_id and employee.job_id.group_ids:
#                     employee.user_id.write({
#                         'groups_id': [(6, 0, employee.job_id.group_ids.ids)]
#                     })
#         return res
# ------------------------------------------------------------------------------------------------
# from odoo import models, fields, api
#
# class HREmployee(models.Model):
#     _inherit = 'hr.employee'
#
#     def _create_user(self):
#         self.ensure_one()
#         if not self.user_id and self.work_email:
#             user = self.env['res.users'].create({
#                 'name': self.name,
#                 'login': self.work_email,
#                 'groups_id': [(6, 0, self.job_id.group_ids.ids)],
#                 'email': self.work_email,
#             })
#             self.user_id = user
#             return user
#         return False
#
#     @api.model_create_multi
#     def create(self, vals_list):
#         for vals in vals_list:
#             # Auto-fill manager based on department logic
#             if 'department_id' in vals and not vals.get('parent_id'):
#                 manager = self.env['hr.employee'].search([
#                     ('department_id', '=', vals['department_id']),
#                     ('is_manager', '=', True)
#                 ], limit=1)
#                 if manager:
#                     vals['parent_id'] = manager.id
#
#         employees = super().create(vals_list)
#
#         for employee in employees:
#             employee._create_user()
#
#         return employees
#
#     def write(self, vals):
#         res = super().write(vals)
#         if 'job_id' in vals:
#             for employee in self:
#                 if employee.user_id and employee.job_id.group_ids:
#                     employee.user_id.write({
#                         'groups_id': [(6, 0, employee.job_id.group_ids.ids)]
#                     })
#         return res
#----------------------------------------------------------------------------------------------------///////
from odoo import models, fields, api

class HREmployee(models.Model):
    _inherit = 'hr.employee'

    def _create_user(self):
        self.ensure_one()
        if not self.user_id and self.work_email:
            user = self.env['res.users'].create({
                'name': self.name,
                'login': self.work_email,
                'groups_id': [(6, 0, self.job_id.group_ids.ids)],
                'email': self.work_email,
            })
            self.user_id = user
            return user
        return False

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            job_id = vals.get('job_id')
            if job_id and not vals.get('parent_id'):
                job = self.env['hr.job'].browse(job_id)
                parent_job = job.parent_id
                if parent_job:
                    manager = self.env['hr.employee'].search([('job_id', '=', parent_job.id)], limit=1)
                    if manager:
                        vals['parent_id'] = manager.id

        employees = super().create(vals_list)

        for employee in employees:
            employee._create_user()

        return employees

    def write(self, vals):
        res = super().write(vals)
        if 'job_id' in vals:
            for employee in self:
                if employee.user_id and employee.job_id.group_ids:
                    employee.user_id.write({
                        'groups_id': [(6, 0, employee.job_id.group_ids.ids)]
                    })
        return res
