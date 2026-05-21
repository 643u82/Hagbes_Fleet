import logging
_logger = logging.getLogger(__name__)
from odoo import models, fields, api
from odoo.exceptions import ValidationError
from odoo import _



class HrJob(models.Model):
    _inherit = 'hr.job'

    parent_id = fields.Many2one('hr.job', string="Parent Job Position", help="Defines the job hierarchy", domain="[('id', '!=', id)]")
    email_type = fields.Char(string="Email Type")
    _sql_constraints = [
        (
            'name_company_uniq',
            'unique(name, company_id, department_id, analytic_account_id, parent_id)',
            'A job position with the same name, company, department, branch, and parent already exists.'
        ),
    ]
    email_type_choice = fields.Selection([
        ('self', 'Self'),
        ('group_predefined', 'Group / Predefined'),
        ('no_email', 'No Email'),
    ], string="Email Type Choice", compute='_compute_email_type_choice', inverse='_inverse_email_type_choice', default=False,
        store=False)

    email_type_custom = fields.Char(string="Custom Email Type", store=False)

    temp_child_ids = fields.Many2many(
        comodel_name="hr.job",
        string="Child Positions",
        compute="_compute_temp_child_ids",
        inverse="_inverse_temp_child_ids",
        domain="[('id', '!=', id)]",
        store=False
    )

    analytic_account_id = fields.Many2one(
        'account.analytic.account',
        string='Branch',
        domain="[('plan_id.name', '=', 'Branch'), ('company_id', '=', company_id)]"
    )

    group_ids = fields.Many2many(
        'res.groups',
        string='Access Groups',
        help="Groups automatically assigned to users created for this job position.",
        required=True
    )
    expected_employees = fields.Integer(
        string='Expected Employees',
        required=True,
        help='Defined when creating the job. Cannot be changed after creation.',
    )

    no_of_employee = fields.Integer(
        compute='_compute_no_of_employee',
        store=True,
        string='Current Employees',
    )

    no_of_recruitment = fields.Integer(
        compute='_compute_no_of_recruitment',
        string='Recruitment Target',
        store=True,
        default=0
    )

    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True
    )

    department_id = fields.Many2one(
        'hr.department',
        string='Department',
        required=True
    )



    def name_get(self):
        result = []
        show_full_name = self._context.get('show_job_hierarchy_names', False)
        for job in self:
            name = job.name or ''
            if show_full_name:
                company = job.company_id.name or ""
                branch = job.analytic_account_id.name or ""
                department = job.department_id.name or ""
                name += f" [{company}"
                if branch:
                    name += f" / {branch}"
                if department:
                    name += f" / {department}"
                    name += "]"
            result.append((job.id, name))
        return result

    @api.model
    def name_search(self, name='', args=None, operator='ilike', limit=100):
        args = args or []
        domain = args
        if name:
            domain = args + [(self._rec_name, operator, name)]

        recs = self.search(domain, limit=limit)
        # Important: call name_get on the found records (with proper context)
        return recs.with_context(show_job_hierarchy_names=True).name_get()

    def unlink(self):
        for job in self:
            if job.employee_ids:
                raise ValidationError(_("Cannot delete this job because employees are assigned to it."))
            if self.env['hr.job'].search_count([('parent_id', '=', job.id)]):
                raise ValidationError(_("Cannot delete this job because it has child job positions."))
        return super(HrJob, self).unlink()

    def toggle_active(self):
        """Prevent archiving jobs that have employees or child jobs."""
        for job in self:
            if job.active:
                # Only restrict when archiving (not unarchiving)
                if job.employee_ids:
                    raise ValidationError(_("Cannot archive this job because employees are assigned to it."))
                if self.env['hr.job'].search_count([('parent_id', '=', job.id)]):
                    raise ValidationError(_("Cannot archive this job because it has child job positions."))
        return super(HrJob, self).toggle_active()

    def _is_abbreviation(self, name):
        """Return True if the name looks like an abbreviation/special format."""
        if not name:
            return False
        return (
                name.isupper() or
                any(c in name for c in ['/', '&', '-', '.']) or
                len(name) <= 3
        )

    @api.depends('employee_ids.active')
    def _compute_no_of_employee(self):
        for job in self:
            active_employees = job.employee_ids.filtered(lambda e: e.active)
            job.no_of_employee = len(active_employees)
            if job.no_of_employee > job.expected_employees:
                raise ValidationError(
                    f"Assigned employees ({job.no_of_employee}) exceed expected employees ({job.expected_employees})."
                )

    @api.depends('expected_employees', 'no_of_employee')
    def _compute_no_of_recruitment(self):
        for job in self:
            job.no_of_recruitment = max(job.expected_employees - job.no_of_employee, 0)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if 'expected_employees' not in vals:
                raise ValidationError("Expected Employees must be set at creation.")
            if not vals.get('expected_employees') or vals.get('expected_employees') <= 0:
                raise ValidationError("Expected Employees must be greater than zero.")
        return super().create(vals_list)

    def _compute_employees(self):
        # Disable inherited compute if any
        pass

    @api.model
    def get_org_chart_data(self):
        # Fetch all jobs in one search_read call
        jobs = self.search_read([], [
            'id', 'name', 'parent_id', 'expected_employees',
            'company_id', 'analytic_account_id', 'department_id'
        ])

        job_ids = [job['id'] for job in jobs]

        # Fetch all active employees assigned to the job_ids
        employees = self.env['hr.employee'].search_read([
            ('job_id', 'in', job_ids),
            ('active', '=', True)
        ], ['id', 'name', 'job_id', 'image_128'])

        # Group employees by job_id
        from collections import defaultdict
        emp_map = defaultdict(list)
        for emp in employees:
            job_id = emp['job_id'][0] if emp['job_id'] else None
            if job_id:
                emp_map[job_id].append(emp)

        # Build data list
        data = []
        for job in jobs:
            job_id = job['id']
            assigned_emps = emp_map.get(job_id, [])
            for i in range(job['expected_employees']):
                emp = assigned_emps[i] if i < len(assigned_emps) else None
                display_location = (
                                           job.get('analytic_account_id') and job['analytic_account_id'][1]
                                   ) or (
                                           job.get('company_id') and job['company_id'][1]
                                   ) or ""
                slot_id = f"{job_id}-{emp['id'] if emp else 'vacant'}-{i}"
                data.append({
                    'job_id': job_id,
                    'job_name': job['name'],
                    'employee_id': emp['id'] if emp else None,
                    'employee_name': emp['name'] if emp else 'No employee assigned',
                    'employee_photo_url': f"/web/image/hr.employee/{emp['id']}/image_128" if emp and emp.get(
                        'image_128') else None,
                    'vacant': not bool(emp),
                    'parent_job_id': job['parent_id'][0] if job['parent_id'] else None,
                    'department': job['department_id'][1] if job['department_id'] else "",
                    'company': display_location,
                    'slot_id': slot_id,
                })
        _logger.info("Org Chart Data: %s", data)
        return data

    @api.depends('email_type')
    def _compute_email_type_choice(self):
        for rec in self:
            if not rec.email_type:
                rec.email_type_choice = False
                rec.email_type_custom = False
            elif rec.email_type in ['self', 'no_email']:
                rec.email_type_choice = rec.email_type
                rec.email_type_custom = False
            else:
                rec.email_type_choice = 'group_predefined'
                rec.email_type_custom = rec.email_type

    def _inverse_email_type_choice(self):
        for rec in self:
            if rec.email_type_choice in ['self', 'no_email']:
                rec.email_type = rec.email_type_choice
            else:
                # If user selected group_predefined, use custom input or empty string
                rec.email_type = rec.email_type_custom or ''

    @api.constrains('parent_id')
    def _check_single_root(self):
        for job in self:
            if not job.parent_id:
                root_jobs = self.search([('parent_id', '=', False), ('id', '!=', job.id)])
                if len(root_jobs) >= 2:
                    raise ValidationError("Only two job positions can have no parent. Please select a parent job.")

    @api.constrains('expected_employees')
    def _check_expected_employees(self):
        for job in self:
            if job.expected_employees < job.no_of_employee:
                raise ValidationError(
                    f"Expected Employees ({job.expected_employees}) cannot be less than current active employees ({job.no_of_employee})."
                )

    @api.depends('parent_id')
    def _compute_temp_child_ids(self):
        """Automatically fill child job positions based on parent_id."""
        for job in self:
            children = self.env['hr.job'].search([('parent_id', '=', job.id)])
            job.temp_child_ids = children

    def _inverse_temp_child_ids(self):
        for job in self:
            for child in job.temp_child_ids:
                child.parent_id = job.id

    @api.onchange('name','company_id', 'department_id')
    def _on_change_main_fields(self):
        if self.employee_ids:
            return {
                'warning': {
                    'title': _('Warning'),
                    'message': _(
                        'There are employees assigned to this job. '
                        'Changing this information will affect their records.'
                    ),
                }
            }

    @api.onchange('company_id')
    def _onchange_company(self):
         self.analytic_account_id = False

    @api.onchange('name')
    def _onchange_format_name(self):
        if self.name:
            name = self.name.strip()
            if not self._is_abbreviation(name):
                # Capitalize words only if not abbreviation
                self.name = ' '.join(word.capitalize() for word in name.split())

    @api.model
    def create(self, vals):
        if 'name' in vals:
            vals['name'] = ' '.join(word.capitalize() for word in vals['name'].split())

        self._check_custom_duplicate(vals)
        return super().create(vals)

    def write(self, vals):
        # 🔹 Prepare: Validate expected_employees
        for job in self:
            new_expected = vals.get('expected_employees')
            if new_expected is not None and new_expected < job.no_of_employee:
                raise ValidationError(
                    f"Expected Employees ({new_expected}) cannot be less than current active employees ({job.no_of_employee})."
                )

        # 🔹 Prepare: Clean name and check for duplicates
        combined_vals = {
            'name': vals.get('name', job.name),
            'company_id': vals.get('company_id', job.company_id.id),
            'department_id': vals.get('department_id', job.department_id.id),
            'analytic_account_id': vals.get('analytic_account_id', job.analytic_account_id.id),
            'parent_id': vals.get('parent_id', job.parent_id.id),
        }

        if 'name' in vals:
            combined_vals['name'] = ' '.join(word.capitalize() for word in combined_vals['name'].split())
            vals['name'] = combined_vals['name']

        job._check_custom_duplicate(combined_vals, exclude_id=job.id)

        # 🔹 Track old group_ids if group_ids is being updated
        old_groups_map = {}
        if 'group_ids' in vals:
            for job in self:
                old_groups_map[job.id] = job.group_ids.ids

        # 🔹 Perform original write
        res = super().write(vals)

        # 🔹 Sync group_ids to employees' users if needed
        if 'group_ids' in vals:
            for job in self:
                job._sync_job_group_ids_to_users(old_groups_map.get(job.id, []))

        return res

    def _sync_job_group_ids_to_users(self, old_group_ids):
        """Sync updated job access groups to all users assigned to this job."""
        base_group = self.env.ref('base.group_user')
        for employee in self.employee_ids.filtered(lambda e: e.user_id):
            user = employee.user_id.sudo()

            # ✅ Remove old groups that are no longer in job.group_ids
            for old_group_id in old_group_ids:
                if old_group_id != base_group.id and old_group_id not in self.group_ids.ids:
                    user.groups_id = [(3, old_group_id)]

            # ✅ Add new groups from job.group_ids (avoid duplicates)
            for group in self.group_ids:
                if group not in user.groups_id:
                    user.groups_id = [(4, group.id)]

    def _check_custom_duplicate(self, vals, exclude_id=None):
        name = vals.get('name')
        company_id = vals.get('company_id')
        department_id = vals.get('department_id')
        branch_id = vals.get('analytic_account_id')
        parent_id = vals.get('parent_id')

        if name and company_id and department_id:
            domain = [
                ('name', '=ilike', name.strip()),
                ('company_id', '=', company_id),
                ('department_id', '=', department_id),
                ('analytic_account_id', '=', branch_id),
                ('parent_id', '=', parent_id),
            ]
            if exclude_id:
                domain.append(('id', '!=', exclude_id))

            if self.env['hr.job'].search(domain, limit=1):
                raise ValidationError(
                    _("A job with the same name, company, department, branch, and parent already exists.")
                )

    def _get_all_subordinate_jobs(self):
        """Get all subordinate jobs recursively."""
        all_jobs = self.env['hr.job']
        to_check = self
        while to_check:
            children = self.env['hr.job'].search([('parent_id', 'in', to_check.ids)])
            all_jobs |= children
            to_check = children
        return all_jobs

    def get_subordinate_employees(self):
        """Return all employees under this job (recursively)."""
        subordinate_jobs = self._get_all_subordinate_jobs()
        employees = self.env['hr.employee'].search([
            ('job_id', 'in', subordinate_jobs.ids),
            ('active', '=', True)
        ])
        return employees
