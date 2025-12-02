from odoo import models, fields, api


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    height = fields.Float(default=0)
    width = fields.Float(default=0)
    formula_id = fields.Many2one(
        # 'product.formula',
        related='categ_id.formula_id',
        string='Custom Formula',
        help='Formula to compute price dynamically.'
    )
    profit_percentage = fields.Float()
    image_url_1920 = fields.Char(string='Image URL 1920', compute='_compute_image_urls')
    image_url_1024 = fields.Char(string='Image URL 1024', compute='_compute_image_urls')
    image_url_512 = fields.Char(string='Image URL 512', compute='_compute_image_urls')
    image_url_256 = fields.Char(string='Image URL 256', compute='_compute_image_urls')
    image_url_128 = fields.Char(string='Image URL 128', compute='_compute_image_urls')
        
    @api.depends('image_1920', 'image_1024', 'image_512', 'image_256', 'image_128')
    def _compute_image_urls(self):
        for product in self:
            product.image_url_1920 = product._get_image_url('image_1920')
            product.image_url_1024 = product._get_image_url('image_1024')
            product.image_url_512 = product._get_image_url('image_512')
            product.image_url_256 = product._get_image_url('image_256')
            product.image_url_128 = product._get_image_url('image_128')
    
    def _get_image_url(self, field_name):
        self.ensure_one()
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        if getattr(self, field_name):
            return f"{base_url}/web/image/product.template/{self.id}/{field_name}"
        return False
    
    @api.onchange('profit_percentage')
    def _onchange_profit_percentage(self):
        profit_percentage = self.profit_percentage
        standard_price = self.standard_price
        if profit_percentage and standard_price:
            self.list_price = standard_price + (standard_price * (profit_percentage / 100))
    