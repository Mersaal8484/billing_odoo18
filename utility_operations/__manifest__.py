{
    'name': 'Utility Operations',
    'version': '16.0.1.0.0',
    'category': 'Utility ERP',
    'summary': 'Field Operations & Service Order Management',
    'description': """
Enterprise Utility Operations Module
======================================
Field operations, service orders, work orders,
installations, inspections, maintenance, tamper management,
and alarm monitoring.

Models: Service Order, Installation, Removal, Replacement,
Inspection, Disconnection, Reconnection, Tamper Case,
Maintenance, Alarm, Work Order.
    """,
    'author': 'Utility ERP Platform',
    'website': 'https://www.utility-erp.com',
    'license': 'LGPL-3',
    'depends': ['utility_core', 'utility_inventory', 'maintenance', 'stock', 'mail'],
    'data': [
        'security/ir.model.access.csv',
        'security/utility_operations_security.xml',
        'data/utility_sequence.xml',
        'data/utility_cron.xml',
        'data/utility_operations_data.xml',
        'views/utility_service_order_views.xml',
        'views/utility_installation_views.xml',
        'views/utility_inspection_views.xml',
        'views/utility_tamper_views.xml',
        'views/utility_alarm_views.xml',
        'views/utility_work_order_views.xml',
        'views/meter_replace_views.xml',
        'views/reading_settlement_views.xml',
        'views/utility_customer_lifecycle_views.xml',
        'views/utility_operations_menu.xml',
    ],
    'demo': ['data/utility_demo.xml'],
    'installable': True,
    'application': True,
    'auto_install': False,
    'sequence': 2,
}
