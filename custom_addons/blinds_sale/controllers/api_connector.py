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
        depth = data.get("depth", 1)  # Control nested serialization depth
        
        print(f"Received request to call {model}.{method} with args: {args} and kwargs: {kwargs}")
        
        if not model or not method:
            return {"error": "Model and method are required"}
        
        try:
            model_obj = request.env[model]
            
            if method == 'unlink' and args:
                record_ids = args[0]
                records_to_delete = model_obj.browse(record_ids)
                result = records_to_delete.unlink()
            else:
                method_to_call = getattr(model_obj, method)
                result = method_to_call(*args, **kwargs)
                
                # Apply profit percentage if needed
                if model == 'product.template' and method in ['search_read', 'read'] and \
                   employee and employee.profit_percentage:
                    for record in result:
                        record['list_price'] = record['list_price'] * (1 + employee.profit_percentage / 100)
            
            # Serialize based on result type
            if method in ['search_read', 'read']:
                # search_read and read return list of dicts, process each dict
                if isinstance(result, list):
                    result = [self.process_dict_result(record, model_obj, depth=depth) for record in result]
            elif hasattr(result, "ids"):
                result = [self.serialize_record(rec, depth=depth) for rec in result]
            elif hasattr(result, "id"):
                result = self.serialize_record(result, depth=depth)

            return {"result": result}

        except Exception as e:
            print(f"Error calling {model}.{method}: {e}")
            return {"error": str(e)}
    
    def process_dict_result(self, data_dict, model_obj, depth=1):
        """
        Process a dictionary result from search_read/read to expand relational fields.
        
        Args:
            data_dict: Dictionary from search_read/read
            model_obj: The model object to get field info
            depth: How deep to serialize nested relations
        """
        if depth <= 0:
            return data_dict
        
        result = data_dict.copy()
        
        # Get field definitions
        for field_name in data_dict.keys():
            if field_name not in model_obj._fields:
                continue
                
            field = model_obj._fields[field_name]
            value = data_dict[field_name]
            
            # Many2one field - usually returns [id, name]
            if field.type == "many2one" and value:
                if isinstance(value, (list, tuple)) and len(value) >= 1:
                    # Fetch the actual record
                    record_id = value[0] if isinstance(value[0], int) else value
                    related_record = request.env[field.comodel_name].browse(record_id)
                    if related_record.exists():
                        result[field_name] = self.serialize_record(related_record, depth=depth-1)
                    else:
                        result[field_name] = None
            
            # One2many / Many2many - usually returns list of IDs
            elif field.type in ("one2many", "many2many") and value:
                if isinstance(value, list) and value:
                    # Fetch actual records
                    related_records = request.env[field.comodel_name].browse(value)
                    result[field_name] = [
                        self.serialize_record(rec, depth=depth-1)
                        for rec in related_records if rec.exists()
                    ]
        
        return result
    
    def serialize_record(self, record, depth=1, visited=None):
        """
        Convert an Odoo record into JSON-safe nested object.
        
        Args:
            record: Odoo recordset
            depth: How deep to serialize nested relations (0 = IDs only, 1+ = full data)
            visited: Set of already serialized record IDs to prevent circular refs
        """
        if not record:
            return {}
        
        if visited is None:
            visited = set()
        
        # Prevent circular references
        record_key = f"{record._name}_{record.id}"
        if record_key in visited:
            return {"id": record.id, "name": record.display_name}
        
        visited.add(record_key)
        data = {}

        for field_name, field in record._fields.items():
            value = record[field_name]

            # Basic fields
            if field.type in ("char", "text", "float", "integer", "boolean", "monetary", "date", "datetime", "selection"):
                data[field_name] = value

            # Many2one field
            elif field.type == "many2one":
                if value:
                    if depth > 0:
                        # Full nested object
                        data[field_name] = self.serialize_record(value, depth=depth-1, visited=visited.copy())
                    else:
                        # Just ID and name
                        data[field_name] = {
                            "id": value.id,
                            "name": value.display_name,
                        }
                else:
                    data[field_name] = None

            # One2many / Many2many fields
            elif field.type in ("one2many", "many2many"):
                if depth > 0:
                    # Full nested objects
                    data[field_name] = [
                        self.serialize_record(rec, depth=depth-1, visited=visited.copy())
                        for rec in value
                    ]
                else:
                    # Just IDs and names
                    data[field_name] = [
                        {"id": rec.id, "name": rec.display_name}
                        for rec in value
                    ]

            # Binary field
            elif field.type == "binary":
                data[field_name] = value.decode() if value else ""

        return data