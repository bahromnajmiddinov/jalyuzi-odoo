from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    payment_proof_ids = fields.One2many(
        'payment.proof', 'sale_order_id', string='Payment Proofs',
        help='List of payment proofs associated with this sale order.'
    )
    
    def action_create_invoice(self):
        self.ensure_one()
        self._create_invoices()
        return self.invoice_ids.ids
    
    @api.model
    def create(self, vals_list):
        if not vals_list.get('access_token'):
            import uuid
            vals_list['access_token'] = str(uuid.uuid4())
        
        return super().create(vals_list)


class PaymentProof(models.Model):
    _name = 'payment.proof'
    _description = 'Payment Proof'
    _order = 'payment_date desc'

    name = fields.Char(string='Reference', required=True, 
                      default=lambda self: self.env['ir.sequence'].next_by_code('payment.proof'))
    payment_date = fields.Datetime(string='Payment Date', required=True, default=fields.Datetime.now)
    amount = fields.Float(string='Amount', required=True)
    currency_id = fields.Many2one('res.currency', string='Currency', 
                                 default=lambda self: self.env.company.currency_id)
    sale_order_id = fields.Many2one('sale.order', string='Sale Order', required=True)
    payment_method_id = fields.Many2one('account.payment.method', string='Payment Method', required=True)
    journal_id = fields.Many2one('account.journal', string='Payment Journal',
                                domain="[('type', 'in', ('bank', 'cash'))]")
    proof_image = fields.Binary(string='Proof Image', attachment=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('verified', 'Verified'),
        ('rejected', 'Rejected'),
        ('processed', 'Processed'),
    ], string='Status', default='draft', tracking=True)
    notes = fields.Text(string='Admin Notes')
    invoice_id = fields.Many2one('account.move', string='Linked Invoice')
    partner_id = fields.Many2one('res.partner', related='sale_order_id.partner_id', store=True)
    
    # SQL Constraints must be class-level attributes
    _sql_constraints = [
        ('amount_positive', 'CHECK(amount > 0)', 'Payment amount must be positive'),
    ]
    
    # Constraint methods must be class-level methods
    @api.constrains('journal_id', 'payment_method_id')
    def _check_journal_method(self):
        for proof in self:
            if proof.payment_method_id.id not in proof.journal_id.inbound_payment_method_line_ids.payment_method_id.ids:
                raise ValidationError(_("Payment method not allowed for selected journal"))
    
    def action_verify(self):
        if any(proof.state not in ('draft','submitted') for proof in self):
            raise UserError(_("Only draft/submitted proofs can be verified"))
        self.write({'state': 'verified'})

    def action_reject(self):
        allowed_states = ('draft','submitted','verified')
        if any(proof.state not in allowed_states for proof in self):
            raise UserError(_("Cannot reject in current state"))
        self.write({'state': 'rejected'})
    
    def action_create_invoice(self):
        self.ensure_one()
        
        if self.state != 'verified':
            raise UserError(_("Only verified proofs can be invoiced"))

        if not self.journal_id:
            raise UserError(_("Please select a payment journal."))

        sale_order = self.sale_order_id

        # Use or create a simple down payment product
        product = self.env['product.product'].search([('name', '=', 'Down Payment')], limit=1)
        if not product:
            product = self.env['product.product'].create({
                'name': 'Down Payment',
                'type': 'service',
                'invoice_policy': 'order',
                'sale_ok': True,
                'purchase_ok': False,
                'list_price': 0.0,
            })

        income_account = product.property_account_income_id or \
                        product.categ_id.property_account_income_categ_id
        if not income_account:
            raise UserError(_("Please configure an income account on the product or its category."))

        # Create the invoice manually
        invoice = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': sale_order.partner_id.id,
            'invoice_origin': sale_order.name,
            'invoice_date': fields.Date.context_today(self),
            'invoice_line_ids': [(0, 0, {
                'name': f"Payment Proof: {self.name}",
                'quantity': 1.0,
                'price_unit': self.amount,
                'product_id': product.id,
                'account_id': income_account.id,
            })],
        })

        invoice.action_post()

        # Register payment without payment_method_id
        payment_register = self.env['account.payment.register'].with_context(
            active_model='account.move',
            active_ids=[invoice.id]
        ).create({
            'amount': min(self.amount, invoice.amount_residual),
            'payment_date': self.payment_date,
            'journal_id': self.journal_id.id,
            'currency_id': self.currency_id.id,
        })
        payment_register.action_create_payments()

        # Finalize
        self.write({
            'invoice_id': invoice.id,
            'state': 'processed',
        })
