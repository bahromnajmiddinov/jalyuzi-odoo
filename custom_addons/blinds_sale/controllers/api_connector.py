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
        depth = data.get("depth", 2)
        
        # Pagination parameters
        limit = data.get("limit")
        offset = data.get("offset", 4)
        
        # Field filtering for relations
        relation_fields = data.get("relation_fields", {})
        # Example: {"categ_id": ["id", "name"], "uom_id": ["id", "name", "uom_type"]}
        
        print(f"Received request to call {model}.{method} with args: {args} and kwargs: {kwargs}")
        print(f"Pagination: limit={limit}, offset={offset}")
        print(f"Relation fields filter: {relation_fields}")
        
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
            elif method == 'write' and args:
                record_ids = args[0]
                values = args[1] if len(args) > 1 else {}
                records_to_write = model_obj.browse(record_ids)
                result = records_to_write.write(values)
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
                if model == 'product.template' and method in ['search_read', 'read'] and employee:
                    profit = employee.profit_percentage or 0
                    for record in result:
                        price = record.get('list_price') or 0
                        record['list_price'] = price * (1 + profit / 100)

            
            # Serialize based on result type
            if method in ['search_read', 'read']:
                if isinstance(result, list):
                    result = [self.process_dict_result(record, model_obj, depth=depth, relation_fields=relation_fields) for record in result]
            elif hasattr(result, "ids"):
                result = [self.serialize_record(rec, depth=depth, relation_fields=relation_fields) for rec in result]
            elif hasattr(result, "id"):
                result = self.serialize_record(result, depth=depth, relation_fields=relation_fields)

            # Return with pagination metadata
            response = {"result": result}
            if total_count is not None and total_count > 1:
                response["total_count"] = total_count
                response["limit"] = limit
                response["offset"] = offset
                response["has_more"] = (offset + limit) < total_count
            
            return response

        except Exception as e:
            print(f"Error calling {model}.{method}: {e}")
            return {"error": str(e)}
    
    def process_dict_result(self, data_dict, model_obj, depth=1, relation_fields=None):
        """
        Process a dictionary result from search_read/read to expand relational fields.
        
        Args:
            data_dict: Dictionary from search_read/read
            model_obj: The model object to get field info
            depth: How deep to serialize nested relations
            relation_fields: Dict of field_name -> list of fields to include
                            e.g. {"categ_id": ["id", "name"], "uom_id": ["id", "name"]}
        """
        if depth <= 0:
            return data_dict
        
        relation_fields = relation_fields or {}
        result = data_dict.copy()
        
        for field_name in data_dict.keys():
            if field_name not in model_obj._fields:
                continue
                
            field = model_obj._fields[field_name]
            value = data_dict[field_name]
            
            # Get allowed fields for this relation
            allowed_fields = relation_fields.get(field_name)
            
            # Many2one field - usually returns [id, name]
            if field.type == "many2one" and value:
                if isinstance(value, (list, tuple)) and len(value) >= 1:
                    record_id = value[0] if isinstance(value[0], int) else value
                    related_record = request.env[field.comodel_name].browse(record_id)
                    if related_record.exists():
                        result[field_name] = self.serialize_record(
                            related_record, 
                            depth=depth-1, 
                            relation_fields=relation_fields,
                            allowed_fields=allowed_fields
                        )
                    else:
                        result[field_name] = None
            
            # One2many / Many2many - usually returns list of IDs
            elif field.type in ("one2many", "many2many") and value:
                if isinstance(value, list) and value:
                    related_records = request.env[field.comodel_name].browse(value)
                    result[field_name] = [
                        self.serialize_record(
                            rec, 
                            depth=depth-1, 
                            relation_fields=relation_fields,
                            allowed_fields=allowed_fields
                        )
                        for rec in related_records if rec.exists()
                    ]
        
        return result
    
    def serialize_record(self, record, depth=1, visited=None, relation_fields=None, allowed_fields=None):
        """
        Convert an Odoo record into JSON-safe nested object.
        
        Args:
            record: Odoo recordset
            depth: How deep to serialize nested relations (0 = IDs only, 1+ = full data)
            visited: Set of already serialized record IDs to prevent circular refs
            relation_fields: Dict of field_name -> list of fields to include for nested relations
            allowed_fields: List of fields to include for THIS record (None = all fields)
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
        relation_fields = relation_fields or {}
        data = {}

        for field_name, field in record._fields.items():
            # Skip field if allowed_fields is specified and field is not in the list
            if allowed_fields is not None and field_name not in allowed_fields:
                continue
                
            value = record[field_name]

            # Basic fields
            if field.type in ("char", "text", "float", "integer", "boolean", "monetary", "date", "datetime", "selection"):
                data[field_name] = value

            # Many2one field
            elif field.type == "many2one":
                if value:
                    # Get allowed fields for this specific relation
                    nested_allowed_fields = relation_fields.get(field_name)
                    
                    if depth > 0:
                        # Full nested object
                        data[field_name] = self.serialize_record(
                            value, 
                            depth=depth-1, 
                            visited=visited.copy(), 
                            relation_fields=relation_fields,
                            allowed_fields=nested_allowed_fields
                        )
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
                # Get allowed fields for this specific relation
                nested_allowed_fields = relation_fields.get(field_name)
                
                if depth > 0:
                    # Full nested objects
                    data[field_name] = [
                        self.serialize_record(
                            rec, 
                            depth=depth-1, 
                            visited=visited.copy(), 
                            relation_fields=relation_fields,
                            allowed_fields=nested_allowed_fields
                        )
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
    