{
    'name': 'Hagbes Org Chart',
    'version': '1.0',
    'summary': 'Displays a new custom Org Chart',
    'category': 'Human Resources',
    'depends': ['hr', 'hr_org_chart', 'web', 'hr_recruitment', 'website_hr_recruitment'],
    'data': [
        'security/groups.xml',
        'security/ir.model.access.csv',
        'security/record_rules.xml',
        'views/job_org_chart.xml',
        'views/hr_job_views.xml',
        'views/hr_job_recruitment_view.xml',
        'views/hide_builtin_hr_org_chart_menu.xml',
        'views/hide_new_job_recruitment.xml',
        'views/hide_org_chart_icon.xml',
        'views/hide_publish_butoon.xml',
        'views/res_company_hide_branches.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}


# {
#     'name': 'Hagbes Org Chart',
#     'version': '1.0',
#     'summary': 'A custom org chart widget as a sibling view to default',
#     'category': 'Human Resources',
#     'depends': ['hr', 'hr_org_chart', 'web'],
#     'data': [
#         'views/assets.xml',
#         'views/custom_org_chart_view.xml',
#         'views/menu.xml',
#     ],
#     'installable': True,
#     'application': False,
#     'auto_install': False,
# }
