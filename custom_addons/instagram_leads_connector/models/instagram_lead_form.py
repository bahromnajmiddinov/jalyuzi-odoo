from odoo import models, fields, api, _
from odoo.exceptions import UserError
import requests
import json
import logging

_logger = logging.getLogger(__name__)

class InstagramLeadForm(models.Model):
    _name = 'instagram.lead.form'
    _description = 'Instagram/Facebook Lead Form'
    _rec_name = 'name'

    name = fields.Char(string='Form Name', required=True)
    form_id = fields.Char(string='Form ID', required=True)
    config_id = fields.Many2one('instagram.config', string='Configuration', required=True, ondelete='cascade')
    status = fields.Char(string='Status')
    leads_count = fields.Integer(string='FB Leads Count', readonly=True)
    lead_count = fields.Integer(string='Synced Leads', compute='_compute_lead_count')
    lead_ids = fields.One2many('crm.lead', 'instagram_form_id', string='Leads')
    active = fields.Boolean(default=True)
    last_sync = fields.Datetime(string='Last Sync')
    auto_sync = fields.Boolean(string='Auto Sync', default=True)
    contact_name = fields.Char(string='Contact Name')
    email_from = fields.Char(string='Email From')
    phone = fields.Char(string='Phone')
    stage_id = fields.Many2one('crm.stage', string='Stage')
    
    _sql_constraints = [
        ('form_id_unique', 'unique(form_id)', 'This lead form is already registered!')
    ]

    @api.depends('lead_ids')
    def _compute_lead_count(self):
        for form in self:
            form.lead_count = len(form.lead_ids)

    def action_sync_leads(self):
        """Sync leads from this form"""
        total_created = 0
        total_duplicate = 0
        
        for form in self:
            if not form.config_id.state == 'connected':
                continue
                
            try:
                url = f"{form.config_id.graph_api_url}/{form.form_id}/leads"
                params = {
                    'access_token': form.config_id.access_token,
                    'fields': 'id,created_time,field_data'
                }
                
                response = requests.get(url, params=params, timeout=10)
                data = response.json()
                
                if 'error' in data:
                    raise UserError(_('Error: %s') % data['error'].get('message'))
                
                leads_data = data.get('data', [])
                
                for lead_data in leads_data:
                    # Check if lead already exists
                    existing = self.env['crm.lead'].search([
                        ('fb_lead_id', '=', lead_data['id'])
                    ], limit=1)
                    
                    if existing:
                        total_duplicate += 1
                        continue
                    
                    # Parse lead data
                    parsed_data = self._parse_lead_data(lead_data)
                    
                    # Create lead in CRM
                    self._create_crm_lead(parsed_data, form)
                    total_created += 1
                
                form.last_sync = fields.Datetime.now()
                
            except Exception as e:
                _logger.error('Error syncing form %s: %s', form.name, str(e))
                raise UserError(_('Error syncing form %s: %s') % (form.name, str(e)))
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Sync Complete'),
                'message': _('Created: %d, Duplicates: %d') % (total_created, total_duplicate),
                'type': 'success',
                'sticky': False,
            }
        }

    def _parse_lead_data(self, lead_data):
        """Parse Facebook lead data"""
        parsed = {
            'fb_lead_id': lead_data['id'],
            'created_time': lead_data['created_time']
        }
        
        for field in lead_data.get('field_data', []):
            field_name = field['name'].lower().replace(' ', '_')
            parsed[field_name] = field['values'][0] if field['values'] else ''
        
        return parsed

    def _create_crm_lead(self, lead_data, form):
        """Create lead in CRM"""
        # Get or create Instagram source
        source = self.env['utm.source'].search([('name', '=', 'Instagram')], limit=1)
        if not source:
            source = self.env['utm.source'].create({'name': 'Instagram'})
        
        # Prepare lead values
        lead_vals = {
            'name': lead_data.get('full_name') or lead_data.get('name') or 'Instagram Lead',
            'contact_name': lead_data.get('full_name') or lead_data.get('name', ''),
            'email_from': lead_data.get('email', ''),
            'phone': lead_data.get('phone_number') or lead_data.get('phone', ''),
            'type': 'lead',
            'source_id': source.id,
            'fb_lead_id': lead_data.get('fb_lead_id'),
            'instagram_form_id': form.id,
            'description': f"Lead from Instagram/Facebook Form: {form.name}\n"
                          f"FB Lead ID: {lead_data.get('fb_lead_id')}\n"
                          f"Created: {lead_data.get('created_time')}\n\n"
        }
        
        # Add custom fields to description
        for key, value in lead_data.items():
            if key not in ['fb_lead_id', 'created_time', 'full_name', 'name', 
                          'email', 'phone_number', 'phone'] and value:
                lead_vals['description'] += f"{key.replace('_', ' ').title()}: {value}\n"
        
        return self.env['crm.lead'].create(lead_vals)