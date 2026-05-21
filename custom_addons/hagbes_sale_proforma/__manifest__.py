{
    'name': 'Hagbes Sale Pro-Forma',
    'version': '1.0',
    'category': 'Sales',
    'summary': 'Adds branch after company name and removes part numbers from product descriptions',
    'author': 'Your Name',
    'depends': ['sale','hagbes_contact_tin_vat','hagbes_company_settings'],
    'assets': {
    'web.assets_backend':  [
        'hagbes_sale_proforma/static/src/scss/report.scss',
            ],
        },
    'data': [
        # 'views/external_layout_company_name.xml',
        'views/external_layout_folder.xml',
        'views/customer_address_layout.xml',
        'views/report_saleorder_proforma.xml',
    ],
    'installable': True,
    'application': False,
}