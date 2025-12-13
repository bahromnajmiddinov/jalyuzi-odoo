from odoo import models, fields, api, _
from odoo.exceptions import UserError

class ResPartner(models.Model):
    _inherit = "res.partner"
    
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        compute='_compute_currency_id',
        store=True,
    )
    
    vendor_due_amount = fields.Monetary(
        string="Amount to Pay",
        compute="_compute_vendor_due_amount",
        currency_field='currency_id',
        store=False,
    )
    
    # stored_vendor_due_amount = fields.Monetary(
    #     string="Amount to Pay",
    #     compute="_compute_vendor_due_amount_by_company",
    #     currency_field='currency_id',
    #     store=True,
    #     index=True,
    # )
    
    @api.depends('company_id')
    def _compute_currency_id(self):
        for rec in self:
            rec.currency_id = rec.company_id.currency_id or self.env.company.currency_id

    @api.depends('invoice_ids.amount_residual', 'invoice_ids.move_type', 'invoice_ids.payment_state')
    def _compute_vendor_due_amount(self):
        current_companies = self.env.companies
        for partner in self:
            vendor_bills = partner.invoice_ids.filtered(
                lambda inv: inv.move_type == 'in_invoice' and inv.payment_state != 'paid' and inv.company_id in current_companies
            )
            partner.vendor_due_amount = sum(vendor_bills.mapped('amount_residual'))
    
    # @api.depends('vendor_due_amount')
    # def _compute_vendor_due_amount_by_company(self):
    #     companies = self.env.companies
    #     for partner in self:
    #         vendor_bills = partner.invoice_ids.filtered(
    #             lambda inv: inv.move_type == 'in_invoice' and inv.payment_state != 'paid' and inv.company_id in companies
    #         )
    #         amount = sum(vendor_bills.mapped('amount_residual'))
    #         partner.stored_vendor_due_amount = amount
    