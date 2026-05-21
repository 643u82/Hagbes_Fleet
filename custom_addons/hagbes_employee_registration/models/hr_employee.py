from odoo import models, fields, api
from datetime import datetime
import re
from odoo.exceptions import ValidationError
# employee registration module employee ID auto-generation
class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    emp_id = fields.Char(string='Employee ID', copy=False, index=True)

    # _sql_constraints = [
    #     ('unique_emp_id', 'unique(emp_id)', 'Employee ID must be unique.')
    # ]

    @api.model
    def create(self, vals):
        if not vals.get('emp_id'):
            current_year = str(datetime.now().year)

            company_id = vals.get('company_id') or self.env.company.id
            company = self.env['res.company'].browse(company_id)
            prefix = company.prefix or ''

            # LOCK TABLE to prevent concurrent writes (PostgreSQL)
            self.env.cr.execute("LOCK TABLE hr_employee IN SHARE ROW EXCLUSIVE MODE")

            # Get all emp_ids for this year
            existing_ids = self.env['hr.employee'].search([
                ('emp_id', 'ilike', f'{prefix}%{current_year}')
            ]).mapped('emp_id')

            max_number = 0
            pattern = re.compile(rf'{prefix}(\d{{3}}){current_year}')

            for emp_id in existing_ids:
                match = pattern.fullmatch(emp_id) # Match the pattern 
                if match:
                    num = int(match.group(1))
                    max_number = max(max_number, num)
                    print(f"Found emp_id: {emp_id}, extracted number: {num}")
                    
            next_number = max_number + 1
            emp_id = f"{prefix}{next_number:03}{current_year}"

            # Just in case, check again for duplicates (very rare)
            if self.env['hr.employee'].search([('emp_id', '=', emp_id)]):
                raise ValidationError(f"Duplicate Employee ID generated: {emp_id}")

            vals['emp_id'] = emp_id

        return super(HrEmployee, self).create(vals)
