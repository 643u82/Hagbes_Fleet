{
    'name': 'Hagbes POS Invoice Export',
    'version': '1.0',
    'category': 'Accounting',
    'summary': 'Adds a button to send invoice data to external POS API',
    'depends': ['account', 'web'],
    'data': [
        'views/account_move_views.xml',
        'views/account_move_state_views.xml'
    ],
    'assets': {
        'web.assets_backend': [
            'hagbes_pos_invoice_export/static/src/js/print_to_pos_client_action.js',
            'hagbes_pos_invoice_export/static/src/js/get_fs_number_client_action.js'
        ],
    },
    'installable': True,
    'application': False,
}
