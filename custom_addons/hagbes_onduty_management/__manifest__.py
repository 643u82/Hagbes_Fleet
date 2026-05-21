{
    'name': 'Hagbes On-Duty Management',
    'version': '1.0',
    'summary': 'OnDuty Management',
    'author': 'SE Team',
    'category': 'Human Resources',
    'depends': ['base', 'hr', 'hr_holidays', 'analytic', "hagbes_approval_workflow", "hagbes_org_chart", "hagbes_timeoff_management"],
    'data': [
        'security/ir.model.access.csv',
        'security/on_duty_access_rules.xml',
        'views/onduty_request.xml',
        'views/onduty_reports.xml',
        'views/onduty_action.xml',
        'views/onduty_menu.xml',
        'views/onduty_wizard_admin.xml',
        'views/success_message_wizard.xml',




    ],
    'installable': True,
    'application': False,
}