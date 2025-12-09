# -*- coding: utf-8 -*-
{
    'name': 'Blinds Sale',
    'summary': 'Manage blinds sale',
    'description': """
Manage blinds sale
    """,
    'category': 'Website/Website',
    'version': '1.0',
    'depends': ['sale', 'hr', 'sales_invoice_detail', 'zehntech_sale_order_line_image',
                'owl_sale_order_dashboard'],
    'data': [
        'security/ir.model.access.csv',
        'views/formula_view.xml',
        'views/product_formula_wizard_view.xml',
        'views/order_line_view.xml',
        'views/product_template_views.xml',
        'views/hr_employee_view.xml',
        'views/res_user_views.xml',
    ],
    'auto_install': True,
    'license': 'LGPL-3',
    'installable': True,
    'application': True,
}
