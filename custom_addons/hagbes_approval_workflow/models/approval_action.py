from odoo import models, fields, api
from odoo.exceptions import ValidationError
class ApprovalAction(models.Model):
    _name = 'approval.action'
    _description = 'Global Approval Actions'

    name = fields.Char(string='Action Name', required=True)
    code = fields.Char(string='Action Code', required=True, help="Unique code to identify the action in the workflow")

    _sql_constraints = [
        ('unique_action_name', 'unique(name)', 'Action Name must be unique!'),
        ('unique_action_code', 'unique(code)', 'Action Code must be unique!'),
    ]
