from odoo import models, api, fields


class AccountMove(models.Model):
    _inherit = 'account.move'

    show_product_image_setting = fields.Boolean(
        compute='_compute_show_product_image_setting',
        help="Technical field to control image column visibility"
    )

    @api.depends('invoice_line_ids.is_downpayment', 'invoice_line_ids.product_id')
    def _compute_show_product_image_setting(self):
        show_image = self.env['ir.config_parameter'].sudo().get_param(
            'sale_order_line_image.show_product_image_invoice', False)
        for move in self:
            # Hide column if all lines are downpayment lines
            has_product_lines = any(not line.is_downpayment for line in move.invoice_line_ids)
            move.show_product_image_setting = bool(show_image) and has_product_lines

class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    product_image = fields.Binary(related='product_id.image_128', readonly=True, string="Product Image")
    show_product_image = fields.Boolean(compute='_compute_show_product_image')
    
    @api.depends('product_id', 'is_downpayment')
    def _compute_show_product_image(self):
        show_image = self.env['ir.config_parameter'].sudo().get_param(
            'sale_order_line_image.show_product_image_invoice', False)
        for line in self:
            line.show_product_image = bool(show_image) and not line.is_downpayment
