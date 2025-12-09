from django.core.cache import cache
from drf_spectacular.utils import extend_schema, OpenApiParameter
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework import serializers

from .serializers import (
    ProductSerializer, ProductCategorySerializer,
    ProductTagSerializer, ProductFormulaSerializer,
    ProductFormulaCalculateSerializer, ComboProductWithComponentsSerializer,
)
from apps.utils.pagination import StandardResultsSetPagination
from apps.utils.odoo import get_odoo_client, get_odoo_client_with_cached_session
from apps.utils.odoo_utils import _get_profit_per_order
from .utils import _get_products_by_combo_id


class ProductListAPIView(GenericAPIView):
    """
    Returns paginated products with metadata.
    """
    
    @extend_schema(
        parameters=[
            OpenApiParameter(
                name='search',
                description='Search products by name',
                required=False,
                type=str,
                location=OpenApiParameter.QUERY,
            ),
            OpenApiParameter(
                name='tag',
                description='Filter products by tag ID',
                required=False,
                type=int,
                location=OpenApiParameter.QUERY,
            ),
            OpenApiParameter(
                name='category',
                description='Filter products by category ID',
                required=False,
                type=int,
                location=OpenApiParameter.QUERY,
            ),
            OpenApiParameter(
                name='combo_id',
                description='Filter products by combo ID',
                required=False,
                type=int,
                location=OpenApiParameter.QUERY,
            ),
            OpenApiParameter(
                name='page',
                description='Page number (default: 1)',
                required=False,
                type=int,
                location=OpenApiParameter.QUERY,
            ),
            OpenApiParameter(
                name='page_size',
                description='Number of items per page (default: 20, max: 100)',
                required=False,
                type=int,
                location=OpenApiParameter.QUERY,
            ),
        ],
        responses={200: ProductSerializer(many=True)},
        summary="List all products with pagination and optional filtering",
    )
    def get(self, request):
        domain = []

        # Get query parameters
        tag_id = request.query_params.get('tag')
        category_id = request.query_params.get('category')
        search_by_name = request.query_params.get('search')
        combo_id = request.query_params.get('combo_id')
        
        # Pagination parameters
        page = int(request.query_params.get('page', 1))
        page_size = int(request.query_params.get('page_size', 20))
        
        # Limit max page size to prevent abuse
        page_size = min(page_size, 100)
        
        # Calculate offset
        offset = (page - 1) * page_size
        
        # Build domain
        if category_id:
            domain.append(('categ_id', '=', int(category_id)))

        if tag_id:
            domain.append(('product_tag_ids', 'in', [int(tag_id)]))

        if search_by_name:
            domain.append(('name', 'ilike', search_by_name))
            
        if combo_id:
            domain.append(('combo_ids', 'in', [int(combo_id)]))

        try:
            user = request.user
            odoo = get_odoo_client_with_cached_session(username=user.username)
            
            # Check if odoo is a Response (error response)
            if isinstance(odoo, Response):
                return odoo

            if combo_id:
                products = _get_products_by_combo_id(int(combo_id), odoo, product_domain=domain)
                total_count = len(products)
                has_more = False
            else:
                # Call Odoo with pagination
                result = odoo.call(
                    model='product.template',
                    method='search_read',
                    kwargs={
                        'domain': domain,
                        'fields': [
                            'id', 'name', 'default_code', 'list_price',
                            'uom_id', 'formula_id', 'image_url_1920', 'taxes_id',
                            'uom_name', 'standard_price', 'categ_id', 'product_tag_ids',
                            'qty_available',
                        ]
                    },
                    limit=page_size,
                    offset=offset
                )
                
                # Extract pagination metadata
                products = result.get('result', [])
                total_count = result.get('total_count', len(products))
                has_more = result.get('has_more', False)
            
            # Apply profit percentage for salesperson
            if request.user.salesperson_id:
                profit_percentage = _get_profit_per_order(request.user.salesperson_id)
                for product in products:
                    if 'list_price' in product:
                        product['list_price'] = round(product['list_price'] * (1 + profit_percentage), 2)
            
            # Calculate pagination info
            total_pages = (total_count + page_size - 1) // page_size if total_count > 0 else 1
            
            return Response({
                "products": products,
                "pagination": {
                    "page": page,
                    "page_size": page_size,
                    "total_count": total_count,
                    "total_pages": total_pages,
                    "has_next": has_more,
                    "has_previous": page > 1,
                }
            })

        except Exception as e:
            return Response(
                {"error": str(e)}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class ProductRetrieveAPIView(GenericAPIView):
    """
    Retrieve a single product by ID.
    """
    
    @extend_schema(
        responses={200: ProductSerializer},
        summary="Retrieve a product by ID",
    )
    def get(self, request, id):
        try:
            user = request.user
            odoo = get_odoo_client_with_cached_session(username=user.username)
            
            # Check if odoo is a Response (error response)
            if isinstance(odoo, Response):
                return odoo

            # Get product from Odoo
            result = odoo.call(
                model='product.template',
                method='search_read',
                kwargs={
                    'domain': [('id', '=', int(id))],
                    'fields': [
                        'id', 'name', 'default_code', 'list_price',
                        'uom_id', 'formula_id', 'image_url_1920', 'taxes_id',
                        'uom_name', 'standard_price', 'categ_id', 'product_tag_ids', 
                        'qty_available'
                    ],
                    'limit': 1
                }
            )
            
            products = result.get('result', [])
            
            if not products:
                raise NotFound("Product not found.")
            
            product = products[0]
            
            # Apply profit percentage for salesperson
            if request.user.salesperson_id:
                profit_percentage = _get_profit_per_order(request.user.salesperson_id)
                if 'list_price' in product:
                    product['list_price'] = round(product['list_price'] * (1 + profit_percentage), 2)
            
            return Response(product, status=status.HTTP_200_OK)

        except NotFound as e:
            return Response(
                {"error": str(e)}, 
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {"error": str(e)}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class ProductCategoryListAPIView(GenericAPIView):
    """
    Returns paginated product categories with metadata.
    """
    
    @extend_schema(
        parameters=[
            OpenApiParameter(
                name='page',
                description='Page number (default: 1)',
                required=False,
                type=int,
                location=OpenApiParameter.QUERY,
            ),
            OpenApiParameter(
                name='page_size',
                description='Number of items per page (default: 20, max: 100)',
                required=False,
                type=int,
                location=OpenApiParameter.QUERY,
            ),
        ],
        responses={200: ProductCategorySerializer(many=True)},
        summary="List all product categories with pagination",
    )
    def get(self, request):
        # Pagination parameters
        page = int(request.query_params.get('page', 1))
        page_size = int(request.query_params.get('page_size', 20))
        
        # Limit max page size to prevent abuse
        page_size = min(page_size, 100)
        
        # Calculate offset
        offset = (page - 1) * page_size

        try:
            user = request.user
            odoo = get_odoo_client_with_cached_session(username=user.username)
            
            # Check if odoo is a Response (error response)
            if isinstance(odoo, Response):
                return odoo

            # Call Odoo with pagination
            result = odoo.call(
                model='product.category',
                method='search_read',
                kwargs={
                    'fields': [
                        'id', 'name', 'product_count', 'image_url_1920'
                    ]
                },
                limit=page_size,
                offset=offset
            )

            # Extract pagination metadata
            categories = result.get('result', [])
            total_count = result.get('total_count', len(categories))
            has_more = result.get('has_more', False)
            
            # Calculate pagination info
            total_pages = (total_count + page_size - 1) // page_size if total_count > 0 else 1
            
            return Response({
                "categories": categories,
                "pagination": {
                    "page": page,
                    "page_size": page_size,
                    "total_count": total_count,
                    "total_pages": total_pages,
                    "has_next": has_more,
                    "has_previous": page > 1,
                }
            })

        except Exception as e:
            return Response(
                {"error": str(e)}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class ProductTagListAPIView(GenericAPIView):
    """
    Returns paginated product tags with metadata.
    """
    
    @extend_schema(
        parameters=[
            OpenApiParameter(
                name='page',
                description='Page number (default: 1)',
                required=False,
                type=int,
                location=OpenApiParameter.QUERY,
            ),
            OpenApiParameter(
                name='page_size',
                description='Number of items per page (default: 20, max: 100)',
                required=False,
                type=int,
                location=OpenApiParameter.QUERY,
            ),
        ],
        responses={200: ProductTagSerializer(many=True)},
        summary="List all product tags with pagination",
    )
    def get(self, request):
        # Pagination parameters
        page = int(request.query_params.get('page', 1))
        page_size = int(request.query_params.get('page_size', 20))
        
        # Limit max page size to prevent abuse
        page_size = min(page_size, 100)
        
        # Calculate offset
        offset = (page - 1) * page_size

        try:
            user = request.user
            odoo = get_odoo_client_with_cached_session(username=user.username)
            
            # Check if odoo is a Response (error response)
            if isinstance(odoo, Response):
                return odoo

            # Call Odoo with pagination
            result = odoo.call(
                model='product.tag',
                method='search_read',
                kwargs={
                    'fields': [
                        'id', 'name'
                    ]
                },
                limit=page_size,
                offset=offset
            )

            # Extract pagination metadata
            tags = result.get('result', [])
            total_count = result.get('total_count', len(tags))
            has_more = result.get('has_more', False)
            
            # Calculate pagination info
            total_pages = (total_count + page_size - 1) // page_size if total_count > 0 else 1
            
            return Response({
                "tags": tags,
                "pagination": {
                    "page": page,
                    "page_size": page_size,
                    "total_count": total_count,
                    "total_pages": total_pages,
                    "has_next": has_more,
                    "has_previous": page > 1,
                }
            })

        except Exception as e:
            return Response(
                {"error": str(e)}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class ProductFormulaRetrieveAPIView(GenericAPIView):
    """
    Retrieve a single product formula by ID.
    """
    
    @extend_schema(
        responses={200: ProductFormulaSerializer},
        summary="Retrieve a product formula by ID",
    )
    def get(self, request, id):
        try:
            user = request.user
            odoo = get_odoo_client_with_cached_session(username=user.username)
            
            # Check if odoo is a Response (error response)
            if isinstance(odoo, Response):
                return odoo

            # Get formula from Odoo
            result = odoo.call(
                model='product.formula',
                method='search_read',
                kwargs={
                    'domain': [('id', '=', int(id))],
                    'fields': [
                        'id', 'name', 'formula', 'active'
                    ],
                    'limit': 1
                }
            )
            
            formulas = result.get('result', [])
            
            if not formulas:
                raise NotFound("Formula not found.")
            
            return Response(formulas[0], status=status.HTTP_200_OK)

        except NotFound as e:
            return Response(
                {"error": str(e)}, 
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {"error": str(e)}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class ProductFormulaCalculateAPIView(GenericAPIView):
    """
    Calculate product price using a formula.
    """
    
    serializer_class = ProductFormulaCalculateSerializer

    @extend_schema(
        request=ProductFormulaCalculateSerializer,
        responses={200: serializers.FloatField()},
        summary="Calculate product price using a formula",
    )
    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        validated_data = serializer.validated_data

        try:
            user = request.user
            odoo = get_odoo_client_with_cached_session(username=user.username)
            
            # Check if odoo is a Response (error response)
            if isinstance(odoo, Response):
                return odoo

            formula_id = validated_data['formula_id']
            product_id = validated_data['product_id']
            width = validated_data['width']
            height = validated_data['height']
            count = validated_data.get('count', 1)
            
            # Create first wizard with take_remains=True
            formula_wizard_id_1 = odoo.call(
                model='product.formula.wizard',
                method='create',
                args=[{
                    'formula_id': formula_id,
                    'product_id': product_id,
                    'width': width,
                    'height': height,
                    'count': count,
                    'take_remains': True,
                }]
            )
            
            # Apply formula for first wizard
            result_1 = odoo.call(
                model='product.formula.wizard',
                method='apply_formula',
                args=[formula_wizard_id_1]
            )
            
            # Create second wizard with take_remains=False
            formula_wizard_id_2 = odoo.call(
                model='product.formula.wizard',
                method='create',
                args=[{
                    'formula_id': formula_id,
                    'product_id': product_id,
                    'width': width,
                    'height': height,
                    'count': count,
                    'take_remains': False,
                }]
            )
            
            # Apply formula for second wizard
            result_2 = odoo.call(
                model='product.formula.wizard',
                method='apply_formula',
                args=[formula_wizard_id_2]
            )
            
            return Response({
                'result_with_remains': result_1,
                'result_without_remains': result_2,
                'combined_result': f'{result_1},{result_2}'
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response(
                {"error": str(e)}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class ProductFullAPIView(GenericAPIView):
    """
    Returns paginated products with metadata.
    """
    
    @extend_schema(
        parameters=[
            OpenApiParameter(
                name='search',
                description='Search products by name',
                required=False,
                type=str,
                location=OpenApiParameter.QUERY,
            ),
            OpenApiParameter(
                name='tag',
                description='Filter products by tag ID',
                required=False,
                type=int,
                location=OpenApiParameter.QUERY,
            ),
            OpenApiParameter(
                name='category',
                description='Filter products by category ID',
                required=False,
                type=int,
                location=OpenApiParameter.QUERY,
            ),
            OpenApiParameter(
                name='combo_id',
                description='Filter products by combo ID',
                required=False,
                type=int,
                location=OpenApiParameter.QUERY,
            ),
            OpenApiParameter(
                name='page',
                description='Page number (default: 1)',
                required=False,
                type=int,
                location=OpenApiParameter.QUERY,
            ),
            OpenApiParameter(
                name='page_size',
                description='Number of items per page (default: 20, max: 100)',
                required=False,
                type=int,
                location=OpenApiParameter.QUERY,
            ),
        ],
        responses={200: ProductSerializer(many=True)},
        summary="List all products with pagination and optional filtering",
    )
    def get(self, request):
        domain = []

        # Get query parameters
        tag_id = request.query_params.get('tag')
        category_id = request.query_params.get('category')
        search_by_name = request.query_params.get('search')
        combo_id = request.query_params.get('combo_id')
        
        # Pagination parameters
        page = int(request.query_params.get('page', 1))
        page_size = int(request.query_params.get('page_size', 20))
        
        # Limit max page size to prevent abuse
        page_size = min(page_size, 100)
        
        # Calculate offset
        offset = (page - 1) * page_size
        
        # Build domain
        if category_id:
            domain.append(('categ_id', '=', int(category_id)))

        if tag_id:
            domain.append(('product_tag_ids', 'in', [int(tag_id)]))

        if search_by_name:
            domain.append(('name', 'ilike', search_by_name))
            
        if combo_id:
            domain.append(('combo_ids', 'in', [int(combo_id)]))

        try:
            user = request.user
            odoo = get_odoo_client_with_cached_session(username=user.username)
            
            # Check if odoo is a Response (error response)
            if isinstance(odoo, Response):
                return odoo

            # Call Odoo with pagination and relation field filtering
            result = odoo.call(
                model='product.template',
                method='search_read',
                kwargs={
                    'domain': domain,
                    'fields': [
                        'id', 'name', 'default_code', 'list_price',
                        'uom_id', 'image_url_1920', 'taxes_id', 'standard_price',
                        'categ_id', 'product_tag_ids', 'qty_available',
                        'product_variant_ids',
                        'attribute_line_ids',
                        'combo_ids',
                    ]
                },
                limit=page_size,
                offset=offset,
                relation_fields={
                    # Limit fields in related records for better performance
                    'categ_id': ['id', 'name', 'complete_name'],
                    'uom_id': ['id', 'name', 'uom_type'],
                    'product_tag_ids': ['id', 'name', 'color'],
                    'taxes_id': ['id', 'name', 'amount', 'type_tax_use'],
                    'product_variant_ids': ['id', 'display_name', 'default_code', 'barcode'],
                    'attribute_line_ids': ['id', 'attribute_id', 'value_ids'],
                    'combo_ids': ['id', 'name', 'discount_type', 'discount_value', 'combo_item_ids', 'basic_price'],
                    'combo_item_ids': ['id', 'product_id', 'original_price', 'extra_price'],
                }
            )

            # Extract pagination metadata
            products = result.get('result', [])
            total_count = result.get('total_count', len(products))
            has_more = result.get('has_more', False)
            
            # Calculate pagination info
            total_pages = (total_count + page_size - 1) // page_size  # Ceiling division
            
            return Response({
                "products": products,
                "pagination": {
                    "page": page,
                    "page_size": page_size,
                    "total_count": total_count,
                    "total_pages": total_pages,
                    "has_next": has_more,
                    "has_previous": page > 1,
                }
            })

        except Exception as e:
            return Response(
                {"error": str(e)}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class ProductFullRetrieveAPIView(GenericAPIView):
    """
    Retrieve a single product by ID with full details.
    """
    
    @extend_schema(
        responses={200: ProductSerializer},
        summary="Retrieve a product by ID with full details",
    )
    def get(self, request, id):
        try:
            user = request.user
            odoo = get_odoo_client_with_cached_session(username=user.username)
            
            # Check if odoo is a Response (error response)
            if isinstance(odoo, Response):
                return odoo

            # Get product from Odoo with relation field filtering
            result = odoo.call(
                model='product.template',
                method='search_read',
                kwargs={
                    'domain': [('id', '=', int(id))],
                    'fields': [
                        'id', 'name', 'default_code', 'list_price',
                        'uom_id', 'image_url_1920', 'taxes_id', 'standard_price',
                        'categ_id', 'product_tag_ids', 'qty_available',
                        'product_variant_ids',
                        'attribute_line_ids',
                        'combo_ids',
                    ],
                    'limit': 1
                },
                relation_fields={
                    # Limit fields in related records for better performance
                    'categ_id': ['id', 'name', 'complete_name'],
                    'uom_id': ['id', 'name', 'uom_type'],
                    'product_tag_ids': ['id', 'name', 'color'],
                    'taxes_id': ['id', 'name', 'amount', 'type_tax_use'],
                    'product_variant_ids': ['id', 'display_name', 'default_code', 'barcode'],
                    'attribute_line_ids': ['id', 'attribute_id', 'value_ids'],
                    'combo_ids': ['id', 'name', 'discount_type', 'discount_value', 'combo_item_ids', 'basic_price'],
                    'combo_item_ids': ['id', 'product_id', 'original_price', 'extra_price'],
                }
            )
            
            products = result.get('result', [])
            
            if not products:
                raise NotFound("Product not found.")
            
            return Response(products[0], status=status.HTTP_200_OK)

        except NotFound as e:
            return Response(
                {"error": str(e)}, 
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {"error": str(e)}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
