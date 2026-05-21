from odoo import models, fields, api

class HrEmployee(models.Model):
    _inherit = 'hr.employee'
    
    hired_date = fields.Date(
        string="Hired Date",
    )
    
    employment_type = fields.Selection([
        ('permanent', 'Permanent'),
        ('contract', 'Contract'),
    ], string="Employment Type")

# # this for one2many relation with appraisal line

#     appraisal_line_ids = fields.One2many(
#         'employee.appraisal.line', 'employee_id', string='Appraisals'
#     )

#     total_score = fields.Integer(
#         string="Total Score", compute="_compute_scores", store=True
#     )
#     average_score = fields.Float(
#         string="Average Score", compute="_compute_scores", store=True
#     )

#     @api.depends("appraisal_line_ids.score")
#     def _compute_scores(self):
#         for emp in self:
#             scores = emp.appraisal_line_ids.mapped('score')
#             scores = [int(s) for s in scores if s]
#             emp.total_score = sum(scores) if scores else 0
#             emp.average_score = sum(scores)/len(scores) if scores else 0.0