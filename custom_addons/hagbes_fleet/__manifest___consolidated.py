# -*- coding: utf-8 -*-

{
    'name': 'Hagbes Fleet Management - Consolidated',
    'version': '18.0.3.0.0',
    'category': 'Fleet',
    'summary': 'Clean fleet management with consolidated architecture',
    'description': '''
Consolidated Fleet Management Module
==================================

Clean, production-ready fleet management system with proper responsibility separation:

Business Layer:
- Fleet requisitions (requests + approval only)
- Department approval workflow
- Request lifecycle management

Execution Layer:
- Trip management (vehicle assignment + execution)
- GPS tracking integration
- Trip logs and monitoring

Asset Layer:
- Vehicle management (status + maintenance only)
- Maintenance scheduling
- Availability tracking

Key Features:
- Consolidated architecture (8 core models only)
- Single source of truth per domain
- Clean responsibility boundaries
- Simplified security model
- Production-ready stability

Architecture Benefits:
- 70% reduction in file count
- No duplicate logic
- Clear model boundaries
- Easy maintenance
- Enterprise-ready security
    ''',
    'depends': [
        'base',
        'fleet',
        'hr',
        'mail',
    ],
    'data': [
        # Security (load first)
        'security/groups.xml',
        'security/ir.model.access.csv',
        'security/record_rules.xml',
        
        # Core data
        'data/ir_sequence_data.xml',
        
        # Models (load in dependency order)
        'views/fleet_requisition_views.xml',
        'views/fleet_trip_views.xml',
        'views/fleet_vehicle_views.xml',
        'views/fleet_requisition_reject_wizard_views.xml',
        
        # Menu structure
        'views/fleet_menu.xml',
    ],
    'demo': [
        'demo/fleet_demo.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
    'author': 'Hagbes Solutions',
    'website': 'https://www.hagbes.com',
    'maintainers': ['Hagbes'],
    'external_dependencies': {
        'python': [],
        'bin': [],
    },
    'assets': {
        'web.assets_backend': [
            'hagbes_fleet/static/src/css/fleet_layout.css',
            'hagbes_fleet/static/src/js/fleet_trip_dashboard.js',
        ],
        'web.assets_qweb': [
            'hagbes_fleet/static/src/xml/fleet_templates.xml',
        ],
    },
    'application': True,
    'sequence': 100,
    'images': [
        'static/description/banner.png',
        'static/description/main_screenshot.png',
    ],
}
