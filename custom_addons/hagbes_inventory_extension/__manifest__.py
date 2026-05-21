{
    'name': 'Hagbes Inventory Extension',
    'summary': "Inventory customization based on Hagbes requirements",
    'version': '18.0.1.0.0',
    'category': 'Inventory/Product',
    'depends': ['web','base','product', 'stock', 'analytic','hagbes_employee_registration','purchase','purchase_stock'],
    'data': [
        'security/ir_rules.xml',
        'security/accessgroup_security.xml',    # Groups first
        'security/ir.model.access.csv',       # Access rights next
        'data/interstock_transfer_sequence.xml',
        'views/product_category_views.xml',
        'views/product_view.xml',             # This is where your previous XML was
        'views/custom_stock_pick_list.xml',
        'views/stock_warehouse_view.xml',
        'views/interstock_transfer_view.xml',
        'views/interstock_transfer_menu.xml',
        'views/stock_quant.xml',
        'views/replenishment_custom_view.xml',
        'views/stock_view.xml',
        'views/stock_picking_delivery_order.xml',
        'views/issue_note.xml',
        'views/exhibition_request.xml',
        'views/exhibition_return_modal.xml',
        'views/picking_type_kanban.xml',
        'views/stock_request_count.xml',
        'views/stock_move_line.xml',
        'reports/inter_store.xml',
        'reports/grn.xml',
        'views/backorder_remark.xml',
        'views/issue_note_print.xml',
        'views/temporary_note_print.xml',
        'views/delivery_order_print.xml',
        'views/jobs_menu.xml'
    ],
    "assets": {
        'web.assets_backend': [
            'hagbes_inventory_extension/static/src/css/inter_stock.css',
            # 'hagbes_inventory_extension/static/src/js/hide_return_button.js',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}