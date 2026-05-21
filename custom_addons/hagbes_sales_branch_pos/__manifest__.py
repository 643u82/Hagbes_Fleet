{
    "name": "Sales: Branch & POS Print",
    "version": "1.0",
    "depends": ["sale_management", "account","hagbes_employee_registration","hagbes_inventory_extension","hagbes_contact_tin_vat","stock","hagbes_invoice_extension"],
    "author": "Anteneh",
    "category": "Sales",
    "summary": "Adds branch selection and POS printing to sales invoices",
    "data": [
        "security/group.xml",
        "security/sale_branch_rules.xml",
        "views/sale_order_views.xml",
        'views/sale_order_pricelist_restriction.xml',
        'views/product_cost_hide.xml',
        'views/selected_warehouse_only.xml',
        'views/report_layout.xml'
        # "security/ir.model.access.csv",
        # 'views/lost_sale_views.xml',
        # 'views/sale_confirmation_wizard_views.xml',
        # 'views/lost_sale_notification_wizard_view.xml',
       

        
        
    ],
    "installable": True,
    "application": False
}
