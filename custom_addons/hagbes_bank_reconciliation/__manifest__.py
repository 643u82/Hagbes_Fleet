{
    "name": "Bank Reconciliation (Agresso)",
    "summary": "Bank reconciliation by month with Agresso ledger transactions",
    "version": "18.0.1.0.0",
    "category": "Accounting",
    "author": "Hagbes",
    "website": "https://hagbes.com",
    "license": "LGPL-3",
    "depends": ["base"],
    "data": [
        "report/bank_reco_report.xml",
        "views/bank_reco_views.xml",
        "security/groups.xml",
        "views/menu.xml",
        'data/ir_cron.xml',
        "security/ir.model.access.csv",
        'security/record_rules.xml'
    ],
    "application": True,
    "installable": True,
}
