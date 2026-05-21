from odoo import models, fields

class HrEmployeePublic(models.Model):
    _inherit = 'hr.employee.public'


    # is_current_user = fields.Boolean(compute="_compute_is_current_user", store=False)
    is_guarantor_required = fields.Boolean(
        related='employee_id.is_guarantor_required',
        readonly=True,
        compute_sudo=True
    )
    guarantor_name = fields.Char(related='employee_id.guarantor_name', string="Guarantor Name", readonly=True,  groups="base.group_user")
    guarantor_organization = fields.Char(related='employee_id.guarantor_organization', string="Guarantor Organization", readonly=True,  groups="base.group_user")
    guarantor_id_doc = fields.Binary(related='employee_id.guarantor_id_doc', string="Guarantor ID Document", readonly=True,  groups="base.group_user")
    guarantor_id_doc_filename = fields.Char(related='employee_id.guarantor_id_doc_filename', string="Guarantor ID Doc Filename", readonly=True,  groups="base.group_user")
    guarantor_support_docs = fields.Binary(related='employee_id.guarantor_support_docs', string="Guarantor Support Documents", readonly=True,  groups="base.group_user")
    guarantor_support_docs_filename = fields.Char(related='employee_id.guarantor_support_docs_filename', string="Guarantor Support Docs Filename", readonly=True, groups="base.group_user")

    # Witnesses (if you want to show the related ones, mark readonly)
    # witness_ids = fields.One2many('your.witness.model', 'employee_id', string="Witnesses", readonly=True)
    # Private Contact
     # Private Contact
    private_street = fields.Char(related='employee_id.private_street', readonly=True, compute_sudo=True)
    private_street2 = fields.Char(related='employee_id.private_street2', readonly=True, compute_sudo=True)
    private_city = fields.Char(related='employee_id.private_city', readonly=True, compute_sudo=True)
    private_state_id = fields.Many2one('res.country.state', related='employee_id.private_state_id', readonly=True, compute_sudo=True)
    private_zip = fields.Char(related='employee_id.private_zip', readonly=True, compute_sudo=True)
    private_country_id = fields.Many2one('res.country', related='employee_id.private_country_id', readonly=True, compute_sudo=True)
    private_phone = fields.Char(related='employee_id.private_phone', readonly=True, compute_sudo=True)
    private_email = fields.Char(related='employee_id.private_email', readonly=True, compute_sudo=True)
    bank_account_id = fields.Many2one('res.partner.bank', related='employee_id.bank_account_id', readonly=True, compute_sudo=True)
    # distance_home_work = fields.Integer(related='employee_id.distance_home_work', readonly=True, compute_sudo=True)
    # distance_home_work_unit = fields.Selection(
    #     selection=[('kilometers', 'km'), ('miles', 'mi')],  # keep or mirror actual src selection
    #     related='employee_id.distance_home_work_unit',
    #     readonly=True,
    #     compute_sudo=True,
    #     groups="base.group_user"
    # )
    private_car_plate = fields.Char(related='employee_id.private_car_plate', readonly=True, compute_sudo=True)

    # Citizenship
    country_id = fields.Many2one('res.country', related='employee_id.country_id', readonly=True, compute_sudo=True)
    identification_id = fields.Char(related='employee_id.identification_id', readonly=True, compute_sudo=True)
    ssnid = fields.Char(related='employee_id.ssnid', readonly=True, compute_sudo=True)
    passport_id = fields.Char(related='employee_id.passport_id', readonly=True, compute_sudo=True)
    gender = fields.Selection([
        ('male', 'Male'),
        ('female', 'Female'),
        ('none', 'None'),
        ('other', 'Other')
        ],
        compute="_compute_gender",                   
        compute_sudo=True
    )
    def _compute_gender(self):
     for rec in self:
        rec.gender = rec.employee_id.gender or 'none'

    birthday = fields.Date(related='employee_id.birthday', readonly=True, compute_sudo=True)
    place_of_birth = fields.Char(related='employee_id.place_of_birth', readonly=True, compute_sudo=True)
    country_of_birth = fields.Many2one('res.country', related='employee_id.country_of_birth', readonly=True, compute_sudo=True)

    # Emergency
    emergency_contact = fields.Char(related='employee_id.emergency_contact', readonly=True, compute_sudo=True)
    emergency_phone = fields.Char(related='employee_id.emergency_phone', readonly=True, compute_sudo=True)
    marital = fields.Selection(
    [('single', 'Single'), 
     ('married', 'Married'),
     ('widower', 'Widower'),
     ('none', 'None')
     ],
    compute="_compute_marital",
    readonly=True,
    compute_sudo=True
    )
    def _compute_marital(self):
     for rec in self:
        rec.marital = rec.employee_id.marital or 'none'
    spouse_complete_name = fields.Char(related='employee_id.spouse_complete_name', readonly=True, compute_sudo=True)
    spouse_birthdate = fields.Date(related='employee_id.spouse_birthdate', readonly=True, compute_sudo=True)
    children = fields.Integer(related='employee_id.children', readonly=True, compute_sudo=True)
    branch_id = fields.Many2one(related='employee_id.branch_id', readonly=True, compute_sudo=True)
    hired_date = fields.Date(related='employee_id.hired_date', readonly=True, compute_sudo=True)
    employee_type = fields.Selection(related='employee_id.employee_type', readonly=True, compute_sudo=True)
    emp_id = fields.Char(related='employee_id.emp_id', readonly=True, compute_sudo=True)
    tin_no = fields.Char(related='employee_id.tin_no', readonly=True, compute_sudo=True)
    pension_id = fields.Char(related='employee_id.pension_id', readonly=True, compute_sudo=True)
    house_number= fields.Char(related='employee_id.house_number', readonly=True, compute_sudo=True)

    # Education
    certificate = fields.Selection(
    [
        ('tvt level 1', 'TVET LEVEL I'),
        ('tvt level 2', 'TVET LEVEL II'),
        ('tvt level 3', 'TVET LEVEL III'),
        ('tvt level 4', 'TVET LEVEL IV'),
        ('tvt level 5', 'TVET LEVEL V'),
        ('diploma', 'Diploma'),
        ('ba', 'BA'),
        ('bsc', 'BSc'),
        ('ma', 'MA'),
        ('msc', 'MSc'),
        ('none', 'None')
    ],
    compute="_compute_certificate",
    readonly=True,
    compute_sudo=True,
)

    def _compute_certificate(self):
        valid_values = [val[0] for val in self._fields['certificate'].selection]
        for rec in self:
            value = rec.employee_id.certificate or 'none'
            rec.certificate = value if value in valid_values else 'none'

    study_field = fields.Char(related='employee_id.study_field', readonly=True, compute_sudo=True)
    study_school = fields.Char(related='employee_id.study_school', readonly=True, compute_sudo=True)
    visa_no = fields.Char(related='employee_id.visa_no', readonly=True, compute_sudo=True)
    permit_no = fields.Char(related='employee_id.permit_no', readonly=True, compute_sudo=True)
    visa_expire = fields.Date(related='employee_id.visa_expire', readonly=True, compute_sudo=True)
    work_permit_expiration_date = fields.Date(related='employee_id.work_permit_expiration_date', readonly=True, compute_sudo=True)
    has_work_permit = fields.Binary(related='employee_id.has_work_permit', readonly=True, compute_sudo=True)

    # @api.depends('employee_id.user_id')
    # def _compute_is_current_user(self):
    #     for rec in self:
    #         rec.is_current_user = rec.employee_id.user_id == self.env.user 
        