{
    'name': 'Hagbes Document Manager',
    'version': '1.0',
    'summary': 'Department based User Manual Management',
    'category': 'Tools',
    'author': 'HG',
    'depends': ['base', 'hr'],
    'data': [
        'security/manual_groups.xml',
        'security/ir.model.access.csv',
        'views/manual_document_views.xml',
    ],
    'installable': True,
    'application': True,
}