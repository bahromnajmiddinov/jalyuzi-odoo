from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'
    
    # KPI fields
    kpi_employee_id = fields.Many2one('hr.employee')
    is_kpi_product = fields.Boolean(default=False)
    
    height = fields.Float(default=0)
    width = fields.Float(default=0)
    count = fields.Integer(default=0)
    take_remains = fields.Boolean(
        'Take Remains',
        default=False,
        help="If checked, the order line will take into account the remaining stock of the product."
    )
    parent_line_id = fields.Many2one(
        'sale.order.line',
        string='Parent Line',
        ondelete='cascade'
    )
    
    def _auto_add_optional_products(self):
        self.ensure_one()

        template = self.product_id.product_tmpl_id

        for opt_tmpl in template.optional_product_ids.filtered('is_auto_add'):
            optional_product = opt_tmpl.product_variant_id

            exists = self.order_id.order_line.filtered(
                lambda l: l.parent_line_id == self and l.product_id == optional_product
            )
            if exists:
                continue

            new_line = self.env['sale.order.line'].create({
                'order_id': self.order_id.id,
                'product_id': optional_product.id,
                'parent_line_id': self.id,
                'width': self.width,
                'height': self.height,
                'count': self.count,
                'take_remains': self.take_remains,
            })

            if optional_product.use_parent_dimensions and optional_product.formula_id:
                new_line._calculate_formula_for_optional()
    
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
        self.ensure_one()

        optionals = self.order_id.order_line.filtered(
            lambda l: l.parent_line_id == self
        )

        for line in optionals:
            line.write({
                'width': self.width,
                'height': self.height,
                'count': self.count,
                'take_remains': self.take_remains,
            })

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
    
    def action_add_optional_products(self):
        self._auto_add_optional_products()
    
    def action_calculate_optional_products_formula(self):
        self._update_optional_products_dimensions()
         