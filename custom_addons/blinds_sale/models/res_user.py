from odoo import models, fields, api, _


class ResUser(models.Model):
    _inherit = 'res.users'

    is_delivery_person = fields.Boolean(string='Is Delivery Person', default=False)
    debt_amount = fields.Float(string='Debt Amount', default=0.0, compute='_compute_debt_amount')
    total_sales = fields.Float(string='Total Sales', default=0.0, compute='_compute_total_sales')
    total_payments = fields.Float(string='Total Payments', default=0.0, compute='_compute_total_payments')
    debt_limit = fields.Float(string='Debt Limit', default=0.0)
    profit_percentage = fields.Float(string='Profit Percentage', default=0.0)
    sale_debt = fields.Float(string='Sale Debt', default=0.0)
    sale_debt_limit = fields.Float(string='Sale Debt Limit', default=0.0)
    
    @api.depends('sale_order_ids.amount_total')
    def _compute_total_sales(self):
        for employee in self:
            if employee.user_id and employee.user_id.sale_order_ids:
                total_sales = sum(employee.user_id.sale_order_ids.mapped('amount_total'))
            else:
                total_sales = 0.0
            employee.total_sales = total_sales


    @api.depends('sale_order_ids.paid_amount')
    def _compute_total_payments(self):
        for employee in self:
            if employee.user_id and employee.user_id.sale_order_ids:
                total_payments = sum(employee.user_id.sale_order_ids.mapped('paid_amount'))
            else:
                total_payments = 0.0
            employee.total_payments = total_payments


    @api.depends('total_sales', 'total_payments')
    def _compute_debt_amount(self):
        for employee in self:
            employee.debt_amount = (employee.total_sales or 0.0) - (employee.total_payments or 0.0)
