from odoo import models, fields, api
from odoo.exceptions import ValidationError

class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    is_guarantor_required = fields.Boolean(string="Is Guarantor Required?")
    guarantor_name = fields.Char(string="Guarantor Full Name")
    guarantor_organization = fields.Char(string="Guarantor Organization")
    guarantor_id_doc = fields.Binary(string="Guarantor ID Document")
    guarantor_id_doc_filename = fields.Char(string="ID Document Filename")
    guarantor_support_docs = fields.Binary(string="Other Supporting Documents")
    guarantor_support_docs_filename = fields.Char(string="Supporting Docs Filename")
  
    witness_ids = fields.One2many('employee.witness', 'employee_id', string='Witnesses')

    @api.constrains('is_guarantor_required', 'guarantor_name', 'guarantor_organization',
                    'guarantor_id_doc', 'guarantor_support_docs', 'witness_ids')
    def _check_guarantor_fields(self):
        for rec in self:
            if rec.is_guarantor_required:
                missing = []
                if not rec.guarantor_name:
                    missing.append("Guarantor Full Name")
                if not rec.guarantor_organization:
                    missing.append("Guarantor Organization")
                if not rec.guarantor_id_doc:
                    missing.append("Guarantor ID Document")
                if not rec.guarantor_support_docs:
                    missing.append("Other Supporting Documents")
                if len(rec.witness_ids) < 2:
                    missing.append("At least 2 Witnesses are required")

                if missing:
                    raise ValidationError(
                        "The following fields are required when 'Is Guarantor Required?' is checked:\n- " +
                        "\n- ".join(missing)
                    )


class EmployeeWitness(models.Model):
    _name = 'employee.witness'
    _description = 'Employee Witness'

    employee_id = fields.Many2one('hr.employee', string='Employee', required=True, ondelete='cascade')
    full_name = fields.Char(string='Full Name', required=True)
    date = fields.Date(string='Date', required=True)

    @api.constrains('employee_id')
    def _check_max_witnesses(self):
        for witness in self:
            count = self.search_count([('employee_id', '=', witness.employee_id.id)])
            if count > 4:
                raise ValidationError("You cannot have more than 4 witnesses per employee.")
