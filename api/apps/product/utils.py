def _get_products_by_combo_id(combo_id, odoo, product_domain=None):
    
    product_ids = odoo.call(
        'product.combo.item', 
        'search_read', 
        kwargs={
            'domain': [('combo_id', '=', combo_id)],
            'fields': ['product_id']
        }
    )
    
    product_domain.append(('id', 'in', [item['product_id'][0] for item in product_ids]))
    
    products = odoo.call(
        'product.product', 
        'search_read', 
        kwargs={
            'domain': product_domain,
            'fields': [
                    'id', 'name', 'default_code', 'list_price',
                    'uom_id', 'formula_id', 'image_1920', 'taxes_id',
                    'uom_name', 'standard_price', 'categ_id', 'product_tag_ids',
                    'qty_available',
                ]
        }
    )
    
    return products
    