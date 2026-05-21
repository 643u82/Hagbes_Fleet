{
    'name': 'Hagbes Procurement Management',
    'version': '18.0.1.0.0',
    'category': 'Purchase',
    'summary': 'Foreign Procurement Management System',
    'description': """
        Procurement Management System
        -------------------------------------
        
        This module provides management for procurement processes including:
        * Payment Requests Management
        * Bank Follow-up Process
        * Document Management
        * Accounting Integration
        * Foreign-specific RFQ and Purchase Orders
        * Vendor Management
        * Shipment and Transit Tracking
        * Landed Cost Management
        *Local Purchase  Management
    """,
    'author': '',
    'depends': [
        'base',
        'purchase',
        'purchase_stock',
        'account',
        'stock',
        'stock_landed_costs',
        'hagbes_approval_workflow',
        'hagbes_inventory_extension',
        'hagbes_price_update',
        # 'mail',
    ],
    'data': [
        # Security
        # 'security/groups.xml', 
        'security/foreign_procurement_security.xml',
        'security/ir.model.access.csv',
         'security/ir_rule.xml',
        
        # Settings
        # Data
        'data/sequence_data.xml',
       
        # Views
        'views/foreign_payment_request_views.xml',
        
        'views/foreign_lc_views.xml',
        'views/foreign_bank_process_views.xml',
        'views/foreign_shipment_views.xml',
        'views/foreign_document_views.xml',
        'views/purchase_order_views.xml',
        'views/foreign_costing_views.xml',
        'views/res_partner_views.xml',
        'views/foreign_transit_process_views.xml',
        'views/purchase_request_views.xml',
        # 'views/local_purchase_request_views.xml',
        # 'views/res_company_views.xml',
        'views/account_move_views.xml',
        'views/res_users_view.xml',
       # 'views/foreign_procurement_dashboard.xml',
        'views/leaflet_templates.xml',
        # Reports
        'reports/foreign_procurement_reports.xml',
        'reports/purchase_request_report.xml',
        'reports/payment_request_report.xml',
        'reports/lc_report.xml',
        'reports/shipment_report.xml',
        'views/manual_inventory_views.xml',
        'views/foreign_procurement_menus.xml',
        # 'views/local_procurement_menus.xml',
        'views/foreign_landing_views.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'https://unpkg.com/leaflet@1.7.1/dist/leaflet.css',
            '/hagbes_procurement_management/static/src/css/leaflet_custom.css',
            'https://unpkg.com/leaflet@1.7.1/dist/leaflet.js',
            '/hagbes_procurement_management/static/src/js/leaflet_tracking_frontend.js',
        ],
        'web.assets_backend': [
            'https://unpkg.com/leaflet@1.7.1/dist/leaflet.css',
            '/hagbes_procurement_management/static/src/css/leaflet_custom.css',
            'https://unpkg.com/leaflet@1.7.1/dist/leaflet.js',
           # '/hagbes_procurement_management/static/src/js/leaflet_tracking.js',
            # '/hagbes_procurement_management/static/src/js/transit_form_view_handler.js',
            '/hagbes_procurement_management/static/src/xml/leaflet_templates.xml',
        ],
    },
    'external_dependencies': {
        'python': ['websocket-client'],
    },
    'demo': [],
    'installable': True,
    'auto_install': False,
    'application': False,
    'license': 'LGPL-3',
}
