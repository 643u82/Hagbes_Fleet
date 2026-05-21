# -*- coding: utf-8 -*-
{
    'name': 'Hagbes Payroll Extension',
    'version': '1.0',
    'author': 'Hagbes Software Team',
    'website': 'https://www.hagbes.com',
    'sequence':'1',
    'category': 'Human Resources',
    'license': 'LGPL-3',

    'summary': 'Custom payroll module for hagbes plc by Hagbes software team',
    'depends': ['hr', 'hr_contract','web'],
    'data': [
        'security/ir.model.access.csv',
        'views/payroll_views.xml',
        
    ],
    'installable': True,
    'application': True,
}
