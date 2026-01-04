from odoo import http
from odoo.http import request
import base64
from werkzeug.wrappers import Response
import odoo


class CustomPublicImageController(http.Controller):
    
    def _get_db(self):
        """Get the current database name"""
        # Try to get from request
        db = request.db
        if db:
            return db
        
        # Try to get from session
        if hasattr(request, 'session') and request.session.db:
            return request.session.db
        
        # Get from config (if only one database)
        if odoo.tools.config.get('db_name'):
            return odoo.tools.config['db_name']
        
        # List available databases and use the first one
        try:
            dbs = odoo.service.db.list_dbs(force=True)
            if dbs and len(dbs) > 0:
                return dbs[0]
        except:
            pass
        
        return None
    
    @http.route('/my/image/<string:model>/<int:rec_id>/<string:field>', 
                type='http', auth='none', csrf=False, methods=['GET'], save_session=False)
    def get_public_image(self, model, rec_id, field, **kwargs):
        """
        Simple custom route to serve images publicly
        URL: http://localhost:8069/my/image/product.template/23/image_1920
        """
        try:
            # Get database name
            db_name = self._get_db()
            
            if not db_name:
                return Response('Database not found', status=500)
            
            # List of allowed models (add more as needed)
            allowed_models = [
                'product.template',
                'product.product',
                'product.attribute',
                'product.category',
                'res.users',
            ]
            
            # List of allowed image fields (add more as needed)
            allowed_fields = [
                'image_1920',
                'image_1024', 
                'image_512',
                'image_256',
                'image_128',
                'image',
            ]
            
            # Security check
            if model not in allowed_models:
                return Response('Model not allowed', status=403)
            
            if field not in allowed_fields:
                return Response('Field not allowed', status=403)
            
            # Create environment with database
            registry = odoo.registry(db_name)
            with registry.cursor() as cr:
                env = odoo.api.Environment(cr, odoo.SUPERUSER_ID, {})
                
                # Get record with sudo (bypass security)
                record = env[model].sudo().browse(rec_id)
                
                # Check if record exists
                if not record.exists():
                    return Response('Record not found', status=404)
                
                # Get image data (it's stored as base64 in Odoo)
                image_base64 = getattr(record, field, False)
                
                if not image_base64:
                    return Response('No image', status=404)
                
                # Decode base64 to binary
                image_binary = base64.b64decode(image_base64)
            
            # Detect image type
            if image_binary[:2] == b'\xff\xd8':
                content_type = 'image/jpeg'
            elif image_binary[:4] == b'\x89PNG':
                content_type = 'image/png'
            elif image_binary[:3] == b'GIF':
                content_type = 'image/gif'
            elif image_binary[:4] == b'<svg' or image_binary[:5] == b'<?xml':
                content_type = 'image/svg+xml'
            else:
                content_type = 'image/png'  # default
            
            # Return image
            return Response(
                image_binary,
                headers=[
                    ('Content-Type', content_type),
                    ('Cache-Control', 'public, max-age=86400'),  # Cache 1 day
                ],
                status=200
            )
            
        except Exception as e:
            # Log error
            import logging
            _logger = logging.getLogger(__name__)
            _logger.error('Error serving image: %s', str(e), exc_info=True)
            
            return Response('Error: ' + str(e), status=500)
    
    
    @http.route('/my/test', type='http', auth='none', csrf=False, save_session=False)
    def test_route(self, **kwargs):
        """Test if controller is working"""
        db_name = self._get_db()
        return f"Controller is working! ✓ Database: {db_name}"