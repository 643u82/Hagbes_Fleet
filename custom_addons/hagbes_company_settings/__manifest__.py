{
    'name': 'Hagbes Company Settings',
    'version': '18.0.1.0.0',
    'category': 'Settings',
    'summary': 'Rename Tax ID to TIN, add VAT and Prefix fields on company form.',
    'description': """
        This module customizes the company form by:
        - Renaming "Tax ID" to "TIN"
        - Adding a new "VAT" field for legal VAT number
        - Adding a "Prefix" field for document sequences
    """,
    
    
    'license': 'LGPL-3',
    'depends': ['base'],
    'data': [
        'views/res_company_views.xml',
    ],
    'installable': True,
    'application': False,
   
}