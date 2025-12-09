from odoo import models, fields, api


class ProductTemplate(models.Model):
    _inherit = 'product.template'
    
    is_carpet = fields.Boolean(string='Is Carpet', default=False)
    carpet_width = fields.Float(string='Width (m)', digits=(10, 2))
    carpet_height = fields.Float(string='Height (m)', digits=(10, 2))
    carpet_area = fields.Float(
        string='Area (m²)', 
        compute='_compute_carpet_area', 
        store=True,
        digits=(10, 4)
    )
    
    @api.depends('carpet_width', 'carpet_height')
    def _compute_carpet_area(self):
        for record in self:
            if record.is_carpet and record.carpet_width and record.carpet_height:
                record.carpet_area = record.carpet_width * record.carpet_height
            else:
                record.carpet_area = 0.0


class ProductProduct(models.Model):
    _inherit = 'product.product'
    
    is_carpet = fields.Boolean(related='product_tmpl_id.is_carpet', store=True)
    carpet_width = fields.Float(related='product_tmpl_id.carpet_width', store=True)
    carpet_height = fields.Float(related='product_tmpl_id.carpet_height', store=True)
    carpet_area = fields.Float(related='product_tmpl_id.carpet_area', store=True)
