from odoo import http
from odoo.http import request
import json

class MobilePWAController(http.Controller):
    
    @http.route('/mobile', type='http', auth='user', website=True)
    def mobile_app(self, **kwargs):
        """Main mobile app entry point"""
        return request.render('odoo_mobile_pwa.mobile_app_template', {
            'user': request.env.user,
        })
    
    @http.route('/manifest.json', type='http', auth='public')
    def manifest(self):
        """PWA manifest file"""
        manifest = {
            "name": "Odoo Mobile",
            "short_name": "Odoo",
            "description": "Odoo Mobile PWA",
            "start_url": "/mobile",
            "display": "standalone",
            "background_color": "#714B67",
            "theme_color": "#714B67",
            "orientation": "portrait",
            "icons": [
                {
                    "src": "/odoo_mobile_pwa/static/icons/icon-192x192.png",
                    "sizes": "192x192",
                    "type": "image/png",
                    "purpose": "any maskable"
                },
                {
                    "src": "/odoo_mobile_pwa/static/icons/icon-512x512.png",
                    "sizes": "512x512",
                    "type": "image/png",
                    "purpose": "any maskable"
                }
            ]
        }
        return request.make_response(
            json.dumps(manifest),
            headers=[('Content-Type', 'application/json')]
        )
    
    @http.route('/service-worker.js', type='http', auth='public')
    def service_worker(self):
        """Service worker for offline functionality"""
        sw_content = """
const CACHE_NAME = 'odoo-mobile-v1';
const urlsToCache = [
  '/mobile',
  '/web/static/src/css/bootstrap.css',
  '/web/static/lib/bootstrap/css/bootstrap.css',
];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => cache.addAll(urlsToCache))
  );
});

self.addEventListener('fetch', event => {
  event.respondWith(
    caches.match(event.request)
      .then(response => response || fetch(event.request))
  );
});
"""
        return request.make_response(
            sw_content,
            headers=[('Content-Type', 'application/javascript')]
        )
    
    # API endpoints for mobile app
    @http.route('/mobile/api/menu', type='json', auth='user')
    def get_menu(self):
        """Get user menu items"""
        menus = request.env['ir.ui.menu'].search([
            ('parent_id', '=', False)
        ])
        return [{
            'id': menu.id,
            'name': menu.name,
            'icon': menu.web_icon,
        } for menu in menus]
    
    @http.route('/mobile/api/records/<string:model>', type='json', auth='user')
    def get_records(self, model, domain=None, fields=None, limit=50):
        """Get records from any model"""
        try:
            Model = request.env[model]
            domain = domain or []
            records = Model.search(domain, limit=limit)
            return records.read(fields) if fields else records.read()
        except Exception as e:
            return {'error': str(e)}
    
    @http.route('/mobile/api/create/<string:model>', type='json', auth='user')
    def create_record(self, model, values):
        """Create a new record"""
        try:
            Model = request.env[model]
            record = Model.create(values)
            return {'id': record.id, 'success': True}
        except Exception as e:
            return {'error': str(e), 'success': False}
    
    @http.route('/mobile/api/update/<string:model>/<int:record_id>', type='json', auth='user')
    def update_record(self, model, record_id, values):
        """Update an existing record"""
        try:
            Model = request.env[model]
            record = Model.browse(record_id)
            record.write(values)
            return {'success': True}
        except Exception as e:
            return {'error': str(e), 'success': False}
    
    @http.route('/mobile/api/delete/<string:model>/<int:record_id>', type='json', auth='user')
    def delete_record(self, model, record_id):
        """Delete a record"""
        try:
            Model = request.env[model]
            record = Model.browse(record_id)
            record.unlink()
            return {'success': True}
        except Exception as e:
            return {'error': str(e), 'success': False}