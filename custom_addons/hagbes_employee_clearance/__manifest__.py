{
    'name': 'Hagbes Employee Clearance',
    'version': '1.0.0',
    'summary': 'Simple employee clearance form',
    'category': 'Employee Clearance',
    'author': 'You',
    'depends': ['base', 'hr', 'hagbes_org_chart', 'hagbes_employee_registration', 'mail','hagbes_approval_workflow' ],
    'data': [
        'security/ir.model.access.csv',
        'views/hagbes_employee_clearance_views.xml',
        'views/approval_remark.xml',
    ],
    'installable': True,
    'application': False,
}
