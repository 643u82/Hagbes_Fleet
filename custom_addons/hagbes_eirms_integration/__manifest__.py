{
    'name': 'Hagbes EIRMS Integration',
    'version':"1.0",
    'category':"Accounting",
    'summary':'Integrate Odoo with Ethiopian EIRMS for e-invocing',
    'depends':['account'],
    'data':['security/ir.model.access.csv','views/mor_info_tab.xml','views/cancel_invoice.xml','views/account_move_cancel_wizard_view.xml','views/account_move_payment.xml'],
    'assets': {
    'web.assets_backend': [
        'hagbes_eirms_integration/static/src/scss/mor_style.scss',
    ],
},
    'installable':True,
    'application':False,
}