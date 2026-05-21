#auto creation of Odoo users for employees based on their work email and job position.
from odoo import models, fields, api,SUPERUSER_ID
from odoo.exceptions import ValidationError

class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    auto_create_user = fields.Boolean(string='Create User', default=True)

    @api.model
    def create(self, vals):
        employee = super().create(vals)

        if vals.get('auto_create_user') and employee.work_email:
            self._create_odoo_user_for_employee(employee)

        return employee

    def write(self, vals):
        res = super().write(vals)
        for employee in self:
            if vals.get('auto_create_user') and not employee.user_id and employee.work_email:
                self._create_odoo_user_for_employee(employee)

            # Update user groups when job_id is updated
            if 'job_id' in vals and employee.user_id:
                self._assign_groups_from_job(employee.sudo())


        return res

    def _create_odoo_user_for_employee(self, employee):
     Users = self.env['res.users'].sudo()

    # ✅ Use emp_id as login (same as used during creation)
     existing_user = Users.search([('login', '=', employee.emp_id)], limit=1)

     if existing_user:
        # ✅ Assign user_id only if not already assigned
        if not employee.user_id:
            employee.write({'user_id': existing_user.id})
     else:
        # ✅ Get base group
        base_groups = [self.env.ref('base.group_user').id]

        # ✅ Add job-specific groups
        if employee.job_id:
            base_groups += employee.job_id.group_ids.ids

        # ✅ Create new user
        new_user = Users.create({
            'name': employee.name,
            'login': employee.emp_id,
            'email': employee.work_email,
            'company_id': employee.company_id.id,
            
            'default_branch_id': employee.branch_id.id if employee.branch_id else False,
            'allowed_branch_ids': [(6, 0, list(employee.branch_id.ids))] if employee.branch_id else False,
            'groups_id': [(6, 0, list(set(base_groups)))],
            'must_change_password': True,
        })

        # ✅ Set default password
        hashed_pw = new_user._crypt_context().hash('12345')
        new_user._set_encrypted_password(new_user.id, hashed_pw)

        # ✅ Link user to employee
        employee.write({'user_id': new_user.id})



    def _assign_groups_from_job(self, employee):
        if employee.job_id and employee.user_id:
            # You can include base.group_user if you want to preserve basic access
            base_group = self.env.ref('base.group_user').id
            group_ids = list(set([base_group] + employee.job_id.group_ids.ids))
            employee.user_id.groups_id = [(6, 0, group_ids)]
