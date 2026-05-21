{
    'name': 'Hagbes Time-off Management',
    'version': '1.0',
    'summary': 'Customize Time Off Calculation and Features',
    'author': 'Se Team',
    'category': 'Human Resources',
    'depends': ['hr_holidays','hagbes_approval_workflow','hagbes_employee_registration', 'hagbes_org_chart'],
    'data': [
        'Security/leave_group.xml',
        'Security/ir.model.access.csv',
        'Security/leave_record_rule.xml',
        'data/cron_jobs.xml',
        'views/hr_holidays_view.xml',
         'views/leave_wizard_form.xml',
        'views/hr_leave_balance_configuration.xml',
        'views/backdate_menu.xml',
        'views/hr_leave_backdate_wizard.xml',
        'views/hr_leave_dashboard.xml',
         'views/hr_allocation_form.xml',
         'views/hr_leave_employee_type_report.xml',
         'views/success_message_wizard.xml',
         'views/leave_access_for_admin.xml',
        # 'views/leave_type_hide_buttons.xml'

    ],
    'assets': {
       'web.assets_backend': [
    'hr_holidays/static/src/**/*',   
    'hagbes_timeoff_management/static/src/js/calendar_holiday.js',
    'hagbes_timeoff_management/static/src/js/time_off_dashboard.js',
    'hagbes_timeoff_management/static/src/js/time_off_card.js',
    'hagbes_timeoff_management/static/src/js/hr_leave_12hr.js',
    'hagbes_timeoff_management/static/src/css/calendar_holiday.css',
    'hagbes_timeoff_management/static/src/css/timeoff.css',
     'hagbes_timeoff_management/static/src/css/wizard.scss',



],
       'web.assets_qweb': [
           'hagbes_timeoff_management/static/src/xml/timeoff_dashboard_template_view.xml',
       ],

    },
    'installable': True,
    'application': False,
}
