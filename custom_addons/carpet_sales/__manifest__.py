{
    'name': 'Carpet Sales',
    'version': '18.0.1.0.0',
    'category': 'Sales',
    'summary': 'Carpet sales with area-based pricing',
    'description': '''
        Carpet Sales Module
        ====================
        - Store carpet width and height on products
        - Calculate price based on area (width × height × price per sqm)
        - Automatic price calculation in sales order lines
    ''',
    'author': 'Bahrom Najmiddinov',
    'depends': ['sale_management', 'product'],
    'data': [
        'views/product_template_views.xml',
        'views/sale_order_views.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
