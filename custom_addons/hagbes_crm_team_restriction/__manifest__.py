# __manifest__.py
{
    'name': 'Hagbes CRM Team Restriction',
    'version': '1.0',
    'summary': 'Restrict Salesperson selection to team members and team leader',
    'description': """
        When assigning a salesperson in CRM, only show team members and the team leader.
        Applies dynamic domain filtering based on the selected sales team.
    """,
    'category': 'Sales/CRM',
    'author': 'Your Name',
    'depends': ['crm',"account","hagbes_employee_registration"],
    'data': [
        "security/security.xml",
        "security/groups.xml",
        "security/ir.model.access.csv",
        "security/rules.xml",
        'views/crm_company_filter.xml',
        'views/crm_lead_views.xml',
        'views/crm_team_views.xml',
        'views/crm_menus.xml',
        
        
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}