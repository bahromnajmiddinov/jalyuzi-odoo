from odoo import models, fields, api, _


class ResUser(models.Model):
    _inherit = 'res.users'

    is_delivery_person = fields.Boolean(string='Is Delivery Person', default=False)
    total_sales = fields.Float(string='Total Sales', default=0.0, compute='_compute_total_sales')
    total_orders = fields.Integer(string='Total Orders', default=0, compute='_compute_total_orders')
    pending_orders = fields.Integer(string='Pending Orders', default=0, compute='_compute_total_orders')
    delivered_orders = fields.Integer(string='Delivered Orders', default=0, compute='_compute_total_orders')
    cancelled_orders = fields.Integer(string='Cancelled Orders', default=0, compute='_compute_total_orders')
    total_payments = fields.Float(string='Total Payments', default=0.0, compute='_compute_total_payments')
    profit_percentage = fields.Float(string='Profit Percentage', default=0.0)
    sale_debt = fields.Float(string='Sale Debt', default=0.0, compute='_compute_debt_amount')
    sale_debt_limit = fields.Float(string='Sale Debt Limit', default=0.0)
    image_1920_url = fields.Char(string='Image URL', compute='_compute_image_url')
    sale_order_ids = fields.One2many('sale.order', 'user_id', string='Sale Orders')
    
    # Performance Metrics
    delivery_success_rate = fields.Float(string='Delivery Success Rate', compute='_compute_delivery_success_rate')
    cancellation_rate = fields.Float(string='Cancelation Rate', compute='_compute_cancelation_rate')
    
    @api.depends('delivered_orders', 'total_orders')
    def _compute_delivery_success_rate(self):
        for user in self:
            if user.total_orders > 0:
                user.delivery_success_rate = (user.delivered_orders / user.total_orders) * 100
            else:
                user.delivery_success_rate = 0

    @api.depends('cancelled_orders', 'total_orders')
    def _compute_cancelation_rate(self):
        for user in self:
            if user.total_orders > 0:
                user.cancellation_rate = (user.cancelled_orders / user.total_orders) * 100
            else:
                user.cancellation_rate = 0

    @api.depends('sale_order_ids')
    def _compute_total_orders(self):
        for user in self:
            if user.sale_order_ids:
                total_orders = len(user.sale_order_ids)
                pending_orders = sum(1 for order in user.sale_order_ids if order.state == 'draft')
                delivered_orders = sum(1 for order in user.sale_order_ids if order.state == 'done')
                cancelled_orders = sum(1 for order in user.sale_order_ids if order.state == 'cancel')
            else:
                total_orders = pending_orders = delivered_orders = cancelled_orders = 0
                
            user.total_orders = total_orders
            user.pending_orders = pending_orders
            user.delivered_orders = delivered_orders
            user.cancelled_orders = cancelled_orders

    @api.depends('image_1920')
    def _compute_image_url(self):
        for user in self:
            user.image_1920_url = user._get_image_url('image_1920')
    
    def _get_image_url(self, field_name):
        self.ensure_one()
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        if getattr(self, field_name):
            return f"/my/image/res.users/{self.id}/{field_name}"
        return False
    
    @api.depends('sale_order_ids.amount_total')
    def _compute_total_sales(self):
        for user in self:
            if user.sale_order_ids:
                total_sales = sum(user.sale_order_ids.mapped('amount_total'))
            else:
                total_sales = 0.0
            user.total_sales = total_sales
            
    @api.depends('sale_order_ids.paid_amount')
    def _compute_total_payments(self):
        for user in self:
            if user.sale_order_ids:
                total_payments = sum(user.sale_order_ids.mapped('paid_amount'))
            else:
                total_payments = 0.0
            user.total_payments = total_payments
            
    @api.depends('total_sales', 'total_payments')
    def _compute_debt_amount(self):
        for user in self:
            debt = (user.total_sales or 0.0) - (user.total_payments or 0.0)
            user.sale_debt = debt
            