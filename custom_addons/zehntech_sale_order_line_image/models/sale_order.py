from odoo import fields, models, api

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    show_product_image_setting = fields.Boolean(
        compute='_compute_show_product_image_setting',
        help="Technical field to control image column visibility"
    )

    @api.depends('order_line.product_id', 'order_line.is_downpayment')
    def _compute_show_product_image_setting(self):
        show_image = self.env['ir.config_parameter'].sudo().get_param(
            'sale_order_line_image.show_product_image_sale_order', False)
        for order in self:
            # Hide column if all lines are downpayment lines
            has_product_lines = any(not line.is_downpayment for line in order.order_line)
            order.show_product_image_setting = bool(show_image) and has_product_lines

class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    product_image = fields.Binary(related='product_id.image_128', readonly=True, string="Product Image")
    show_product_image = fields.Boolean(compute='_compute_show_product_image')
    
    @api.depends('product_id', 'is_downpayment')
    def _compute_show_product_image(self):
        show_image = self.env['ir.config_parameter'].sudo().get_param(
            'sale_order_line_image.show_product_image_sale_order', False)
        for line in self:
            line.show_product_image = bool(show_image) and not line.is_downpayment
