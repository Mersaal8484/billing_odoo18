{
    'name': 'Utility Inventory',
    'version': '16.0.1.1.0',
    'category': 'Utility ERP',
    'summary': 'Inventory & Warehouse Management Integration',
    'description': """
Utility Inventory Integration Module
====================================
Integrates Utility Core meters with standard Odoo Stock and Product modules.
Adds lot/serial tracking and product association for physical meters.
    """,
    'author': 'Utility ERP Platform',
    'website': 'https://www.utility-erp.com',
    'license': 'LGPL-3',
    'depends': ['utility_core', 'stock', 'product'],
    'data': [
        'security/ir.model.access.csv',
        'data/utility_inventory_data.xml',
        'data/utility_inventory_product_data.xml',
        'data/utility_cron.xml',
        'views/utility_meter_inventory_views.xml',
        'wizards/views/utility_customer_wizard_inventory_views.xml',
    ],
    'demo': [],
    'installable': True,
    'application': True,
    'auto_install': False,
    'sequence': 2,
}
