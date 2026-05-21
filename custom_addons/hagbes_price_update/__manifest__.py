{
    'name': 'Hagbes Price Update',
    'version': '18.0.1.0.0',
    'category': 'Sales',
    'summary': 'Advanced selling price update with history tracking and bulk operations',
    'description': """
        Sales Price Update Module
        =========================
        
        Features:
        - Manual price update screen
        - Update by margin/percentage/fixed value
        - Product group rules and margin limits
        - Complete history tracking (audit log)
        - Bulk price update operations
        - Price comparison and analysis
        
        This module provides comprehensive tools for managing product selling prices
        with full audit trail and flexible update methods.
    """,
    'author': 'Hagbes IT',
   
       'depends': ['base', 'product', 'sale', 'purchase'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'views/product_price_update_wizard_views.xml',
        'views/product_group_views.xml',
        'views/product_price_history_views.xml',
        'views/product_template_views.xml',
        'views/price_update_views.xml',
        'views/menu_views.xml',  
        # 'data/demo_data.xml',


    ],
    'demo': [],
    'installable': True,
    'auto_install': False,
    'application': True,
    'license': 'LGPL-3',
}
