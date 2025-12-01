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
    product_id = fields.Many2one('product.product', required=True)
    result = fields.Float(readonly=True)
    
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
            if self.take_remains:
                formula = self.formula_id.formula
            else:
                formula = self.formula_id.remains_formula
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
            self.result = eval(formula, {'__builtins__': None}, allowed_vars)
            # from_ui = self.env.context.get('from_ui', False)
            if self.order_line_id:
                self.order_line_id.product_uom_qty = self.result
                self.order_line_id.height = self.height
                self.order_line_id.width = self.width
                self.order_line_id.count = self.count
                self.order_line_id.take_remains = self.take_remains
            # if from_ui:
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
        'Take Remains' , 
        default=False, 
        help='If checked, the formula will consider the remaining stock for calculations.'
    )
    