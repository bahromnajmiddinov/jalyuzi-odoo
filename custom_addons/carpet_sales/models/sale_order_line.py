from odoo import models, fields, api


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    carpet_qty = fields.Float(
        string='Carpet Quantity',
        default=1.0,
        digits=(10, 2)
    )

    is_carpet = fields.Boolean(
        related='product_id.is_carpet',
        string='Is Carpet',
        store=True
    )

    carpet_width = fields.Float(
        related='product_id.carpet_width',
        string='Width (m)',
        store=True
    )

    carpet_height = fields.Float(
        related='product_id.carpet_height',
        string='Height (m)',
        store=True
    )

    carpet_area = fields.Float(
        string='Total Area (m²)',
        compute='_compute_carpet_total_area',
        store=True,
        digits=(10, 4)
    )

    @api.depends('carpet_width', 'carpet_height', 'carpet_qty', 'is_carpet')
    def _compute_carpet_total_area(self):
        for line in self:
            if line.is_carpet:
                line.carpet_area = line.carpet_width * line.carpet_height * line.carpet_qty
                line.product_uom_qty = line.carpet_area
            else:
                line.carpet_area = 0.0
