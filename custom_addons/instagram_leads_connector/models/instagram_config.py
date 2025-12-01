from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import requests
import logging

_logger = logging.getLogger(__name__)

class InstagramConfig(models.Model):
    _name = 'instagram.config'
    _description = 'Instagram/Facebook Configuration'
    _rec_name = 'page_name'

    name = fields.Char(string='Configuration Name', required=True)
    page_name = fields.Char(string='Page Name', readonly=True)
    access_token = fields.Char(string='Access Token', required=True, help='Facebook Page Access Token')
    page_id = fields.Char(string='Page ID', required=True)
    active = fields.Boolean(default=True)
    last_sync = fields.Datetime(string='Last Sync', readonly=True)
    sync_interval = fields.Integer(string='Sync Interval (minutes)', default=30)
    lead_form_ids = fields.One2many('instagram.lead.form', 'config_id', string='Lead Forms')
    lead_count = fields.Integer(string='Total Leads', compute='_compute_lead_count')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('connected', 'Connected'),
        ('error', 'Error')
    ], default='draft', string='Status')
    error_message = fields.Text(string='Error Message', readonly=True)
    
    graph_api_url = fields.Char(default='https://graph.facebook.com/v18.0', readonly=True)

    @api.depends('lead_form_ids.lead_ids')
    def _compute_lead_count(self):
        for config in self:
            config.lead_count = sum(form.lead_count for form in config.lead_form_ids)

    def action_test_connection(self):
        """Test Facebook API connection"""
        self.ensure_one()
        try:
            url = f"{self.graph_api_url}/{self.page_id}"
            params = {
                'access_token': self.access_token,
                'fields': 'name,id'
            }
            
            response = requests.get(url, params=params, timeout=10)
            data = response.json()
            
            if 'error' in data:
                raise UserError(_(
                    'Connection failed: %s\n%s'
                ) % (data['error'].get('message', 'Unknown error'), 
                     data['error'].get('error_user_msg', '')))
            
            self.write({
                'page_name': data.get('name'),
                'state': 'connected',
                'error_message': False
            })
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Success'),
                    'message': _('Connected to page: %s') % data.get('name'),
                    'type': 'success',
                    'sticky': False,
                }
            }
            
        except requests.exceptions.RequestException as e:
            self.write({
                'state': 'error',
                'error_message': str(e)
            })
            raise UserError(_('Connection error: %s') % str(e))

    def action_fetch_lead_forms(self):
        """Fetch all lead forms from Facebook"""
        self.ensure_one()
        
        if self.state != 'connected':
            raise UserError(_('Please test connection first'))
        
        try:
            url = f"{self.graph_api_url}/{self.page_id}/leadgen_forms"
            params = {
                'access_token': self.access_token,
                'fields': 'id,name,status,leads_count,created_time'
            }
            
            response = requests.get(url, params=params, timeout=10)
            data = response.json()
            
            if 'error' in data:
                raise UserError(_('Error: %s') % data['error'].get('message'))
            
            forms_data = data.get('data', [])
            created_count = 0
            
            for form_data in forms_data:
                existing = self.env['instagram.lead.form'].search([
                    ('form_id', '=', form_data['id']),
                    ('config_id', '=', self.id)
                ])
                
                if not existing:
                    self.env['instagram.lead.form'].create({
                        'name': form_data['name'],
                        'form_id': form_data['id'],
                        'config_id': self.id,
                        'status': form_data.get('status', 'active'),
                        'leads_count': form_data.get('leads_count', 0),
                    })
                    created_count += 1
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Success'),
                    'message': _('Found %d form(s), created %d new form(s)') % (len(forms_data), created_count),
                    'type': 'success',
                    'sticky': False,
                }
            }
            
        except Exception as e:
            _logger.error('Error fetching lead forms: %s', str(e))
            raise UserError(_('Error fetching forms: %s') % str(e))

    def action_sync_leads(self):
        """Manual sync leads"""
        self.ensure_one()
        return self.lead_form_ids.action_sync_leads()

    @api.model
    def cron_sync_leads(self):
        """Cron job to sync leads"""
        configs = self.search([('active', '=', True), ('state', '=', 'connected')])
        for config in configs:
            try:
                config.action_sync_leads()
                config.last_sync = fields.Datetime.now()
            except Exception as e:
                _logger.error('Error syncing leads for config %s: %s', config.name, str(e))
                config.write({
                    'state': 'error',
                    'error_message': str(e)
                })