from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

import json, math, ast


class ProductFormula(models.Model):
    _name = 'product.formula'
    _description = 'Custom Price Formulas for Products'

    name = fields.Char('Formula Name', required=True)
    formula = fields.Text('Python Formula', help='e.g., (width * height) * base_price')
    remains_formula = fields.Text('Remains Formula', help='e.g., (width * height) * base_price if take_remains else 0')
    available_fields = fields.Text('Available Fields', help='e.g., width, height, base_price, base_width, base_height, max, count, floor')
    active = fields.Boolean('Active', default=True)
    is_for_price = fields.Boolean('Is for Price', default=False, help='If checked, result will be set to price_unit instead of quantity')
    
    @api.constrains('formula')
    def _check_formula_safety(self):
        allowed_keywords = {'width', 'height', 'base_price', 'ceil', 
                            'floor', 'sqrt', 'base_width', 'base_height', 
                            'max', 'count', 'floor'}
        for formula in self:
            try:
                parsed = ast.parse(formula.formula, mode='eval')
                for node in ast.walk(parsed):
                    if isinstance(node, ast.Name) and node.id not in allowed_keywords:
                        raise ValidationError(_("Unsafe variable '%s' in formula") % node.id)
            except SyntaxError as e:
                raise ValidationError(_("Invalid formula syntax: %s") % str(e))


class ProductFormulaWizard(models.TransientModel):
    _name = 'product.formula.wizard'
    _description = 'Wizard to Apply Product Formula'

    order_line_id = fields.Many2one('sale.order.line')
    formula_id = fields.Many2one('product.formula', required=True)
    formula_price_id = fields.Many2one('product.formula')
    product_id = fields.Many2one('product.product', required=True)
    result = fields.Float(readonly=True)
    price_result = fields.Float(readonly=True)
    
    width = fields.Float(required=True)
    height = fields.Float(required=True)
    count = fields.Float(required=True, default=1)
    take_remains = fields.Boolean(
        'Take Remains',
        default=False,
        help="If checked, the order line will take into account the remaining stock of the product."
    )
    
    def apply_formula(self, id=None):
        if id:
            self = self.browse(id)
        
        self.ensure_one()
        try:
            # Choose the right formula
            if self.formula_id:
                if self.take_remains:
                    formula = self.formula_id.remains_formula
                else:
                    formula = self.formula_id.formula
            
            # Create safe evaluation environment
            allowed_vars = {
                'base_width': self.product_id.width,
                'base_height': self.product_id.height,
                'width': self.width,
                'height': self.height,
                'base_price': self.product_id.list_price,
                'sqrt': math.sqrt,
                'ceil': math.ceil,
                'floor': math.floor,
                'max': max,
                'count': self.count,
                'if': lambda condition, true_val, false_val: true_val if condition else false_val,
                'else': lambda condition, true_val, false_val: true_val if not condition else false_val,
            }
            
            if formula in [None, False]:
                self.result = 0
            else:
                self.result = eval(formula, {'__builtins__': None}, allowed_vars)
            
            if self.formula_price_id:
                self.price_result = eval(self.formula_price_id, {'__builtins__': None}, allowed_vars)

            # Update order line if present
            if self.order_line_id:
                update_vals = {
                    'height': self.height,
                    'width': self.width,
                    'count': self.count,
                    'take_remains': self.take_remains,
                }
                
                # Check if formula is for price or quantity
                if self.formula_id.is_for_price:
                    # Set result to unit price
                    update_vals['price_unit'] = self.result
                else:
                    # Set result to quantity
                    update_vals['product_uom_qty'] = self.result
                
                if self.price_result:
                    update_vals['price_unit'] = self.price_result

                self.order_line_id.write(update_vals)
                
                # Update optional products with parent dimensions
                self.order_line_id._update_optional_products_dimensions()
            
            return self.result
        except Exception as e:
            raise UserError(_("Formula Error: %s") % str(e))
        

class ProductMeasurementWizard(models.TransientModel):
    _name = 'product.measurement.wizard'
    _description = 'Wizard to Set Product Measurements'

    order_line_id = fields.Many2one('sale.order.line')
    product_id = fields.Many2one('product.product', required=True)
    formula_id = fields.Many2one('product.formula', required=True)
    width = fields.Float(required=True)
    height = fields.Float(required=True)
    count = fields.Float(required=True)
    take_remains = fields.Boolean(
        'Take Remains', 
        default=False, 
        help='If checked, the formula will consider the remaining stock for calculations.'
    )
    