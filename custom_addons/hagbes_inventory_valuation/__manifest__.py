{
    'name': 'Hagbes Inventory Valuation',
    'version': '18.0.1.0.0',
    'category': 'Inventory/Inventory',
    'summary': 'Complete Enterprise Stock Valuation Features for Community Edition',
    'description': """
        This module adds ALL enterprise inventory valuation features:
        ✓ Automatic/Manual inventory valuation per category
        ✓ Stock Valuation Account configuration
        ✓ Stock Journal for valuation entries
        ✓ Stock Input/Output accounts per category
        ✓ Price Difference Account for purchase price variances
        ✓ Location-based stock accounts (override category defaults)
        ✓ Automatic journal entries for stock movements
        ✓ Full integration with accounting module
        
        Works with any Odoo 18 Community accounting module.
    """,
    'author': 'Mr-solomno',
    
    'depends': [
        'base',
        'stock',
        'account',
        'product',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/account_data.xml',
        'views/product_category_views.xml',
        'views/stock_location_views.xml',
    ],
    'demo': [],
    'installable': True,
    'auto_install': False,
    'application': False,
    'license': 'LGPL-3',
    'sequence': 1000,  
}
