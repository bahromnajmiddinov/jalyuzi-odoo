from odoo import models, fields, api
from odoo.tools import float_compare

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    company_currency_id = fields.Many2one('res.currency', related='company_id.currency_id', string='Company Currency', readonly=True)
    amount_invoiced = fields.Monetary(string='Amount Invoiced', compute='_compute_payment_info', currency_field='company_currency_id')
    amount_paid = fields.Monetary(string='Amount Paid', compute='_compute_payment_info', currency_field='company_currency_id')
    payment_state = fields.Selection(
        [
            ('no_invoices', 'No Invoices'),
            ('not_paid', 'Not Paid'),
            ('partial', 'Partially Paid'),
            ('paid', 'Paid'),
        ],
        string='Payment Status',
        compute='_compute_payment_info',
        store=True,
    )

    @api.depends('invoice_ids.state', 'invoice_ids.amount_total', 'invoice_ids.amount_residual', 'invoice_ids.currency_id', 'company_id')
    def _compute_payment_info(self):
        for order in self:
            invoices = order.invoice_ids.filtered(lambda inv: inv.move_type in ('out_invoice', 'out_refund') and inv.state != 'cancel')
            total_invoiced = 0.0
            total_paid = 0.0
            for inv in invoices:
                # convert invoice amounts to company currency using invoice date (fallback to today)
                date = inv.invoice_date or inv.date or fields.Date.context_today(self)
                amount_total = inv.currency_id._convert(inv.amount_total, order.company_currency_id, inv.company_id, date)
                amount_residual = inv.currency_id._convert(inv.amount_residual, order.company_currency_id, inv.company_id, date)
                total_invoiced += amount_total
                total_paid += (amount_total - amount_residual)

            order.amount_invoiced = total_invoiced
            order.amount_paid = total_paid

            if not invoices:
                order.payment_state = 'no_invoices'
            else:
                # compare with small tolerance using float_compare
                if float_compare(total_paid, 0.0, precision_digits=2) == 0:
                    order.payment_state = 'not_paid'
                elif float_compare(total_paid, total_invoiced, precision_digits=2) >= 0:
                    order.payment_state = 'paid'
                else:
                    order.payment_state = 'partial'
                    