{
    'name': 'Sales Order Production Management',
    'version': '18.0.1.0.0',
    'category': 'Sales/Sales',
    'summary': 'Manage production lifecycle for sales orders',
    'description': """
        Sales Order Production Management
        ==================================
        * Mark sales orders as ready for production
        * Track production start and end dates
        * Production status management
        * Production notes and comments
        * Integration with manufacturing workflow
    """,
    'author': 'Your Company',
    'website': 'https://www.yourcompany.com',
    'depends': ['sale_management', 'stock'],
    'data': [
        'security/ir.model.access.csv',
        'views/sale_order_views.xml',
        # 'views/production_dashboard_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
