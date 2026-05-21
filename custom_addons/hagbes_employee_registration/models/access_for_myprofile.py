from odoo import models, fields

class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    # Private Contact
    
    private_street = fields.Char(groups="base.group_user")
    private_street2 = fields.Char(groups="base.group_user")
    private_city = fields.Char(groups="base.group_user")
    private_state_id = fields.Many2one('res.country.state', groups="base.group_user")
    private_zip = fields.Char(groups="base.group_user")
    private_country_id = fields.Many2one('res.country', groups="base.group_user")
    private_phone = fields.Char(groups="base.group_user")
    private_email = fields.Char(groups="base.group_user")
    bank_account_id = fields.Many2one('res.partner.bank', groups="base.group_user")
    distance_home_work = fields.Integer(groups="base.group_user")
    
    private_car_plate = fields.Char(groups="base.group_user")

    # Citizenship
    country_id = fields.Many2one('res.country', groups="base.group_user")
    identification_id = fields.Char(groups="base.group_user")
    ssnid = fields.Char(groups="base.group_user")
    passport_id = fields.Char(groups="base.group_user")
    # gender = fields.Selection([
    #     ('male', 'Male'),
    #     ('female', 'Female'),
    #     ('other', 'Other')
    #     ],                        
    #     groups="base.group_user",
    #     compute_sudo=True
    # )
    birthday = fields.Date(groups="base.group_user")
    place_of_birth = fields.Char(groups="base.group_user")
    country_of_birth = fields.Many2one('res.country', groups="base.group_user")

    # Emergency
    emergency_contact = fields.Char(groups="base.group_user")
    emergency_phone = fields.Char(groups="base.group_user")
  
    spouse_complete_name = fields.Char(groups="base.group_user")
    spouse_birthdate = fields.Date(groups="base.group_user")
    children = fields.Integer(groups="base.group_user")

    # Education
    # certificate = fields.Selection(groups="base.group_user")
    study_field = fields.Char(groups="base.group_user")
    study_school = fields.Char(groups="base.group_user")
    visa_no = fields.Char(groups="base.group_user")
    permit_no = fields.Char(groups="base.group_user")
    visa_expire = fields.Date(groups="base.group_user")
    work_permit_expiration_date = fields.Date(groups="base.group_user")
    has_work_permit = fields.Binary(groups="base.group_user")
    # barcode = fields.Char(
    #     related='employee_id.barcode',
    #     readonly=True,
    #     compute_sudo=True,
    #     groups="hr.group_hr_manager"
    # )

    # certificate = fields.Selection(
    #     related='employee_id.certificate',
    #     readonly=True,
    #     compute_sudo=True,
    #     groups="hr.group_hr_manager"
    # )

    # distance_home_work_unit = fields.Selection(
    #     selection=[('kilometers', 'km'), ('miles', 'mi')],
    #     related='employee_id.distance_home_work_unit',
    #     readonly=True,
    #     compute_sudo=True,
    #     groups="hr.group_hr_manager"
    # )

    # employee_type = fields.Selection(
    #     related='employee_id.employee_type',
    #     readonly=True,
    #     compute_sudo=True,
    #     groups="hr.group_hr_manager"
    # )

    # gender = fields.Selection(
    #     related='employee_id.gender',
    #     readonly=True,
    #     compute_sudo=True,
    #     groups="hr.group_hr_manager"
    # )

    # pin = fields.Char(
    #     related='employee_id.pin',
    #     readonly=True,
    #     compute_sudo=True,
    #     groups="hr.group_hr_manager"
    # )

    # private_lang = fields.Char(
    #     related='employee_id.private_lang',
    #     readonly=True,
    #     compute_sudo=True,
    #     groups="hr.group_hr_manager"
    # )
