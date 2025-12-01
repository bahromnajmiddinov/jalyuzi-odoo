from odoo import models, fields

class CrmLead(models.Model):
    _inherit = 'crm.lead'

    fb_lead_id = fields.Char(string='Facebook Lead ID', readonly=True, copy=False)
    instagram_form_id = fields.Many2one('instagram.lead.form', string='Instagram Form', readonly=True, copy=False)

    _sql_constraints = [
        ('fb_lead_id_unique', 'unique(fb_lead_id)', 'This Facebook lead has already been imported!')
    ]