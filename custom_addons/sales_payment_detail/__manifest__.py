{
    'name': 'Sales Payment Detail',
    'version': '1.0',
    'category': 'Sales',
    'summary': 'Module to enhance sales payment details',
    'description': """
        This module provides additional details for sales payments,
        allowing better tracking and management of payment information.
    """,
    'author': 'DevoSoft LLC',
    'website': 'https://www.devosoft.uz',
    'depends': ['sale', 'account'],
    'data': [
        'views/sale_order_views.xml',
        'views/res_partner_views.xml'
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}