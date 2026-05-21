from odoo import models, fields, api

class EmployeePayroll(models.Model):
    _inherit = 'hr.contract'
    
    pension_employee = fields.Float(string="Employee Pension %", default=7.0)
    pension_employer = fields.Float(string="Employer Pension %", default=11.0)
    transport_allowance = fields.Float(string="Transport Allowance")
    housing_allowance = fields.Float(string="Housing Allowance")
from odoo import models, fields, api

class CustomPayslip(models.Model):
    _name = 'custom.payslip'
    _description = 'Custom Employee Payslip'

    employee_id = fields.Many2one('hr.employee', required=True)
    contract_id = fields.Many2one('hr.contract', required=True)

    date_from = fields.Date(required=True)
    date_to = fields.Date(required=True)
    job_id = fields.Many2one('hr.job', required=True)
    department_id = fields.Many2one('hr.department', required=True)
    company_id = fields.Many2one('res.company', required=True)

    # Salary Information
    basic_salary = fields.Float(string="Basic Pay")  # BASIC PAY
    salary_increment = fields.Float(string="Salary Increment")
    updated_basic_salary = fields.Float(string="Updated Basic Pay")  # BASIC PAY after increment

    # Pension and Provident Fund
    pension_employee = fields.Float(string="7% Pension Employee")  # 7% or 11%
    pension_employer = fields.Float(string="11% Pension Employer")
    provident_fund = fields.Float(string="15% Provident Fund")

    # Work Details
    normal_hours = fields.Float(string="Normal Hours")
    weekend_hours = fields.Float(string="Weekend Hours")
    holiday_hours = fields.Float(string="Holiday Hours")
    overtime_hours = fields.Float(string="Overtime Hours")

    # Allowances
    transport_allowance = fields.Float(string="Non-taxable Transport & Fuel")
    taxable_transport_allowance = fields.Float(string="Taxable Fuel & Transport")
    mobile_allowance = fields.Float(string="Mobile Allowance")
    housing_allowance = fields.Float()
    representation_allowance = fields.Float(string="Representation Allowance")

    # Deductions
    absent_deduction = fields.Float(string="Absent Deduction")
    court_cost_lost_item = fields.Float(string="Court/Cost Share/Lost Item")
    fine = fields.Float(string="Fine")
    loan_deduction = fields.Float(string="Loan & Mobile Deduction")
    medical_deduction = fields.Float(string="Medical Deduction")
    income_tax = fields.Float(string="Income Tax on Basic Salary")
    
    # Employer/Employee Contribution
    employer_contribution = fields.Float(string="Employer Contribution")
    employee_contribution = fields.Float(string="Employee Contribution")

    # Totals
    gross_pay = fields.Float(string="Gross Pay")
    total_deduction = fields.Float(string="Total Deduction")
    net_salary = fields.Float(string="Net Pay", compute='_compute_net_salary', store=True)

    @api.depends('gross_pay', 'total_deduction')
    def _compute_net_salary(self):
        for rec in self:
            rec.net_salary = rec.gross_pay - rec.total_deduction if rec.gross_pay and rec.total_deduction else 0.0


# class CustomPayslip(models.Model):
#     _name = 'custom.payslip'
#     _description = 'Custom Employee Payslip'

#     employee_id = fields.Many2one('hr.employee', required=True)
#     contract_id = fields.Many2one('hr.contract', required=True)

#     date_from = fields.Date(required=True)
#     date_to = fields.Date(required=True)
#     basic_salary = fields.Float(string="Basic Salary")
#     job_id = fields.Many2one('hr.job', required=True)
#     department_id = fields.Many2one('hr.department', required=True)
#     company_id = fields.Many2one('res.company', required=True)
#     transport_allowance = fields.Float()
#     housing_allowance = fields.Float()
#     pension_employee = fields.Float()
#     pension_employer = fields.Float()
#     income_tax = fields.Float()
#     net_salary = fields.Float(compute='_compute_net_salary', store=True)

    @api.depends('basic_salary', 'transport_allowance', 'housing_allowance')
    def _compute_net_salary(self):
        for rec in self:
            gross = rec.basic_salary 
            pension = gross * (rec.contract_id.pension_employee / 100)
            tax = self._calculate_income_tax(gross)
            rec.net_salary = gross - pension - tax
            rec.pension_employee = pension
            rec.income_tax = tax

    def _calculate_income_tax(self, salary):
        # income tax logic
        if salary <= 600:
            return 0
        elif salary <= 1650:
            return (salary * 0.10) - 60
        elif salary <= 3200:
            return (salary * 0.15) - 142.50
        elif salary <= 5250:
            return (salary * 0.20) - 302.50
        elif salary <= 7800:
            return (salary * 0.25) - 565
        elif salary <= 10900:
            return (salary * 0.30) - 955
        else:
            return (salary * 0.35) - 1500
        

