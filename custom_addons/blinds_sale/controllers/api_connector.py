from odoo import http
from odoo.http import request

class DynamicOdooCall(http.Controller):

    @http.route('/custom_api/call', type='json', auth='user', csrf=False)
    def call_anything(self, **kw):
        user = request.env.user
        employee = request.env['hr.employee'].search([('user_id', '=', user.id)], limit=1)
        data = request.get_json_data()
        model = data.get("model")
        method = data.get("method")
        args = data.get("args", [])
        kwargs = data.get("kwargs", {})
        depth = data.get("depth", 1)
        
        # Pagination parameters
        limit = data.get("limit")
        offset = data.get("offset", 0)
        
        print(f"Received request to call {model}.{method} with args: {args} and kwargs: {kwargs}")
        print(f"Pagination: limit={limit}, offset={offset}")
        
        if not model or not method:
            return {"error": "Model and method are required"}
        
        try:
            model_obj = request.env[model]
            
            # Apply pagination to kwargs if provided
            if limit is not None and method in ['search_read', 'search']:
                kwargs['limit'] = limit
                kwargs['offset'] = offset
            
            if method == 'unlink' and args:
                record_ids = args[0]
                records_to_delete = model_obj.browse(record_ids)
                result = records_to_delete.unlink()
                total_count = len(record_ids)
            else:
                method_to_call = getattr(model_obj, method)
                result = method_to_call(*args, **kwargs)
                
                # Get total count for pagination
                total_count = None
                if method in ['search_read', 'search'] and limit is not None:
                    # Get domain from args or kwargs
                    domain = args[0] if args else kwargs.get('domain', [])
                    total_count = model_obj.search_count(domain)
                
                # Apply profit percentage if needed
                if model == 'product.template' and method in ['search_read', 'read'] and \
                   employee and employee.profit_percentage:
                    for record in result:
                        record['list_price'] = record['list_price'] * (1 + employee.profit_percentage / 100)
            
            # Serialize based on result type
            if method in ['search_read', 'read']:
                if isinstance(result, list):
                    result = [self.process_dict_result(record, model_obj, depth=depth) for record in result]
            elif hasattr(result, "ids"):
                result = [self.serialize_record(rec, depth=depth) for rec in result]
            elif hasattr(result, "id"):
                result = self.serialize_record(result, depth=depth)

            # Return with pagination metadata
            response = {"result": result}
            if total_count is not None:
                response["total_count"] = total_count
                response["limit"] = limit
                response["offset"] = offset
                response["has_more"] = (offset + limit) < total_count
            
            return response

        except Exception as e:
            print(f"Error calling {model}.{method}: {e}")
            return {"error": str(e)}
    
    def process_dict_result(self, data_dict, model_obj, depth=1):
        """
        Process a dictionary result from search_read/read to expand relational fields.
        """
        if depth <= 0:
            return data_dict
        
        result = data_dict.copy()
        
        for field_name in data_dict.keys():
            if field_name not in model_obj._fields:
                continue
                
            field = model_obj._fields[field_name]
            value = data_dict[field_name]
            
            if field.type == "many2one" and value:
                if isinstance(value, (list, tuple)) and len(value) >= 1:
                    record_id = value[0] if isinstance(value[0], int) else value
                    related_record = request.env[field.comodel_name].browse(record_id)
                    if related_record.exists():
                        result[field_name] = self.serialize_record(related_record, depth=depth-1)
                    else:
                        result[field_name] = None
            
            elif field.type in ("one2many", "many2many") and value:
                if isinstance(value, list) and value:
                    related_records = request.env[field.comodel_name].browse(value)
                    result[field_name] = [
                        self.serialize_record(rec, depth=depth-1)
                        for rec in related_records if rec.exists()
                    ]
        
        return result
    
    def serialize_record(self, record, depth=1, visited=None):
        """
        Convert an Odoo record into JSON-safe nested object.
        """
        if not record:
            return {}
        
        if visited is None:
            visited = set()
        
        record_key = f"{record._name}_{record.id}"
        if record_key in visited:
            return {"id": record.id, "name": record.display_name}
        
        visited.add(record_key)
        data = {}

        for field_name, field in record._fields.items():
            value = record[field_name]

            if field.type in ("char", "text", "float", "integer", "boolean", "monetary", "date", "datetime", "selection"):
                data[field_name] = value

            elif field.type == "many2one":
                if value:
                    if depth > 0:
                        data[field_name] = self.serialize_record(value, depth=depth-1, visited=visited.copy())
                    else:
                        data[field_name] = {
                            "id": value.id,
                            "name": value.display_name,
                        }
                else:
                    data[field_name] = None

            elif field.type in ("one2many", "many2many"):
                if depth > 0:
                    data[field_name] = [
                        self.serialize_record(rec, depth=depth-1, visited=visited.copy())
                        for rec in value
                    ]
                else:
                    data[field_name] = [
                        {"id": rec.id, "name": rec.display_name}
                        for rec in value
                    ]

            elif field.type == "binary":
                data[field_name] = value.decode() if value else ""

        return data