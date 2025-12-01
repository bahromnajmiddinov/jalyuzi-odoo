{
    'name': 'Baha Odoo Mobile PWA',
    'version': '18.0.1.0.0',
    'category': 'Tools',
    'summary': 'Progressive Web App for Odoo Community',
    'description': """
        Mobile-friendly Progressive Web App for Odoo 18 Community
        - Works offline
        - Installable on mobile devices
        - Responsive design
        - Fast and lightweight
    """,
    'depends': ['web', 'base'],
    'data': [
        'views/mobile_app_templates.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'baha_pwa/static/src/js/mobile_app.js',
            'baha_pwa/static/src/xml/mobile_templates.xml',
            'baha_pwa/static/src/css/mobile_app.css',
        ],
    },
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
