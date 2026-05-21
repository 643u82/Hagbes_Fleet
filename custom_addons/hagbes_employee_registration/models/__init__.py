from odoo import api, SUPERUSER_ID, models
# from . import hr_employee
from . import upload_resident_id
from . import hr_employee_report
from . import res_partner
from . import auto_create_user
from . import  res_users
from . import family_status
from . import guarantee_information
from . import added_Validation
from . import hr_employee
from . import employment_type
from . import force_password_change
from . import dufult_password
# from . import my_profile
from . import my_profile_add_fields
from . import access_for_myprofile
from . import hr_job_parent_id
from . import resignation
from . import employee_resignation_action
from . import acceptance_letters
from . import discipline
from . import retirement
from . import termination
from . import linked_user_employee
from . import menu_bage
from . import employee_clearance
from . import remark_wizard

# def assign_parent_hook(cr, registry):
    
#     print("Running assign_parent_hook to set parent_id for employees based on job positions.")
#     env = api.Environment(cr, SUPERUSER_ID, {})
#     employees = env['hr.employee'].search([])
#     employees._assign_parent_from_job()
   
#     print("Completed assign_parent_hook.")
