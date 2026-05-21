{
    'name': 'Hagbes Employee Appraisal',
    'version': '1.0',
    'depends': ['base', 'hr','hagbes_employee_registration','hagbes_org_chart','hagbes_approval_workflow'],
    'category': 'appraisal',
    'author': '@hagbes software tm',
    'data': [

    'views/menu.xml',                  # load root menu first
    'views/appraisal_views.xml',       # then appraisals + action
    'views/appraisal_criteria_views.xml',
    'security/ir.model.access.csv',
    # 'security/filter.xml',
    'views/xpath.xml',
    'views/remark_wizard_view.xml'

],
    'assets': {
        'web.assets_backend': [
            'hagbes_employee_appraisal/static/src/css/appraisal.css',
        ],
    },
    
    'installable': True,
    'application': True,
}

