from odoo import models, fields, api


class ProductCategory(models.Model):
    _inherit = 'product.category'
    
    formula_id = fields.Many2one(
        'product.formula',
        string='Formula',
        help='Formula to calculate the price of products in this category.'
    )
    image_1920 = fields.Binary()
    