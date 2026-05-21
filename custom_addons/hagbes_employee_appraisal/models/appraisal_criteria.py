from odoo import models, fields
from odoo import api
class AppraisalCriteriaCategory(models.Model):
    _name = "appraisal.criteria.category"
    _description = "Appraisal Criteria Category"

    name = fields.Char(string="Category Name", required=True)
    description = fields.Text(string="Description")
    criteria_ids = fields.One2many("appraisal.criteria", "category_id", string="Criteria")


class AppraisalCriteria(models.Model):
    _name = "appraisal.criteria"
    _description = "Appraisal Criteria"

    name = fields.Char(string="Criteria Name", required=True)
    description = fields.Text(string="Description")
    category_id = fields.Many2one("appraisal.criteria.category", string="Category", required=True, ondelete="cascade")
    active = fields.Boolean(default=True)
    