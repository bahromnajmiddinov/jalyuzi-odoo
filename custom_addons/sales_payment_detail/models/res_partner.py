from odoo import models, fields, api


class ResPartner(models.Model):
    _inherit = 'res.partner'

    total_amount_paid = fields.Monetary(string='Total Amount Paid', compute='_compute_total_invoiced', store=True)
    total_amount_remaining = fields.Monetary(string='Total Amount Remaining', compute='_compute_total_invoiced')
    is_debtor = fields.Boolean(default=False, compute="_compute_is_debtor", store=True)
    
    @api.depends('sale_order_ids.amount_invoiced', 'sale_order_ids.amount_paid')
    def _compute_total_invoiced(self):
        for partner in self:
            total_invoiced = sum(partner.sale_order_ids.mapped('amount_invoiced'))
            total_paid = sum(partner.sale_order_ids.mapped('amount_paid'))
            partner.total_amount_remaining = total_invoiced - total_paid
            partner.total_amount_paid = total_paid
    
    @api.depends('total_amount_remaining')
    def _compute_is_debtor(self):
        for partner in self:
            if partner.total_amount_remaining > 0:
                partner.is_debtor = True
            else:
                partner.is_debtor = False
    
    def action_view_partial_invoices(self):
        self.ensure_one()
        action = self.env.ref('account.action_move_out_invoice_type').read()[0]
        action['domain'] = [('partner_id', '=', self.id), ('move_type', 'in', ('out_invoice', 'out_refund')), ('payment_state', '=', 'partial')]
        action['context'] = {'default_partner_id': self.id, 'default_move_type': 'out_invoice'}
        return action
