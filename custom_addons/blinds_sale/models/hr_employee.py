from odoo import models, fields, api, _


class Employee(models.Model):
    _inherit = 'hr.employee'

    is_delivery_person = fields.Boolean(string='Is Delivery Person', default=False, compute='_compute_is_delivery_person')
    debt_amount = fields.Float(string='Debt Amount', default=0.0, compute='_compute_debt_amount')
    total_sales = fields.Float(string='Total Sales', default=0.0, compute='_compute_total_sales')
    total_payments = fields.Float(string='Total Payments', default=0.0, compute='_compute_total_payments')
    debt_limit = fields.Float(string='Debt Limit', default=0.0, compute='_compute_debt_limit')
    profit_percentage = fields.Float(string='Profit Percentage', default=0.0, compute='_compute_profit_percentage')
    
    @api.depends('user_id.is_delivery_person')
    def _compute_is_delivery_person(self):
        for employee in self:
            employee.is_delivery_person = employee.user_id.is_delivery_person if employee.user_id else False

    @api.depends('user_id.sale_debt_limit')
    def _compute_debt_limit(self):
        for employee in self:
            employee.debt_limit = employee.user_id.sale_debt_limit if employee.user_id else 0.0

    @api.depends('user_id.profit_percentage')
    def _compute_profit_percentage(self):
        for employee in self:
            employee.profit_percentage = employee.user_id.profit_percentage if employee.user_id else 0.0
    
    @api.depends('user_id.sale_order_ids.amount_total')
    def _compute_total_sales(self):
        for employee in self:
            if employee.user_id and employee.user_id.sale_order_ids:
                total_sales = sum(employee.user_id.sale_order_ids.mapped('amount_total'))
            else:
                total_sales = 0.0
            employee.total_sales = total_sales


    @api.depends('user_id.sale_order_ids.paid_amount')
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
