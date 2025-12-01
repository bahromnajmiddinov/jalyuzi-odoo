from . import models

def uninstall_hook(env):
    """Remove config parameters on module uninstall"""
    env.cr.execute("DELETE FROM ir_config_parameter WHERE key IN ('sale_order_line_image.show_product_image_sale_order', 'sale_order_line_image.show_product_image_invoice')")
