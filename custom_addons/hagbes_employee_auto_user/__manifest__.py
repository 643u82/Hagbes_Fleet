{
    'name': 'Hagbes Employee Auto User',
    'version': '18.0.1.0.0',
    'summary': 'Automatically create users for employees with job-based access 18.0',
    'depends': ['hr'],
    'data': [
        'views/employee_view.xml',
        'security/ir.model.access.csv'
    ],
    'installable': True,
    'application': True,
}
