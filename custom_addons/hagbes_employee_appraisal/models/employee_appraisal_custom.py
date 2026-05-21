from odoo import models, fields

class EmployeeAppraisalCustom(models.Model):
    _name = "employee.appraisal.custom"
    _description = "Custom Employee Appraisal"

    appraisal_id = fields.Many2one("employee.appraisal", string="Original Appraisal")
    custom_field = fields.Char(string="Custom Field")
