from odoo import models, fields, api


class ProductCategory(models.Model):
    _inherit = 'product.category'
    
    formula_id = fields.Many2one(
        'product.formula',
        string='Formula',
        help='Formula to calculate the price of products in this category.'
    )
    image_1920 = fields.Binary()
    image_url_1920 = fields.Char(string='Image URL 1920', compute='_compute_image_urls')
    
    @api.depends('image_1920')
    def _compute_image_urls(self):
        for category in self:
            if category.image_1920:
                category.image_url_1920 = f'/web/image/product.category/{category.id}/image_1920'
            else:
                category.image_url_1920 = False
    