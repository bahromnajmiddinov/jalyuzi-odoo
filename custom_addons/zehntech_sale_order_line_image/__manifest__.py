{
    "name": "Sale Order Line Image",
    "summary": "Enhance your Odoo sales and invoicing workflow by displaying product images directly on sales order lines, quotations, and invoices with Sale Order Line Image Odoo App. Sale Order Line Image Odoo module improves clarity and professionalism in your documents, helping to reduce errors and build customer trust. Sale Order Image | Quotation Image | Invoice Product Image | Odoo Sales Enhancement | Product Image in PDF | Sale Order Line Image | Odoo Sale Order Customization | Product Image in Quotation | Invoice Line Image | Odoo Sales Order Reports",
    "description": """
        The Sale Order Line Image Odoo module enhances your Odoo sales and invoicing documents by embedding product images directly into quotations, sales orders, and invoices. This visual integration improves product identification, reduces errors, and creates a more professional customer experience. 
        Images appear both in the backend and on PDF reports, with easy configuration from Sales Settings. 
        It supports product variants, maintains clean formatting even when images are missing.
    """,
    "author": "Zehntech Technologies Inc.",
    "company": "Zehntech Technologies Inc.",
    "maintainer": "Zehntech Technologies Inc.",
    "contributor": "Zehntech Technologies Inc.",
    "website": "https://www.zehntech.com/",
    "support": "odoo-support@zehntech.com",
    "category": "Sales",
    "version": "18.0.1.0.0",
    "depends": ["sale_management", "account", "product"],
    "data": [
        "views/res_config_settings_views.xml",
        "views/sale_order_views.xml",
        "views/account_move_views.xml",
        "reports/sale_report_templates.xml",
        "reports/account_report_templates.xml",
        "reports/sale_portal_templates.xml",
    ],
    "images": ["static/description/banner.gif"],
    "license": "LGPL-3",
    "price": 0.00,
    "currency": "USD",
    "uninstall_hook": "uninstall_hook",
    "installable": True,
    "application": True,
    "auto_install": False,
}
