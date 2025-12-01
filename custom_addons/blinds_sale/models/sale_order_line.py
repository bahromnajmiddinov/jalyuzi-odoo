from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'
    
    height = fields.Float(default=0)
    width = fields.Float(default=0)
    count = fields.Integer(default=0)
    take_remains = fields.Boolean(
        'Take Remains',
        default=False,
        help="If checked, the order line will take into account the remaining stock of the product."
    )
    
    @api.depends('product_id.formula_id')
    def _compute_formula_applied(self):
        for record in self:
            if record.product_id.formula_id:
                record.formula_applied = True
            else:
                record.formula_applied = False
    
    def action_recalculate_formula(self):
        self.ensure_one()
        
        if not self.product_id.formula_id:
            raise ValidationError(_("Product do not have formula!"))
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'product.formula.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_order_line_id': self.id,
                'default_product_id': self.product_id.id,
                'default_formula_id': self.product_id.formula_id.id,
            }
        }
    
    def action_show_measurement(self):
        self.ensure_one()
        
        if not self.product_id.formula_id:
            raise ValidationError(_("Product do not have formula!"))
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'product.measurement.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_order_line_id': self.id,
                'default_product_id': self.product_id.id,
                'default_formula_id': self.product_id.formula_id.id,
                'default_width': self.width,
                'default_height': self.height,
                'default_count': self.count,
                'default_take_remains': self.take_remains,
            }
        }
    