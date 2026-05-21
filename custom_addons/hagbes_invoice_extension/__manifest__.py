{
    'name': 'Hagbes Invoice Extension',
    'version':"1.0",
    'category':"Accounting",
    'summary':'Invoicing customization',
    'depends':['account','hagbes_employee_registration'],
    'data':['security/record_rule_invoice.xml','views/account_move_view.xml'],
    'installable':True,
    'application':False,
}