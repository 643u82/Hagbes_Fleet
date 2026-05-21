{
    'name': 'Hagbes Contact TIN/VAT',
    'version': '1.0',
    'category': 'Contacts',
    'summary': 'Adds TIN and VAT fields to company contacts',
    'author': 'Your Name',
    'depends': ['base', 'contacts','account'],
    'data': [
        'views/res_partner_view.xml',
    ],
    'installable': True,
    'application': False,
}
