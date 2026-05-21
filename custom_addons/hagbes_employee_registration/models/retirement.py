from datetime import date, timedelta
from odoo import models, fields, api
from dateutil.relativedelta import relativedelta
from odoo.exceptions import ValidationError,UserError
import logging
_logger = logging.getLogger(__name__)
class EmployeeRetirement(models.Model):
    _name = 'employee.retirement'
    _description = 'Employee Retirement'
    _order = 'retirement_date desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']  
    active = fields.Boolean(default=True) 
    name = fields.Char(string='Retirement Reference', readonly=True, copy=False)
    employee_id = fields.Many2one('hr.employee', string='Employee', required=True)
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        default=lambda self: self.env.company,
        required=True
    )
    branch_id = fields.Many2one(related='employee_id.branch_id', readonly=True)
    department_id = fields.Many2one(related='employee_id.department_id', string='Department', store=True)
    retirement_date = fields.Date(string='Retirement Date', required=True)
    reason = fields.Text(string='Reason for Resignation')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected')
    ], string='Status', default='draft')
    step_progress = fields.Html(string="Approval Progress", compute='_compute_step_progress')

    notify_before_3_months = fields.Boolean(
        string="Notify 3 Months Before Retirement",
        compute='_compute_notify_before_3_months'
    )
   

    @api.model
    def move_to_retirement(self):
        today = date.today()
        retirement_age = 60

        Employee = self.env['hr.employee'].sudo()
        Retirement = self.env['employee.retirement'].sudo()
        ResignationAcceptance = self.env['employee.resignation.acceptance'].sudo()

        _logger.info(f"Starting move_to_retirement for date {today}")

        # Employees aged 59y9m–100
        # start_date = today - relativedelta(years=100)
        # end_date = today - relativedelta(years=59, months=9)
        retirement_cutoff_date = today + relativedelta(months=3)
        employees = Employee.search([
            ('active', '=', True),
            ('birthday', '<=', retirement_cutoff_date - relativedelta(years=retirement_age))
        ])
        # employees = Employee.search([
        #     ('birthday', '>=', start_date),
        #     ('birthday', '<=', end_date),
        #     ('active', '=', True)
        # ])
        _logger.info(f"Found {len(employees)} employees aged 57–100")

        # --- Step 1: Create retirement records ---
        for emp in employees:
            try:
                retirement_date = emp.birthday + relativedelta(years=retirement_age)
                _logger.debug(f"Processing {emp.name}, birthday {emp.birthday}, retirement_date {retirement_date}")

                retirement_record = Retirement.search([
                    ('employee_id', '=', emp.id),
                    ('retirement_date', '=', retirement_date)
                ], limit=1)

                if retirement_record:
                    _logger.info(f"Retirement record already exists for {emp.name}")
                else:
                    retirement_name = self.env['ir.sequence'].next_by_code('employee.retirement') or '/'

                    # Log all fields before creation
                    record_vals = {
                        'employee_id': emp.id,
                        'company_id': emp.company_id.id if emp.company_id else False,
                        'retirement_date': retirement_date,
                        'state': 'draft',
                        'name': retirement_name,
                    }
                    _logger.debug(f"Creating retirement record with values: {record_vals}")

                    created_record = Retirement.create(record_vals)
                    _logger.info(f"Created retirement record for {emp.name}, ID {created_record.id}")

            except Exception as e:
                _logger.error(f"Error creating retirement record for {emp.name}: {e}", exc_info=True)

        # --- Step 2: Move retirement -> acceptance for anyone 60+ ---
        retirement_records = Retirement.search([('retirement_date', '<=', today), ('active', '=', True)])
        _logger.info(f"Found {len(retirement_records)} retirement records to move to acceptance")

        for rec in retirement_records:
            emp = rec.employee_id
            try:
                acceptance = ResignationAcceptance.search([
                    ('employee_id', '=', emp.id),
                    ('req_type', '=', 'retirement')
                ], limit=1)

                if acceptance:
                    _logger.info(f"Acceptance record already exists for {emp.name}")
                    continue

                acceptance_vals = {
                    'employee_id': emp.id,
                    'company_id': rec.company_id.id if rec.company_id else False,
                    'acceptance_date': today,
                    'req_type': 'retirement',
                    'state': 'approved',
                    'comments': 'panding',
                    'ref': rec.name,
                }
                _logger.debug(f"Creating acceptance record with values: {acceptance_vals}")

                created_acceptance = ResignationAcceptance.create(acceptance_vals)
                _logger.info(f"Created acceptance record for {emp.name}, ID {created_acceptance.id}")

                # DELETE retirement record instead of archiving
                _logger.debug(f"Deleting retirement record ID {rec.id} for {emp.name}")
                rec.unlink()
                _logger.info(f"Deleted retirement record for {emp.name}, ID {rec.id}")

            except Exception as e:
                _logger.error(f"Error moving {emp.name} to acceptance: {e}", exc_info=True)

        _logger.info("Retirement processing complete")
        return True



    

    @api.model
    def clear_all_retirements(self):
        """
        Cron job: delete all records in employee.retirement.
        """
        try:
            Retirement = self.env['employee.resignation.acceptance']
            all_records = Retirement.search([])  # Find all retirement records
            count = len(all_records)
            if count:
                all_records.sudo().unlink()  # Delete them
                _logger.info(f"Deleted {count} employee.retirement records")
            else:
                _logger.info("No employee.retirement records found to delete")
            return True
        except Exception as e:
            _logger.error("Error deleting employee.retirement records: %s", str(e), exc_info=True)
            return False
        
    @api.model
    def _get_retirement_count(self):
       return self.search_count([('state', '=', 'pending')])