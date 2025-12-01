{
    'name': 'Instagram Leads Connector',
    'version': '18.0.1.0.0',
    'category': 'Marketing/Social Marketing',
    'summary': 'Sync Instagram/Facebook Lead Ads to Odoo CRM',
    'description': """
        Instagram Leads Connector
        =========================
        Automatically sync leads from Instagram and Facebook Lead Ads to Odoo CRM.
        
        Features:
        ---------
        * Connect Facebook/Instagram Lead Ads
        * Automatic lead synchronization
        * Manual sync option
        * Lead form mapping
        * UTM tracking
        * Duplicate detection
    """,
    'author': 'Your Company',
    'website': 'https://www.yourcompany.com',
    'license': 'LGPL-3',
    'depends': ['crm', 'utm'],
    'data': [
        'security/ir.model.access.csv',
        'data/ir_cron.xml',
        'views/menus.xml',
        'views/instagram_lead_form_views.xml',
        'views/instagram_config_views.xml',
        'views/crm_lead_views.xml',
    ],
    'images': ['static/description/icon.png'],
    'installable': True,
    'application': False,
    'auto_install': False,
}