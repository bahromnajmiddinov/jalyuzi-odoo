from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from datetime import datetime, timedelta


class SaleOrder(models.Model):
    _inherit = 'sale.order'
    
    # Production Status
    production_state = fields.Selection([
        ('not_ready', 'Not Ready'),
        ('ready', 'Ready for Production'),
        ('in_production', 'In Production'),
        ('completed', 'Production Completed'),
        ('on_hold', 'On Hold'),
    ], string='Production Status', default='not_ready', tracking=True)
    
    # Production Dates
    production_ready_date = fields.Datetime(
        string='Ready for Production Date',
        readonly=True,
        tracking=True
    )
    production_start_date = fields.Datetime(
        string='Production Start Date',
        tracking=True
    )
    production_end_date = fields.Datetime(
        string='Production End Date',
        tracking=True
    )
    production_expected_date = fields.Date(
        string='Expected Production Date',
        compute='_compute_expected_production_date',
        store=True
    )
    
    # Production Details
    production_priority = fields.Selection([
        ('0', 'Normal'),
        ('1', 'Medium'),
        ('2', 'High'),
        ('3', 'Urgent'),
    ], string='Production Priority', default='0', tracking=True)
    
    production_notes = fields.Text(string='Production Notes')
    production_responsible_id = fields.Many2one(
        'res.users',
        string='Production Responsible',
        tracking=True
    )
    
    # Computed Fields
    production_duration = fields.Float(
        string='Production Duration (Days)',
        compute='_compute_production_duration',
        store=True
    )
    is_production_ready = fields.Boolean(
        string='Ready for Production',
        compute='_compute_is_production_ready',
        store=True
    )
    production_delay = fields.Integer(
        string='Production Delay (Days)',
        compute='_compute_production_delay',
        store=True
    )
    
    # Requirements Checklist
    materials_available = fields.Boolean(
        string='Materials Available',
        default=False
    )
    specifications_confirmed = fields.Boolean(
        string='Specifications Confirmed',
        default=False
    )
    payment_received = fields.Boolean(
        string='Payment Received',
        compute='_compute_payment_received',
        store=True
    )
    
    @api.depends(
        'state',
        'order_line',
        'materials_available',
        'specifications_confirmed'
    )
    def _compute_is_production_ready(self):
        for order in self:
            order.is_production_ready = (
                order.state in ['sale', 'done']
                and order.order_line
                and order.materials_available
                and order.specifications_confirmed
            )
    
    @api.depends('commitment_date', 'date_order')
    def _compute_expected_production_date(self):
        for order in self:
            if order.commitment_date:
                # Expect production 2 days before commitment
                order.production_expected_date = order.commitment_date - timedelta(days=2)
            elif order.date_order:
                # Default 7 days from order date
                order.production_expected_date = order.date_order.date() + timedelta(days=7)
            else:
                order.production_expected_date = False
    
    @api.depends('production_start_date', 'production_end_date')
    def _compute_production_duration(self):
        for order in self:
            if order.production_start_date and order.production_end_date:
                delta = order.production_end_date - order.production_start_date
                order.production_duration = delta.total_seconds() / 86400  # Convert to days
            else:
                order.production_duration = 0.0
    
    @api.depends('production_end_date', 'production_expected_date')
    def _compute_production_delay(self):
        for order in self:
            if order.production_end_date and order.production_expected_date:
                end_date = order.production_end_date.date()
                delay = (end_date - order.production_expected_date).days
                order.production_delay = delay if delay > 0 else 0
            else:
                order.production_delay = 0
    
    @api.depends('invoice_ids', 'invoice_ids.payment_state')
    def _compute_payment_received(self):
        for order in self:
            order.payment_received = any(
                inv.payment_state in ['paid', 'in_payment'] 
                for inv in order.invoice_ids
            )
    
    def action_mark_ready_for_production(self):
        for order in self:
            order._check_production_requirements()
            order.write({
                'production_state': 'ready',
                'production_ready_date': fields.Datetime.now(),
            })

            # Post message in chatter
            order.message_post(
                body=_('Sales Order marked as Ready for Production by %s') % self.env.user.name,
                message_type='notification'
            )
    
    def action_start_production(self):
        """Start production for the sales order"""
        for order in self:
            if order.production_state not in ['ready', 'on_hold']:
                raise UserError(_('Only orders that are Ready or On Hold can start production.'))
            
            order.write({
                'production_state': 'in_production',
                'production_start_date': fields.Datetime.now(),
            })
            
            order.message_post(
                body=_('Production started by %s') % self.env.user.name,
                message_type='notification'
            )
        
        return True
    
    def action_complete_production(self):
        """Complete production for the sales order"""
        for order in self:
            if order.production_state != 'in_production':
                raise UserError(_('Only orders in production can be completed.'))
            
            order.write({
                'production_state': 'completed',
                'production_end_date': fields.Datetime.now(),
            })
            
            # Calculate if there was a delay
            delay_msg = ''
            if order.production_delay > 0:
                delay_msg = _('<br/>⚠️ Production completed %s days late.') % order.production_delay
            
            order.message_post(
                body=_('Production completed by %s%s') % (self.env.user.name, delay_msg),
                message_type='notification'
            )
        
        return True
    
    def action_hold_production(self):
        """Put production on hold"""
        for order in self:
            if order.production_state not in ['ready', 'in_production']:
                raise UserError(_('Only Ready or In Production orders can be put on hold.'))
            
            order.production_state = 'on_hold'
            order.message_post(
                body=_('Production put on hold by %s') % self.env.user.name,
                message_type='notification'
            )
        
        return True
    
    def action_open_production_wizard(self):
        """Open production details wizard"""
        return {
            'name': _('Production Details'),
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order',
            'res_id': self.id,
            'view_mode': 'form',
            'view_id': self.env.ref('sales_mo.view_sale_order_production_form').id,
            'target': 'new',
        }
    
    @api.constrains('production_start_date', 'production_end_date')
    def _check_production_requirements(self):
        self.ensure_one()
        if self.state not in ['sale', 'done']:
            raise UserError(_("Sales order must be confirmed."))
        if not self.materials_available:
            raise UserError(_("Materials must be available."))
        if not self.specifications_confirmed:
            raise UserError(_("Specifications must be confirmed."))
        if not self.order_line:
            raise UserError(_("Order must have at least one line."))
                    