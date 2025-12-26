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
    parent_product_id = fields.Many2one('product.product', string='Parent Product')
    
    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        for line in lines:
            if line.product_id and line.product_id.optional_product_ids:
                line._auto_add_optional_products()
        return lines
    
    def write(self, vals):
        result = super().write(vals)
        # If product changed, check for optional products
        if 'product_id' in vals:
            for line in self:
                if line.product_id and line.product_id.optional_product_ids:
                    line._auto_add_optional_products()
        return result
    
    def _auto_add_optional_products(self):
        """Auto-add optional products that have is_auto_add enabled"""
        self.ensure_one()
        
        for optional_product in self.product_id.optional_product_ids:
            if optional_product.is_auto_add:
                # Check if this optional product is already added
                existing_line = self.order_id.order_line.filtered(
                    lambda l: l.product_id == optional_product and 
                    l.parent_product_id == self.product_id and
                    l.id != self.id
                )
                
                if not existing_line:
                    # Create new line for optional product
                    new_line_vals = {
                        'product_id': optional_product.id,
                        'order_id': self.order_id.id,
                        'parent_product_id': self.product_id.id,
                        'product_uom_qty': 1,
                    }
                    
                    # If use_parent_dimensions is True and parent has dimensions, calculate automatically
                    if optional_product.use_parent_dimensions and optional_product.formula_id:
                        if self.width and self.height:
                            new_line_vals.update({
                                'width': self.width,
                                'height': self.height,
                                'count': self.count if self.count else 1,
                                'take_remains': self.take_remains,
                            })
                            
                            # Create the line first
                            new_line = self.create(new_line_vals)
                            
                            # Then calculate the formula
                            new_line._calculate_formula_for_optional()
                    else:
                        self.create(new_line_vals)
    
    def _calculate_formula_for_optional(self):
        """Calculate formula for optional product with parent dimensions"""
        self.ensure_one()
        
        if not self.product_id.formula_id:
            return
        
        wizard = self.env['product.formula.wizard'].create({
            'order_line_id': self.id,
            'product_id': self.product_id.id,
            'formula_id': self.product_id.formula_id.id,
            'width': self.width,
            'height': self.height,
            'count': self.count if self.count else 1,
            'take_remains': self.take_remains,
        })
        
        wizard.apply_formula()
    
    def _update_optional_products_dimensions(self):
        """Update dimensions of optional products when parent dimensions change"""
        self.ensure_one()
        
        # Find all optional products that belong to this parent
        optional_lines = self.order_id.order_line.filtered(
            lambda l: l.parent_product_id == self.product_id and 
            l.product_id.use_parent_dimensions and
            l.id != self.id
        )
        
        for line in optional_lines:
            line.write({
                'width': self.width,
                'height': self.height,
                'count': self.count,
                'take_remains': self.take_remains,
            })
            
            # Recalculate formula if product has one
            if line.product_id.formula_id:
                line._calculate_formula_for_optional()
    
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
            raise ValidationError(_("Product does not have formula!"))
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'product.formula.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_order_line_id': self.id,
                'default_product_id': self.product_id.id,
                'default_formula_id': self.product_id.formula_id.id,
                'default_width': self.width,
                'default_height': self.height,
                'default_count': self.count if self.count else 1,
                'default_take_remains': self.take_remains,
            }
        }
    
    def action_show_measurement(self):
        self.ensure_one()
        
        if not self.product_id.formula_id:
            raise ValidationError(_("Product does not have formula!"))
        
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
        