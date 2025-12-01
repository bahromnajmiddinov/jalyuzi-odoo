from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    show_product_image_sale_order = fields.Boolean(
        string="Show Product Image in Sales Order",
        config_parameter='sale_order_line_image.show_product_image_sale_order',
        help="Display product images in sales order lines"
    )
    
    show_product_image_invoice = fields.Boolean(
        string="Show Product Image in Invoice",
        config_parameter='sale_order_line_image.show_product_image_invoice',
        help="Display product images in invoice lines"
    )
    