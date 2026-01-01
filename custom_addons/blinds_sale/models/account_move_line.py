from odoo import models, fields


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    height = fields.Float(string='Height', default=0)
    width = fields.Float(string='Width', default=0)
    count = fields.Integer(string='Count', default=0)
    take_remains = fields.Boolean(
        string='Take Remains',
        default=False,
        help="If checked, the line will take into account the remaining stock of the product."
    )
