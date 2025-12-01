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
    
    @api.onchange('profit_percentage')
    def _onchange_profit_percentage(self):
        profit_percentage = self.profit_percentage
        standard_price = self.standard_price
        if profit_percentage and standard_price:
            self.list_price = standard_price + (standard_price * (profit_percentage / 100))
    